"""Clustering: L0 deterministic, L1 fingerprint, L2 TF-IDF within L0."""

from __future__ import annotations

from collections import defaultdict

from contracts.models import Cluster, ClustersArtifact, FailureType, SimulationFeatures

_DB_FAILURE_TYPES = frozenset({FailureType.DB_ONLY, FailureType.MIXED})
_NL_FAILURE_TYPES = frozenset({FailureType.NL_ONLY, FailureType.MIXED})


def _tool_fingerprint(sim: SimulationFeatures) -> str:
    """Normalized tool chain (P2): names only, consecutive duplicates collapsed."""
    chain = sim.normalized_tool_chain or [t.name for t in sim.tool_sequence]
    return "->".join(chain) if chain else "no_tools"


def _primary_signature(sim: SimulationFeatures) -> str:
    """Mechanism signature used as the L1 grouping key (P1/P3/P4).

    DB failures group by their structured DB-diff signature; NL failures by
    the denoised failed-assertion signature; everything else falls back to the
    normalized write-tool chain. This replaces the old exact tool-path key
    that produced ~79% singletons.
    """
    parts: list[str] = []
    if sim.failure_type in _DB_FAILURE_TYPES:
        parts.append(f"db={sim.db_diff_signature or 'unknown'}")
    if sim.failure_type in _NL_FAILURE_TYPES:
        parts.append(f"nl={sim.nl_failure_signature or 'unknown'}")
    if not parts:
        chain = sim.write_tool_sequence or sim.normalized_tool_chain
        parts.append(f"chain={'->'.join(chain) if chain else 'no_tools'}")
    return " | ".join(parts)


def _refine_group(
    sims: list[SimulationFeatures],
    *,
    min_size: int = 6,
    distance_threshold: float = 0.5,
) -> list[list[SimulationFeatures]]:
    """Optionally split a large same-signature group by tool-chain similarity.

    Uses agglomerative clustering with a cosine distance *threshold* (not a
    fixed cluster count), so tight groups stay intact and we avoid
    reintroducing singleton fragmentation.
    """
    if len(sims) < min_size:
        return [sims]
    try:
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        return [sims]

    texts = [" ".join(s.normalized_tool_chain) or "none" for s in sims]
    try:
        matrix = TfidfVectorizer().fit_transform(texts).toarray()
        if matrix.shape[1] < 2:
            return [sims]
        labels = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric="cosine",
            linkage="average",
        ).fit_predict(matrix)
    except Exception:
        return [sims]

    sub: dict[int, list[SimulationFeatures]] = defaultdict(list)
    for sim, label in zip(sims, labels):
        sub[int(label)].append(sim)
    return list(sub.values())


def _flag_summary(features: list[SimulationFeatures]) -> dict[str, int]:
    summary: dict[str, int] = defaultdict(int)
    for f in features:
        pf = f.policy_flags
        if pf.auth_before_mutate is False:
            summary["auth_missing"] += 1
        if pf.confirm_before_write is False:
            summary["confirm_missing"] += 1
        if not pf.single_tool_per_turn:
            summary["multi_tool_turn"] += 1
        if pf.num_env_errors:
            summary["env_errors"] += 1
    return dict(summary)


def _failure_rate_for_tasks(
    sims: list[SimulationFeatures],
) -> tuple[float, list[str]]:
    task_trials: dict[str, list[bool]] = defaultdict(list)
    for s in sims:
        task_trials[s.task_id].append(s.failure_type == FailureType.PASS)
    if not task_trials:
        return 0.0, []
    rates = [1.0 - (sum(passes) / len(passes)) for passes in task_trials.values()]
    avg_rate = sum(rates) / len(rates)
    task_ids = sorted(task_trials.keys())
    return avg_rate, task_ids


def cluster_l0(
    simulations: list[SimulationFeatures],
    run_name: str,
) -> ClustersArtifact:
    buckets: dict[str, list[SimulationFeatures]] = defaultdict(list)
    for sim in simulations:
        if sim.failure_type == FailureType.PASS:
            key = "pass"
        elif sim.failure_type == FailureType.MIXED:
            key = f"mixed:{sim.termination_reason or 'unknown'}"
        else:
            key = f"{sim.failure_type.value}:{sim.termination_reason or 'unknown'}"
        buckets[key].append(sim)

    clusters: list[Cluster] = []
    for idx, (key, sims) in enumerate(sorted(buckets.items())):
        failure_rate, task_ids = _failure_rate_for_tasks(sims)
        clusters.append(
            Cluster(
                id=f"l0_{idx:03d}",
                name=key,
                failure_type=sims[0].failure_type.value,
                simulation_ids=[s.simulation_id for s in sims],
                task_ids=task_ids,
                failure_rate=failure_rate,
                count=len(sims),
            )
        )

    clusters.sort(key=lambda c: (-c.failure_rate, -c.count, c.id))
    return ClustersArtifact(
        contract_version="1.0", run_name=run_name, layer="l0", clusters=clusters
    )


def cluster_l1_l2(
    simulations: list[SimulationFeatures],
    l0_clusters: ClustersArtifact,
    run_name: str,
) -> ClustersArtifact:
    """Group failing sims by mechanism signature (P1/P3), then refine large
    same-signature groups by tool-chain similarity (P2/P4)."""
    failing_sims = [s for s in simulations if s.failure_type != FailureType.PASS]
    if not failing_sims:
        return ClustersArtifact(
            contract_version="1.0", run_name=run_name, layer="final", clusters=[]
        )

    sim_to_l0: dict[str, str] = {}
    for c in l0_clusters.clusters:
        for sid in c.simulation_ids:
            sim_to_l0[sid] = c.id

    groups: dict[tuple[str, str], list[SimulationFeatures]] = defaultdict(list)
    for sim in failing_sims:
        parent = sim_to_l0.get(sim.simulation_id, "l0_unknown")
        groups[(parent, _primary_signature(sim))].append(sim)

    refined: list[tuple[str, str, list[SimulationFeatures]]] = []
    for (parent, signature), sims in groups.items():
        for sub_sims in _refine_group(sims):
            refined.append((parent, signature, sub_sims))

    clusters: list[Cluster] = []
    for idx, (parent, signature, sims) in enumerate(
        sorted(refined, key=lambda x: -len(x[2]))
    ):
        failure_rate, task_ids = _failure_rate_for_tasks(sims)
        ft = sims[0].failure_type.value
        fp = _tool_fingerprint(sims[0])
        clusters.append(
            Cluster(
                id=f"c_{idx:03d}",
                name=f"{ft} | {signature}",
                failure_type=ft,
                parent_l0_id=parent,
                simulation_ids=[s.simulation_id for s in sims],
                task_ids=task_ids,
                failure_rate=failure_rate,
                count=len(sims),
                signature=signature,
                tool_sequence_fingerprint=fp,
                policy_flag_summary=_flag_summary(sims),
            )
        )

    clusters.sort(key=lambda c: (-c.failure_rate, -c.count, c.id))
    return ClustersArtifact(
        contract_version="1.0", run_name=run_name, layer="final", clusters=clusters
    )


def assign_cluster_to_simulations(
    simulations: list[SimulationFeatures],
    clusters: ClustersArtifact,
) -> dict[str, str]:
    """Map simulation_id -> cluster_id (pass sims -> 'pass')."""
    mapping: dict[str, str] = {}
    for sim in simulations:
        if sim.failure_type == FailureType.PASS:
            mapping[sim.simulation_id] = "pass"
    for cluster in clusters.clusters:
        for sid in cluster.simulation_ids:
            mapping[sid] = cluster.id
    return mapping
