"""Integration tests for harness-opt Phase 0."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from contracts.models import (
    FailureType,
    FeaturesArtifact,
    PolicyFlags,
    SimulationFeatures,
    ToolCallRecord,
)
from lib.db_diff import diff_dbs
from lib.embedding_cluster import (
    build_cluster_document,
    cluster_embeddings,
    get_embedder,
)
from lib.trace_parser import (
    build_nl_signature,
    classify_failure,
    classify_mechanism,
    denoise_nl,
    extract_write_sequence,
    normalize_tool_chain,
)

from tau2.data_model.simulation import DBCheck, NLAssertionCheck, RewardInfo
from tau2.data_model.tasks import RewardType

HARNESS_OPT = Path(__file__).resolve().parents[1]
REPO_ROOT = HARNESS_OPT.parents[1]
FIXTURE = HARNESS_OPT / "fixtures" / "smoke_results.json"
SMOKE_RUN = "smoke-run-test"


@pytest.fixture
def smoke_simulation(tmp_path, monkeypatch):
    """Install smoke fixture as a simulation run; reports go to tmp reports dir."""
    sim_dir = REPO_ROOT / "data" / "simulations" / SMOKE_RUN
    sim_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE, sim_dir / "results.json")

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr("lib.paths.REPORTS_DIR", reports_dir)
    monkeypatch.setenv("HARNESS_OPT_REPORTS_DIR", str(reports_dir))

    yield SMOKE_RUN

    shutil.rmtree(sim_dir, ignore_errors=True)


def test_contract_models_roundtrip():
    feat = SimulationFeatures(
        simulation_id="x",
        task_id="t",
        trial=0,
        reward=1.0,
        failure_type=FailureType.PASS,
        policy_flags=PolicyFlags(single_tool_per_turn=True, num_env_errors=0),
        num_steps=1,
        embedding_text="failure_type=pass",
    )
    art = FeaturesArtifact(run_name="r", simulations=[feat])
    restored = FeaturesArtifact.model_validate_json(art.model_dump_json())
    assert restored.simulations[0].task_id == "t"


def test_trace_parser_classify_failure():
    db_only = RewardInfo(
        reward=0.0,
        reward_basis=[RewardType.DB, RewardType.NL_ASSERTION],
        reward_breakdown={RewardType.DB: 0.0, RewardType.NL_ASSERTION: 1.0},
        db_check=DBCheck(db_match=False, db_reward=0.0),
    )
    assert classify_failure(db_only, "user_stop") == FailureType.DB_ONLY

    nl_only = RewardInfo(
        reward=0.0,
        reward_basis=[RewardType.DB, RewardType.NL_ASSERTION],
        reward_breakdown={RewardType.DB: 1.0, RewardType.NL_ASSERTION: 0.0},
        db_check=DBCheck(db_match=True, db_reward=1.0),
        nl_assertions=[
            NLAssertionCheck(
                nl_assertion="Agent apologized",
                met=False,
                justification="No apology",
            )
        ],
    )
    assert classify_failure(nl_only, "user_stop") == FailureType.NL_ONLY

    mixed = RewardInfo(
        reward=0.0,
        reward_basis=[RewardType.DB, RewardType.NL_ASSERTION],
        reward_breakdown={RewardType.DB: 0.0, RewardType.NL_ASSERTION: 0.0},
        db_check=DBCheck(db_match=False, db_reward=0.0),
        nl_assertions=[
            NLAssertionCheck(
                nl_assertion="Agent apologized",
                met=False,
                justification="No apology",
            )
        ],
    )
    assert classify_failure(mixed, "user_stop") == FailureType.MIXED

    communicate_only = RewardInfo(
        reward=0.0,
        reward_basis=[RewardType.DB, RewardType.COMMUNICATE],
        reward_breakdown={RewardType.DB: 1.0, RewardType.COMMUNICATE: 0.0},
        db_check=DBCheck(db_match=True, db_reward=1.0),
    )
    assert (
        classify_failure(communicate_only, "user_stop") == FailureType.COMMUNICATE_ONLY
    )

    nl_pass_db_fail = RewardInfo(
        reward=0.0,
        reward_basis=[RewardType.DB, RewardType.NL_ASSERTION],
        reward_breakdown={RewardType.DB: 0.0, RewardType.NL_ASSERTION: 1.0},
        db_check=DBCheck(db_match=False, db_reward=0.0),
    )
    assert classify_failure(nl_pass_db_fail, "max_steps") == FailureType.TERMINATION


def test_normalize_tool_chain_collapses_consecutive_dupes():
    seq = [
        ToolCallRecord(name="get_order_details", turn=0),
        ToolCallRecord(name="get_order_details", turn=1),
        ToolCallRecord(name="cancel_pending_order", turn=2),
        ToolCallRecord(name="get_order_details", turn=3),
    ]
    assert normalize_tool_chain(seq) == [
        "get_order_details",
        "cancel_pending_order",
        "get_order_details",
    ]
    assert extract_write_sequence(seq, frozenset({"cancel_pending_order"})) == [
        "cancel_pending_order"
    ]


def test_denoise_nl_strips_task_specific_values():
    text = (
        "Agent should tell the user the total refund amount is $918.43 for #W3792453."
    )
    out = denoise_nl(text)
    assert "$" not in out and "918" not in out and "#w3792453" not in out
    assert "refund" in out and "agent should tell" in out


def test_build_nl_signature_uses_failed_assertions_only():
    ri = RewardInfo(
        reward=0.0,
        reward_basis=[RewardType.DB, RewardType.NL_ASSERTION],
        nl_assertions=[
            NLAssertionCheck(
                nl_assertion="Agent confirmed refund of $10.00",
                met=False,
                justification="no",
            ),
            NLAssertionCheck(
                nl_assertion="Agent greeted the user", met=True, justification="ok"
            ),
        ],
    )
    sig, failed = build_nl_signature(ri)
    assert sig is not None
    assert len(failed) == 1
    assert "greeted" not in sig


def test_diff_dbs_classifies_missed_wrong_extra():
    initial = {"orders": {"#W1": {"status": "pending"}}}
    gold = {"orders": {"#W1": {"status": "cancelled"}}}

    missed = diff_dbs(initial, gold, {"orders": {"#W1": {"status": "pending"}}})
    assert missed.signature == "missed:orders.*.status"

    wrong = diff_dbs(initial, gold, {"orders": {"#W1": {"status": "returned"}}})
    assert wrong.signature == "wrong:orders.*.status"

    extra = diff_dbs(
        initial,
        {"orders": {"#W1": {"status": "pending"}}},
        {"orders": {"#W1": {"status": "cancelled"}}},
    )
    assert extra.signature == "extra:orders.*.status"

    same = diff_dbs(initial, gold, gold)
    assert same.signature == "no_db_diff"


def test_analyze_pipeline(smoke_simulation, tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr("lib.paths.REPORTS_DIR", reports_dir)
    monkeypatch.setenv("HARNESS_OPT_REPORTS_DIR", str(reports_dir))

    from scripts.cluster import run_cluster
    from scripts.extract_features import run_extract
    from scripts.generate_report import run_report
    from scripts.label_clusters import run_label

    run_extract(smoke_simulation, overwrite=True)
    run_cluster(smoke_simulation, overwrite=True)
    run_label(smoke_simulation, mock=True, overwrite=True)
    run_report(smoke_simulation, overwrite=True)

    report_dir = reports_dir / smoke_simulation
    assert (report_dir / "features.json").exists()
    assert (report_dir / "clusters.json").exists()
    assert (report_dir / "cluster_labels.json").exists()
    assert (report_dir / "manifest.json").exists()
    assert (report_dir / "task_summary.csv").exists()

    clusters = json.loads((report_dir / "clusters.json").read_text())
    assert clusters["layer"] == "final"
    assert len(clusters["clusters"]) >= 1


def test_classify_mechanism_rules():
    # escalation dominates "did nothing" on a DB failure
    assert (
        classify_mechanism(
            FailureType.DB_ONLY,
            escalated_to_human=True,
            write_tool_sequence=[],
            db_diff_kinds={"missed": 3},
            tool_error_messages=[],
        )
        == "bailed_transfer"
    )
    # acted with a wrong value -> wrong_params
    assert (
        classify_mechanism(
            FailureType.DB_ONLY,
            escalated_to_human=False,
            write_tool_sequence=["cancel_pending_order"],
            db_diff_kinds={"wrong": 1},
            tool_error_messages=[],
        )
        == "wrong_params"
    )
    # acted but only missed writes -> incomplete
    assert (
        classify_mechanism(
            FailureType.DB_ONLY,
            escalated_to_human=False,
            write_tool_sequence=["return_delivered_order_items"],
            db_diff_kinds={"missed": 2},
            tool_error_messages=[],
        )
        == "incomplete_multitask"
    )
    # no writes, no escalation -> stalled
    assert (
        classify_mechanism(
            FailureType.DB_ONLY,
            escalated_to_human=False,
            write_tool_sequence=[],
            db_diff_kinds={"missed": 1},
            tool_error_messages=[],
        )
        == "stalled_no_action"
    )
    # couldn't identify user then bailed
    assert (
        classify_mechanism(
            FailureType.MIXED,
            escalated_to_human=True,
            write_tool_sequence=[],
            db_diff_kinds=None,
            tool_error_messages=["error user not found"],
        )
        == "identification_failure"
    )
    # DB ok, NL failed, no bail -> comm miss
    assert (
        classify_mechanism(
            FailureType.NL_ONLY,
            escalated_to_human=False,
            write_tool_sequence=["return_delivered_order_items"],
            db_diff_kinds=None,
            tool_error_messages=[],
        )
        == "comm_miss"
    )


def test_build_cluster_document_contains_signals():
    sim = SimulationFeatures(
        simulation_id="x",
        task_id="t",
        trial=0,
        reward=0.0,
        failure_type=FailureType.DB_ONLY,
        termination_reason="user_stop",
        normalized_tool_chain=["get_order_details", "transfer_to_human_agents"],
        write_tool_sequence=[],
        db_diff_signature="missed:orders.*.exchange_items;missed:orders.*.status",
        db_diff_entities=["orders"],
        policy_flags=PolicyFlags(single_tool_per_turn=True, num_env_errors=0),
        num_steps=4,
        embedding_text="",
    )
    doc = build_cluster_document(sim)
    assert "failure db_only" in doc
    assert "transfer_to_human_agents" in doc
    assert "writes none" in doc
    # signature flattened to readable tokens
    assert "missed" in doc and "exchange_items" in doc and "status" in doc


def test_get_embedder_selection():
    assert get_embedder("tfidf").name == "tfidf"
    assert get_embedder("char").name == "char"
    assert get_embedder("lsa").name.startswith("lsa")
    assert get_embedder("st").name.startswith("st:")
    with pytest.raises(ValueError):
        get_embedder("nope")


def test_st_embedder_offline_minilm():
    """The neural 'st' embedder runs via the offline NumPy MiniLM backend when
    the model is cached. Skips cleanly if neither backend is available."""
    from lib.embedding_cluster import st_available

    if not st_available():
        pytest.skip("no neural st backend available (no torch, no cached MiniLM)")

    import numpy as np

    emb = get_embedder("st")
    vecs = np.asarray(
        emb.embed(
            [
                "agent transferred the customer to a human agent",
                "agent escalated the case to a human representative",
                "the weather today is sunny and warm",
            ]
        ),
        dtype=float,
    )
    assert vecs.shape == (3, 384)
    assert not np.isnan(vecs).any()

    def cos(a, b):
        return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

    # paraphrases (0,1) should be closer than unrelated (0,2)
    assert cos(vecs[0], vecs[1]) > cos(vecs[0], vecs[2])


def test_embedding_cluster_engine_end_to_end(smoke_simulation, tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr("lib.paths.REPORTS_DIR", reports_dir)
    monkeypatch.setenv("HARNESS_OPT_REPORTS_DIR", str(reports_dir))

    from scripts.cluster import run_cluster
    from scripts.extract_features import run_extract

    run_extract(smoke_simulation, overwrite=True)
    run_cluster(smoke_simulation, method="embedding", overwrite=True)

    clusters = json.loads(
        (reports_dir / smoke_simulation / "clusters.json").read_text()
    )
    assert clusters["method"] == "embedding"
    assert clusters["layer"] == "final"
    assert len(clusters["clusters"]) >= 1
    # dashboard-required fields present
    c0 = clusters["clusters"][0]
    for field in ("id", "name", "failure_type", "signature", "count", "failure_rate"):
        assert field in c0


def test_cluster_compare_writes_artifacts(smoke_simulation, tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr("lib.paths.REPORTS_DIR", reports_dir)
    monkeypatch.setenv("HARNESS_OPT_REPORTS_DIR", str(reports_dir))

    from scripts.compare_clusterings import run_compare
    from scripts.extract_features import run_extract

    run_extract(smoke_simulation, overwrite=True)
    summary = run_compare(smoke_simulation, overwrite=True)

    assert (reports_dir / smoke_simulation / "clusters_comparison.json").exists()
    assert (reports_dir / smoke_simulation / "clusters_comparison.md").exists()
    assert "agreement" in summary
    assert summary["signature"]["n_clusters"] >= 1
    assert summary["embedding"]["n_clusters"] >= 1


def test_embedding_global_scope_single_bucket():
    sims = [
        SimulationFeatures(
            simulation_id=f"s{i}",
            task_id=f"t{i}",
            trial=0,
            reward=0.0,
            failure_type=FailureType.DB_ONLY,
            termination_reason="user_stop",
            normalized_tool_chain=["get_order_details", "cancel_pending_order"],
            write_tool_sequence=["cancel_pending_order"],
            db_diff_signature="wrong:orders.*.cancel_reason",
            policy_flags=PolicyFlags(single_tool_per_turn=True, num_env_errors=0),
            num_steps=3,
            embedding_text="",
        )
        for i in range(3)
    ]
    art = cluster_embeddings(sims, "r", embedder=get_embedder("tfidf"), scope="global")
    # identical docs -> should collapse to a single cluster
    assert art.method == "embedding"
    assert len(art.clusters) == 1
    assert art.clusters[0].count == 3


def test_oracle_build(smoke_simulation, tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr("lib.paths.REPORTS_DIR", reports_dir)
    monkeypatch.setenv("HARNESS_OPT_REPORTS_DIR", str(reports_dir))

    from scripts.build_subset import run_build_oracle
    from scripts.cluster import run_cluster
    from scripts.extract_features import run_extract
    from scripts.generate_report import run_report
    from scripts.label_clusters import run_label

    run_extract(smoke_simulation, overwrite=True)
    run_cluster(smoke_simulation, overwrite=True)
    run_label(smoke_simulation, mock=True, overwrite=True)
    run_report(smoke_simulation, overwrite=True)
    run_build_oracle(smoke_simulation, overwrite=True)

    oracle_path = reports_dir / smoke_simulation / "oracle.json"
    assert oracle_path.exists()
    oracle = json.loads(oracle_path.read_text())
    assert oracle["mode"] == "oracle"
    assert len(oracle["task_ids"]) >= 1
