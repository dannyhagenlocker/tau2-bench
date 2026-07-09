"""Build smoke fixture by running: uv run python tools/harness-opt/fixtures/build_smoke_fixture.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from tau2.data_model.message import AssistantMessage, ToolCall, ToolMessage, UserMessage
from tau2.data_model.simulation import (
    AgentInfo,
    DBCheck,
    EnvironmentInfo,
    Info,
    NLAssertionCheck,
    Results,
    RewardInfo,
    SimulationRun,
    UserInfo,
)
from tau2.data_model.tasks import RewardType
from tau2.utils.utils import get_now

OUT = Path(__file__).parent / "smoke_results.json"


def _sim(
    sim_id: str,
    task_id: str,
    trial: int,
    reward: float,
    db: float,
    nl: float,
    messages: list,
    termination: str = "user_stop",
    nl_checks: list[NLAssertionCheck] | None = None,
) -> SimulationRun:
    ri = RewardInfo(
        reward=reward,
        reward_basis=[RewardType.DB, RewardType.NL_ASSERTION],
        reward_breakdown={RewardType.DB: db, RewardType.NL_ASSERTION: nl},
        db_check=DBCheck(db_match=db >= 0.999, db_reward=db),
        nl_assertions=nl_checks,
    )
    return SimulationRun(
        id=sim_id,
        task_id=task_id,
        trial=trial,
        start_time=get_now(),
        end_time=get_now(),
        duration=10.0,
        termination_reason=termination,
        agent_cost=0.01,
        user_cost=0.005,
        reward_info=ri,
        messages=messages,
        mode="half_duplex",
    )


def main() -> None:
    # Pass
    pass_msgs = [
        AssistantMessage(role="assistant", content="Hi! How can I help?"),
        UserMessage(role="user", content="I need help with order 123"),
        AssistantMessage(
            role="assistant",
            tool_calls=[
                ToolCall(
                    id="t1",
                    name="find_user_id_by_email",
                    arguments={"email": "a@b.com"},
                )
            ],
        ),
        ToolMessage(role="tool", id="t1", content="user_1", requestor="assistant"),
    ]
    # DB fail — write without auth
    db_fail_msgs = [
        AssistantMessage(role="assistant", content="Hi!"),
        UserMessage(role="user", content="Cancel order W123"),
        AssistantMessage(
            role="assistant",
            tool_calls=[
                ToolCall(
                    id="t2", name="cancel_pending_order", arguments={"order_id": "W1"}
                )
            ],
        ),
        ToolMessage(role="tool", id="t2", content="ok", requestor="assistant"),
    ]
    # NL fail only
    nl_fail_msgs = pass_msgs + [
        AssistantMessage(role="assistant", content="Done."),
    ]
    nl_fail_checks = [
        NLAssertionCheck(
            nl_assertion="Agent apologized for the delay",
            met=False,
            justification="No apology given",
        )
    ]

    sims = [
        _sim("s1", "task_0", 0, 1.0, 1.0, 1.0, pass_msgs),
        _sim("s2", "task_1", 0, 0.0, 0.0, 1.0, db_fail_msgs),
        _sim("s3", "task_2", 0, 0.0, 1.0, 0.0, nl_fail_msgs, nl_checks=nl_fail_checks),
        _sim("s4", "task_3", 0, 0.0, 0.0, 0.0, db_fail_msgs, nl_checks=nl_fail_checks),
    ]

    info = Info(
        git_commit="smoke",
        num_trials=1,
        max_steps=100,
        max_errors=10,
        agent_info=AgentInfo(implementation="llm_agent", llm="gpt-5.5"),
        user_info=UserInfo(implementation="user_simulator", llm="gpt-5.5"),
        environment_info=EnvironmentInfo(domain_name="retail", policy="smoke"),
    )
    results = Results(timestamp=get_now(), info=info, tasks=[], simulations=sims)
    OUT.write_text(results.model_dump_json(indent=2))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
