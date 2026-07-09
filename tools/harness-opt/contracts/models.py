"""Pydantic models mirroring docs/phases/contracts/*.schema.json."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

CONTRACT_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FailureType(str, Enum):
    PASS = "pass"
    DB_ONLY = "db_only"
    NL_ONLY = "nl_only"
    MIXED = "mixed"  # DB + NL_ASSERTION both failed (retail)
    COMMUNICATE_ONLY = "communicate_only"  # non-retail domains where COMMUNICATE gates
    TERMINATION = "termination"


class ToolCallRecord(BaseModel):
    name: str
    turn: int
    error: bool = False


class PolicyFlags(BaseModel):
    auth_before_mutate: Optional[bool] = None
    confirm_before_write: Optional[bool] = None
    single_tool_per_turn: bool = True
    num_env_errors: int = 0


class SimulationFeatures(BaseModel):
    simulation_id: str
    task_id: str
    trial: int
    reward: float
    failure_type: FailureType
    termination_reason: Optional[str] = None
    db_reward: Optional[float] = None
    nl_reward: Optional[float] = None
    communicate_reward: Optional[float] = None
    tool_sequence: list[ToolCallRecord] = Field(default_factory=list)
    # P2: normalized tool signals (names only, no args)
    normalized_tool_chain: list[str] = Field(default_factory=list)
    write_tool_sequence: list[str] = Field(default_factory=list)
    # P1: structured DB divergence (gold vs predicted env replay)
    db_diff_signature: Optional[str] = None
    db_diff_kinds: Optional[dict[str, int]] = None
    db_diff_entities: list[str] = Field(default_factory=list)
    # P3: denoised NL-assertion failure signal
    nl_failure_signature: Optional[str] = None
    nl_failed_assertions: list[str] = Field(default_factory=list)
    # Root-cause "why" signals (enrichment for embedding documents)
    escalated_to_human: bool = False
    last_agent_message: Optional[str] = None
    tool_error_messages: list[str] = Field(default_factory=list)
    # Primary axis: deterministic root-cause mechanism (see classify_mechanism).
    # failure_type (db_only/nl_only/mixed) is kept as a secondary reward-basis
    # attribute; mechanism_class is the actionable cause axis.
    mechanism_class: str = "unknown"
    policy_flags: PolicyFlags
    num_steps: int
    agent_cost: Optional[float] = None
    embedding_text: str


class FeaturesArtifact(BaseModel):
    contract_version: str = CONTRACT_VERSION
    run_name: str
    domain: str = "retail"
    simulations: list[SimulationFeatures]


class Cluster(BaseModel):
    id: str
    name: str
    failure_type: str
    parent_l0_id: Optional[str] = None
    simulation_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    failure_rate: float = 0.0
    count: int = 0
    mechanism: Optional[str] = None
    signature: Optional[str] = None
    tool_sequence_fingerprint: Optional[str] = None
    policy_flag_summary: Optional[dict[str, int]] = None


class ClustersArtifact(BaseModel):
    contract_version: str = CONTRACT_VERSION
    run_name: str
    layer: Literal["l0", "l1", "l2", "final"]
    method: str = "signature"
    clusters: list[Cluster]


class ClusterLabel(BaseModel):
    cluster_id: str
    display_name: str
    cohesion: float
    blame_tags: list[str]
    summary: str
    representative_simulation_ids: list[str] = Field(default_factory=list)


class ClusterLabelsArtifact(BaseModel):
    contract_version: str = CONTRACT_VERSION
    run_name: str
    model: Optional[str] = None
    labels: list[ClusterLabel]


class ManifestArtifact(BaseModel):
    contract_version: str = CONTRACT_VERSION
    run_name: str
    simulation_path: str
    baseline_run: Optional[str] = None
    git_sha: Optional[str] = None
    domain: str = "retail"
    num_simulations: int = 0
    num_trials: Optional[int] = None
    agent_llm: Optional[str] = None
    user_llm: Optional[str] = None
    created_at: str
    artifacts: dict[str, str] = Field(default_factory=dict)


class SubsetSpecArtifact(BaseModel):
    contract_version: str = CONTRACT_VERSION
    mode: Literal["oracle", "cluster", "proposal"]
    run_name: str = ""
    baseline_run: str = ""
    cluster_id: Optional[str] = None
    proposal_id: Optional[str] = None
    task_ids: list[str] = Field(default_factory=list)
    target_task_ids: list[str] = Field(default_factory=list)
    control_task_ids: list[str] = Field(default_factory=list)
    oracle_stable_pass_ids: list[str] = Field(default_factory=list)
    oracle_representative_fail_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now)


class TaskComparison(BaseModel):
    task_id: str
    role: Literal["target", "control", "oracle_stable", "oracle_fail"]
    baseline_reward: float
    candidate_reward: float
    delta: float = 0.0


class SubsetResultsArtifact(BaseModel):
    contract_version: str = CONTRACT_VERSION
    proposal_id: str
    baseline_run: str
    candidate_run: str
    subset_spec_path: Optional[str] = None
    tasks: list[TaskComparison] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    target_improvements: int = 0
    control_regressions: int = 0
    verdict: Literal["pass", "fail", "review"]
    recommendation: str
    created_at: str = Field(default_factory=_utc_now)


class ProposalMetadataArtifact(BaseModel):
    contract_version: str = CONTRACT_VERSION
    proposal_id: str
    cluster_id: str
    run_name: str
    branch_name: str  # proposal/<id> (ephemeral eval branch)
    example_task_ids: list[str]
    failure_mode_summary: Optional[str] = None
    status: Literal["draft", "evaluating", "evaluated", "accepted", "rejected"] = "draft"
    # Phase 2 lineage + coder tracking
    lineage_id: Optional[str] = None
    coder_backend: Optional[str] = None
    parent_commit: Optional[str] = None  # lineage tip the proposal forked from
    resulting_commit: Optional[str] = None  # lineage commit after accept (squashed)
    generation: Optional[int] = None
    diff_stat: Optional[str] = None
    eval_verdict: Optional[Literal["pass", "fail", "review"]] = None
    candidate_run: Optional[str] = None
    created_at: str = Field(default_factory=_utc_now)
    evaluated_at: Optional[str] = None


class LineageProposalRef(BaseModel):
    proposal_id: str
    cluster_id: str
    commit: Optional[str] = None
    summary: Optional[str] = None


class LineageArtifact(BaseModel):
    """State of one improvement-loop rollout: a durable lineage/<id> branch."""

    contract_version: str = CONTRACT_VERSION
    lineage_id: str
    branch: str  # lineage/<id>
    base_commit: str
    tip_commit: str
    generation: int = 0
    accepted_proposals: list[LineageProposalRef] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now)
    updated_at: str = Field(default_factory=_utc_now)


class LineageIndexArtifact(BaseModel):
    contract_version: str = CONTRACT_VERSION
    lineages: list[LineageArtifact] = Field(default_factory=list)
