"""Embedding-based clustering engine (generalizable alternative to signatures).

The signature engine (``lib/clustering.py``) groups failures by a hand-built,
domain-specific decision tree over the DB-diff / NL signatures. This module is
the "less bucketed" counterpart: it turns each failing trace into a text
*document*, embeds it with a pluggable embedder, and clusters the embeddings by
similarity (HDBSCAN or agglomerative with a cosine distance threshold). No
domain rules decide cluster membership — the geometry of the embedding does.

Output is a ``ClustersArtifact`` identical in shape to the signature engine's,
so the dashboard, labeler, report, and subset builder consume it unchanged.
By default clustering runs *within* each L0 failure bucket (``scope="l0"``) so
we never merge across reward axes (db vs nl); ``scope="global"`` lets the
embedding define everything.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional, Protocol

from contracts.models import Cluster, ClustersArtifact, FailureType, SimulationFeatures
from lib.clustering import (
    _failure_rate_for_tasks,
    _flag_summary,
    _primary_signature,
    _tool_fingerprint,
)

# ---------------------------------------------------------------------------
# Trace -> document
# ---------------------------------------------------------------------------


def _signature_tokens(signature: Optional[str]) -> str:
    """Flatten a DB-diff signature into readable tokens for embedding.

    ``missed:orders.*.exchange_items;wrong:orders.*.items[].price``
      -> ``missed exchange_items wrong items price``
    """
    if not signature:
        return ""
    skip = {"orders", "users", "products", "*", ""}
    tokens: list[str] = []
    for item in signature.split(";"):
        kind, _, path = item.partition(":")
        tokens.append(kind)
        for part in path.split("."):
            part = part.replace("[]", "")
            if part not in skip:
                tokens.append(part)
    return " ".join(tokens)


# "why" segments that can be toggled on/off for ablation. The core spine
# (failure type, tool chain, writes, DB divergence, flags) is always included.
WHY_FIELDS = ("nl", "escalation", "last_message", "tool_errors", "mechanism")


def build_cluster_document(
    sim: SimulationFeatures,
    fields: Optional[set[str]] = None,
) -> str:
    """Natural-ish text summary of a failing trace for embedding.

    The core spine describes *what* the agent did and *what diverged*; the
    optional ``fields`` (subset of ``WHY_FIELDS``) add root-cause "why" signals
    (NL miss, escalation, last message, tool errors). ``fields=None`` includes
    all of them. Kept as words (not opaque paths) so both bag-of-words and
    neural embedders work. Termination is omitted (constant on retail runs).
    """
    active = WHY_FIELDS if fields is None else fields

    # --- core spine (always on) ---
    parts: list[str] = [f"failure {sim.failure_type.value}"]
    chain = sim.normalized_tool_chain or [t.name for t in sim.tool_sequence]
    parts.append("tools " + (" ".join(chain) if chain else "none"))
    parts.append(
        "writes "
        + (" ".join(sim.write_tool_sequence) if sim.write_tool_sequence else "none")
    )
    if sim.db_diff_signature:
        parts.append("db " + _signature_tokens(sim.db_diff_signature))
    if sim.db_diff_entities:
        parts.append("entities " + " ".join(sim.db_diff_entities))

    pf = sim.policy_flags
    flags = []
    if pf.auth_before_mutate is False:
        flags.append("auth_missing")
    if pf.confirm_before_write is False:
        flags.append("confirm_missing")
    if not pf.single_tool_per_turn:
        flags.append("multi_tool_turn")
    if pf.num_env_errors:
        flags.append("env_errors")
    if flags:
        parts.append("flags " + " ".join(flags))

    # --- optional "why" segments ---
    if "nl" in active and sim.nl_failure_signature:
        parts.append("nl " + sim.nl_failure_signature)
    if "escalation" in active:
        parts.append(
            "escalated transfer human" if sim.escalated_to_human else "escalated no"
        )
    if "last_message" in active and sim.last_agent_message:
        parts.append("said " + sim.last_agent_message)
    if "tool_errors" in active and sim.tool_error_messages:
        parts.append("errors " + " ".join(sim.tool_error_messages))
    if "mechanism" in active and sim.mechanism_class:
        parts.append("mechanism " + sim.mechanism_class.replace("_", " "))

    return " . ".join(parts)


# ---------------------------------------------------------------------------
# Pluggable embedders
# ---------------------------------------------------------------------------


class Embedder(Protocol):
    name: str

    def embed(self, docs: list[str]):  # -> np.ndarray (n_docs, dim)
        ...


class TfidfEmbedder:
    """Offline bag-of-words (1-2 gram) embedder. Default; sklearn-only."""

    name = "tfidf"

    def embed(self, docs: list[str]):
        import numpy as np

        if len(docs) <= 1:
            return np.ones((len(docs), 1), dtype=float)
        from sklearn.feature_extraction.text import TfidfVectorizer

        matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(docs)
        return matrix.toarray()


class CharEmbedder:
    """Offline character n-gram (3-5) TF-IDF embedder. Captures token
    morphology / shared substrings; sklearn-only."""

    name = "char"

    def embed(self, docs: list[str]):
        import numpy as np

        if len(docs) <= 1:
            return np.ones((len(docs), 1), dtype=float)
        from sklearn.feature_extraction.text import TfidfVectorizer

        matrix = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=1
        ).fit_transform(docs)
        return matrix.toarray()


class LsaEmbedder:
    """Offline dense latent embedding: TF-IDF -> TruncatedSVD (LSA). A real
    low-dimensional embedding using only sklearn (no neural deps)."""

    def __init__(self, n_components: int = 64) -> None:
        self.n_components = n_components
        self.name = f"lsa:{n_components}"

    def embed(self, docs: list[str]):
        import numpy as np

        if len(docs) <= 1:
            return np.ones((len(docs), 1), dtype=float)
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(docs)
        n_comp = min(self.n_components, tfidf.shape[1] - 1, tfidf.shape[0] - 1)
        if n_comp < 2:
            return tfidf.toarray()
        return TruncatedSVD(n_components=n_comp, random_state=0).fit_transform(tfidf)


class SentenceTransformerEmbedder:
    """Neural sentence embedder (all-MiniLM-L6-v2 by default).

    Uses the ``sentence-transformers`` library when installed; otherwise falls
    back to an offline pure-NumPy MiniLM forward pass over the HF-cached weights
    (``lib.minilm_numpy``), so it works on this torch-less / network-less box.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self.name = f"st:{model_name}"

    def embed(self, docs: list[str]):
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name)
            return model.encode(list(docs), normalize_embeddings=True)
        except ImportError:
            from lib import minilm_numpy

            if "MiniLM-L6-v2" in self.model_name and minilm_numpy.is_available():
                return minilm_numpy.encode(list(docs))
            raise RuntimeError(
                "sentence-transformers not installed and no offline backend for "
                f"'{self.model_name}'. Install sentence-transformers or use a "
                "cached all-MiniLM-L6-v2 model."
            ) from None


# Offline embedders (no neural deps) available on any harness-opt install.
OFFLINE_EMBEDDERS = ("tfidf", "char", "lsa")

# Cosine distance thresholds tuned per embedder against ground-truth labels
# (see eval/ablation.*.md). Neural embeddings cluster tighter than TF-IDF.
DEFAULT_THRESHOLD_BY_EMBEDDER = {
    "st": 0.3,
    "tfidf": 0.6,
    "lsa": 0.6,
    "char": 0.4,
}

# Auto-threshold: a single fixed cosine threshold doesn't transfer across runs
# with very different failure distributions (e.g. a weak model collapses 74% of
# failures into one blob at 0.3). Instead, scan a loose->tight ladder and take
# the loosest threshold whose largest cluster stays under MAX_CLUSTER_SHARE.
# This reproduces the label-validated granularity on the tuning run and avoids
# the blob on high-failure runs. See eval/ablation.*.md and the cross-run report.
# Cap of 0.45 tuned against the baseline-gpt55-t2 ground-truth labels: it
# reproduces the ARI-optimal 6-cluster result on the tuning run (ARI 0.70) while
# tightening the weak-model run from a 74% blob to 30 clusters (22% largest).
DEFAULT_THRESHOLD_LADDER = (0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15)
DEFAULT_MAX_CLUSTER_SHARE = 0.45


def st_available() -> bool:
    """True if a neural 'st' backend can run (library or offline cache)."""
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        pass
    try:
        from lib import minilm_numpy

        return minilm_numpy.is_available()
    except Exception:
        return False


def get_embedder(name: str) -> Embedder:
    key = (name or "tfidf").lower()
    if key in ("tfidf", "tf-idf", "bow"):
        return TfidfEmbedder()
    if key == "char":
        return CharEmbedder()
    if key in ("lsa", "svd"):
        return LsaEmbedder()
    if key.startswith("lsa:"):
        return LsaEmbedder(int(key[4:]))
    if key in ("st", "sentence-transformers", "sbert"):
        return SentenceTransformerEmbedder()
    if key.startswith("st:"):
        return SentenceTransformerEmbedder(key[3:])
    raise ValueError(
        f"Unknown embedder '{name}'. Offline: {', '.join(OFFLINE_EMBEDDERS)}; "
        "neural: 'st' (requires sentence-transformers)."
    )


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def _l0_key(sim: SimulationFeatures) -> str:
    if sim.failure_type == FailureType.MIXED:
        return f"mixed:{sim.termination_reason or 'unknown'}"
    return f"{sim.failure_type.value}:{sim.termination_reason or 'unknown'}"


def _agglomerative(vectors, threshold: float) -> list[int]:
    from sklearn.cluster import AgglomerativeClustering

    labels = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=threshold,
        metric="cosine",
        linkage="average",
    ).fit_predict(vectors)
    return [int(x) for x in labels]


def _auto_select_labels(
    vectors,
    ladder: tuple[float, ...],
    max_cluster_share: float,
) -> list[int]:
    """Loosest threshold whose largest cluster share <= cap; else the tightest.

    Only re-clusters cached vectors, so this is sub-second at our scale.
    """
    fallback: list[int] = [0] * len(vectors)
    for threshold in ladder:  # loose -> tight
        labels = _agglomerative(vectors, threshold)
        counts = Counter(labels)
        share = max(counts.values()) / len(labels)
        fallback = labels
        if share <= max_cluster_share:
            return labels
    return fallback  # nothing satisfied the cap -> tightest (most split)


def _cluster_labels(
    sims: list[SimulationFeatures],
    embedder: Embedder,
    *,
    algo: str,
    distance_threshold: Optional[float],
    min_cluster_size: int,
    document_fields: Optional[set[str]] = None,
    max_cluster_share: float = DEFAULT_MAX_CLUSTER_SHARE,
    threshold_ladder: tuple[float, ...] = DEFAULT_THRESHOLD_LADDER,
) -> list[int]:
    """Return an integer cluster label per sim within one scope bucket.

    ``distance_threshold=None`` enables auto-selection (share-capped ladder);
    a positive value forces that fixed threshold.
    """
    n = len(sims)
    if n <= 1:
        return [0] * n

    docs = [build_cluster_document(s, fields=document_fields) for s in sims]
    try:
        import numpy as np

        vectors = np.asarray(embedder.embed(docs), dtype=float)
    except Exception:
        return list(range(n))  # degrade: every sim its own cluster

    if vectors.shape[1] < 1 or np.allclose(vectors, vectors[0]):
        return [0] * n  # all identical -> one cluster

    try:
        if algo == "hdbscan":
            from sklearn.cluster import HDBSCAN

            labels = HDBSCAN(
                min_cluster_size=max(2, min_cluster_size),
                metric="euclidean",
            ).fit_predict(_l2_normalize(vectors))
            return _relabel_noise(labels)

        if distance_threshold is None:
            return _auto_select_labels(vectors, threshold_ladder, max_cluster_share)
        return _agglomerative(vectors, distance_threshold)
    except Exception:
        return list(range(n))


def _l2_normalize(vectors):
    import numpy as np

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _relabel_noise(labels) -> list[int]:
    """HDBSCAN marks outliers as -1; give each its own cluster id."""
    out: list[int] = []
    next_id = max([int(x) for x in labels], default=-1) + 1
    for x in labels:
        if int(x) == -1:
            out.append(next_id)
            next_id += 1
        else:
            out.append(int(x))
    return out


def _dominant_signature(sims: list[SimulationFeatures]) -> str:
    counts = Counter(_primary_signature(s) for s in sims)
    return counts.most_common(1)[0][0]


def _dominant_mechanism(sims: list[SimulationFeatures]) -> str:
    counts = Counter(s.mechanism_class for s in sims)
    return counts.most_common(1)[0][0]


# Ablation-validated default document (ground-truth root-cause labels): the
# core spine plus the denoised last-agent message. See eval/ablation.*.md.
DEFAULT_DOCUMENT_FIELDS = frozenset({"last_message"})


def cluster_embeddings(
    simulations: list[SimulationFeatures],
    run_name: str,
    *,
    embedder: Optional[Embedder] = None,
    scope: str = "l0",
    algo: str = "agglomerative",
    distance_threshold: Optional[float] = None,
    min_cluster_size: int = 2,
    document_fields: Optional[set[str]] = None,
    max_cluster_share: float = DEFAULT_MAX_CLUSTER_SHARE,
    threshold_ladder: tuple[float, ...] = DEFAULT_THRESHOLD_LADDER,
) -> ClustersArtifact:
    """Cluster failing sims by embedded-document similarity.

    scope="l0": cluster within each (failure_type, termination) bucket.
    scope="global": cluster all failing sims together.
    document_fields: which "why" segments to include (default: last_message).
    distance_threshold: None (default) auto-selects per bucket via a share-capped
      ladder; a positive value forces a fixed threshold. Values <=0 mean auto.
    """
    embedder = embedder or TfidfEmbedder()
    if document_fields is None:
        document_fields = set(DEFAULT_DOCUMENT_FIELDS)
    if distance_threshold is not None and distance_threshold <= 0:
        distance_threshold = None
    failing = [s for s in simulations if s.failure_type != FailureType.PASS]
    if not failing:
        return ClustersArtifact(
            run_name=run_name, layer="final", method="embedding", clusters=[]
        )

    buckets: dict[str, list[SimulationFeatures]] = defaultdict(list)
    for sim in failing:
        key = _l0_key(sim) if scope == "l0" else "all"
        buckets[key].append(sim)

    groups: list[list[SimulationFeatures]] = []
    for _, sims in sorted(buckets.items()):
        labels = _cluster_labels(
            sims,
            embedder,
            algo=algo,
            distance_threshold=distance_threshold,
            min_cluster_size=min_cluster_size,
            document_fields=document_fields,
            max_cluster_share=max_cluster_share,
            threshold_ladder=threshold_ladder,
        )
        by_label: dict[int, list[SimulationFeatures]] = defaultdict(list)
        for sim, label in zip(sims, labels):
            by_label[label].append(sim)
        groups.extend(by_label.values())

    clusters: list[Cluster] = []
    for idx, sims in enumerate(sorted(groups, key=lambda g: -len(g))):
        failure_rate, task_ids = _failure_rate_for_tasks(sims)
        ft = sims[0].failure_type.value
        signature = _dominant_signature(sims)
        mechanism = _dominant_mechanism(sims)
        clusters.append(
            Cluster(
                id=f"c_{idx:03d}",
                name=f"{mechanism} | {signature}",
                failure_type=ft,
                mechanism=mechanism,
                simulation_ids=[s.simulation_id for s in sims],
                task_ids=task_ids,
                failure_rate=failure_rate,
                count=len(sims),
                signature=signature,
                tool_sequence_fingerprint=_tool_fingerprint(sims[0]),
                policy_flag_summary=_flag_summary(sims),
            )
        )

    clusters.sort(key=lambda c: (-c.failure_rate, -c.count, c.id))
    return ClustersArtifact(
        run_name=run_name, layer="final", method="embedding", clusters=clusters
    )
