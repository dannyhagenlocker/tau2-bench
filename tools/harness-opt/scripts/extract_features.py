"""Extract per-simulation features from a tau2 run."""

from __future__ import annotations

import argparse

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import FeaturesArtifact
from lib.io import load_simulation_path, write_json_artifact
from lib.trace_parser import extract_simulation_features

from tau2.data_model.simulation import Results


def _load_retail_context() -> tuple[dict, object]:
    """Load retail tasks (by id) and a base DB for offline DB-diff replay."""
    from tau2.domains.retail.data_model import RetailDB
    from tau2.domains.retail.environment import get_tasks
    from tau2.domains.retail.utils import RETAIL_DB_PATH

    tasks_by_id = {t.id: t for t in get_tasks(None)}
    base_db = RetailDB.load(RETAIL_DB_PATH)
    return tasks_by_id, base_db


def run_extract(
    run_name: str, *, domain: str = "retail", overwrite: bool = False
) -> str:
    path = load_simulation_path(run_name)
    results = Results.load(path)
    env_domain = results.info.environment_info.domain_name
    domain = env_domain or domain

    tasks_by_id: dict = {}
    base_db = None
    if domain == "retail":
        try:
            tasks_by_id, base_db = _load_retail_context()
        except Exception:
            tasks_by_id, base_db = {}, None

    simulations = [
        extract_simulation_features(
            sim,
            domain=domain,
            task=tasks_by_id.get(sim.task_id),
            base_db=base_db,
        )
        for sim in results.simulations
    ]
    artifact = FeaturesArtifact(
        run_name=run_name,
        domain=domain,
        simulations=simulations,
    )
    write_json_artifact(run_name, "features.json", artifact, overwrite=overwrite)
    return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract features from a simulation run"
    )
    parser.add_argument(
        "--run", required=True, help="Simulation run name (--save-to value)"
    )
    parser.add_argument("--domain", default="retail")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    out = run_extract(args.run, domain=args.domain, overwrite=args.overwrite)
    print(f"Wrote features.json for run {args.run} (source: {out})")


if __name__ == "__main__":
    main()
