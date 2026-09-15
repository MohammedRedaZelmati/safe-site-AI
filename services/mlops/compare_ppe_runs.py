import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import mlflow
from mlflow import MlflowClient


def tracking_uri(database: Path) -> str:
    return f"sqlite:///{database.resolve().as_posix()}"


def read_summary(training_dir: Path) -> dict[str, Any]:
    path = training_dir / "safesite-run.json"
    if not path.is_file():
        raise FileNotFoundError(f"Training summary not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("metrics"), dict):
        raise ValueError(f"Invalid SafeSite training summary: {path}")
    return value


def find_run(client: MlflowClient, experiment_id: str, run_name: str):
    escaped = run_name.replace("'", "\\'")
    runs = client.search_runs(
        [experiment_id],
        filter_string=f"attributes.run_name = '{escaped}' AND attributes.status = 'FINISHED'",
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    return runs[0] if runs else None


def metric_name(raw_name: str) -> str:
    normalized = raw_name.replace("/", "_")
    return re.sub(r"[^A-Za-z0-9_. -]", "_", normalized)


def log_summary_run(
    experiment_id: str,
    training_dir: Path,
    summary: dict[str, Any],
) -> str:
    run_name = training_dir.name
    with mlflow.start_run(experiment_id=experiment_id, run_name=run_name) as active_run:
        parameters = {
            "epochs": summary.get("epochs"),
            "image_size": summary.get("image_size"),
            "batch_size": summary.get("batch_size"),
            "device": summary.get("device"),
            "workers": summary.get("workers"),
            "seed": summary.get("seed"),
            "fraction": summary.get("fraction"),
            "torch_version": summary.get("torch_version"),
            "cuda_available": summary.get("cuda_available"),
        }
        mlflow.log_params({key: value for key, value in parameters.items() if value is not None})
        mlflow.log_metrics({metric_name(key): float(value) for key, value in summary["metrics"].items()})
        for name in ("safesite-run.json", "results.csv", "results.png", "confusion_matrix.png"):
            artifact = training_dir / name
            if artifact.is_file():
                mlflow.log_artifact(artifact, artifact_path="training")
        mlflow.set_tags(
            {
                "safesite.run_kind": "training_comparison",
                "safesite.readiness": "experimental",
            }
        )
        return active_run.info.run_id


def comparison_row(training_dir: Path, summary: dict[str, Any], run_id: str) -> dict[str, Any]:
    metrics = summary["metrics"]
    return {
        "run_name": training_dir.name,
        "run_id": run_id,
        "epochs": summary.get("epochs"),
        "fraction": summary.get("fraction"),
        "precision": metrics.get("metrics/precision(B)"),
        "recall": metrics.get("metrics/recall(B)"),
        "map50": metrics.get("metrics/mAP50(B)"),
        "map50_95": metrics.get("metrics/mAP50-95(B)"),
    }


def rank_runs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("map50_95") or 0.0),
            float(row.get("recall") or 0.0),
            float(row.get("precision") or 0.0),
        ),
        reverse=True,
    )


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log and compare existing SafeSite PPE training runs.")
    parser.add_argument("training_dirs", type=Path, nargs="+")
    parser.add_argument("--database", type=Path, default=Path("data/mlflow/mlflow.db"))
    parser.add_argument("--artifact-root", type=Path, default=Path("data/mlflow/artifacts"))
    parser.add_argument("--experiment-name", default="SafeSite-PPE-Experiments")
    parser.add_argument("--output", type=Path, default=Path("data/mlflow/run-comparison.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking_uri(args.database))
    client = MlflowClient()
    experiment = client.get_experiment_by_name(args.experiment_name)
    if experiment is None:
        experiment_id = client.create_experiment(
            args.experiment_name,
            artifact_location=args.artifact_root.resolve().as_uri(),
        )
    else:
        experiment_id = experiment.experiment_id

    rows = []
    for directory in args.training_dirs:
        summary = read_summary(directory)
        existing = find_run(client, experiment_id, directory.name)
        run_id = existing.info.run_id if existing else log_summary_run(experiment_id, directory, summary)
        rows.append(comparison_row(directory, summary, run_id))

    ranking = rank_runs(rows)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_name": args.experiment_name,
        "compared_run_count": len(ranking),
        "ranking": ranking,
        "selected_run": ranking[0]["run_name"],
        "selection_rule": "Highest mAP50-95, then recall, then precision",
        "decision": "Selected only as the experimental candidate; production promotion still requires strong violation-class recall and new construction-site evaluation.",
    }
    write_json_atomic(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
