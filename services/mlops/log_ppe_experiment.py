import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import mlflow
from mlflow import MlflowClient


DATASET_ARCHIVE_SHA256 = (
    "bef8dcb599aa4e9d9f5e602cb6fa7143d3c84d7f6a0ff40463d7f2a4c2632ccc"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def require_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.stat().st_size == 0:
        raise FileNotFoundError(f"{label} is missing or empty: {resolved}")
    return resolved


def sqlite_tracking_uri(database_path: Path) -> str:
    return f"sqlite:///{database_path.resolve().as_posix()}"


def flatten_metrics(training: dict, evaluation: dict) -> dict[str, float]:
    metrics = {}
    for name, value in training.get("metrics", {}).items():
        safe_name = name.replace("metrics/", "").replace("mAP", "map").replace(
            "(B)", ""
        )
        metrics[f"training_{safe_name}"] = float(value)

    for name, value in evaluation.get("overall", {}).items():
        safe_name = name.replace("metrics/", "").replace("mAP", "map").replace(
            "(B)", ""
        )
        metrics[f"evaluation_{safe_name}"] = float(value)

    for class_metrics in evaluation.get("per_class", []):
        class_name = str(class_metrics["class_name"]).lower()
        for metric_name in ("precision", "recall", "mAP50", "mAP50_95"):
            safe_metric = metric_name.replace("mAP", "map")
            metrics[f"class_{class_name}_{safe_metric}"] = float(
                class_metrics[metric_name]
            )
    return metrics


def write_json_atomic(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)


def find_registered_version(
    client: MlflowClient, model_name: str, run_id: str
) -> str:
    versions = client.search_model_versions(f"name='{model_name}'")
    matching = [version for version in versions if version.run_id == run_id]
    if not matching:
        raise RuntimeError(
            f"No registered {model_name} version belongs to MLflow run {run_id}"
        )
    return str(max(matching, key=lambda version: int(version.version)).version)


def log_experiment(args: argparse.Namespace) -> dict:
    training_dir = args.training_dir.resolve()
    run_summary_path = require_file(training_dir / "safesite-run.json", "run summary")
    evaluation_path = require_file(training_dir / "evaluation.json", "evaluation")
    weights_path = require_file(training_dir / "weights" / "best.pt", "best weights")
    dataset_config = require_file(args.dataset_config, "dataset config")
    dataset_audit = require_file(args.dataset_audit, "dataset audit")
    model_code = require_file(
        Path(__file__).with_name("safesite_yolo_pyfunc.py"), "model code"
    )
    output_summary = args.output_summary.resolve()
    if output_summary.exists() and not args.overwrite_summary:
        raise FileExistsError(
            f"Output summary already exists; use --overwrite-summary: {output_summary}"
        )

    training = load_json(run_summary_path)
    evaluation = load_json(evaluation_path)
    database_path = args.database.resolve()
    artifact_root = args.artifact_root.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    tracking_uri = sqlite_tracking_uri(database_path)
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    experiment = client.get_experiment_by_name(args.experiment_name)
    if experiment is None:
        experiment_id = client.create_experiment(
            args.experiment_name,
            artifact_location=artifact_root.as_uri(),
            tags={"project": "SafeSite AI", "task": "PPE detection"},
        )
    else:
        experiment_id = experiment.experiment_id

    weights_sha256 = sha256(weights_path)
    dataset_config_sha256 = sha256(dataset_config)
    metrics = flatten_metrics(training, evaluation)
    parameters = {
        "epochs": training["epochs"],
        "image_size": training["image_size"],
        "batch_size": training["batch_size"],
        "device": training["device"],
        "workers": training["workers"],
        "seed": training["seed"],
        "fraction": training["fraction"],
        "torch_version": training["torch_version"],
        "cuda_available": training["cuda_available"],
        "dataset_archive_sha256": DATASET_ARCHIVE_SHA256,
        "dataset_config_sha256": dataset_config_sha256,
        "weights_sha256": weights_sha256,
    }
    tags = {
        "project": "SafeSite AI",
        "task": "construction PPE detection",
        "model_family": "YOLO26n",
        "dataset": "Ultralytics Construction-PPE",
        "readiness": "experimental_not_production",
        "validation_decision": "candidate_only",
    }

    with mlflow.start_run(
        experiment_id=experiment_id,
        run_name=args.run_name,
        tags=tags,
    ) as active_run:
        run_id = active_run.info.run_id
        mlflow.log_params(parameters)
        mlflow.log_metrics(metrics)
        for filename in (
            "safesite-run.json",
            "evaluation.json",
            "results.csv",
            "args.yaml",
            "results.png",
            "confusion_matrix.png",
            "confusion_matrix_normalized.png",
        ):
            artifact = training_dir / filename
            if artifact.is_file() and artifact.stat().st_size > 0:
                mlflow.log_artifact(str(artifact), artifact_path="training")
        mlflow.log_artifact(str(dataset_config), artifact_path="dataset")
        mlflow.log_artifact(str(dataset_audit), artifact_path="dataset")

        model_info = mlflow.pyfunc.log_model(
            name="ppe_detector",
            python_model=str(model_code),
            artifacts={"weights": str(weights_path)},
            registered_model_name=args.model_name,
            await_registration_for=60,
            pip_requirements=[
                "mlflow==3.15.2",
                "ultralytics==8.4.107",
                "pandas>=2.2,<3",
            ],
            metadata={
                "project": "SafeSite AI",
                "weights_sha256": weights_sha256,
                "readiness": "experimental_not_production",
            },
        )

    version = find_registered_version(client, args.model_name, run_id)
    client.update_registered_model(
        name=args.model_name,
        description=(
            "SafeSite experimental Construction-PPE detector. Registry versions are "
            "not production-approved without stronger violation recall and field testing."
        ),
    )
    client.update_model_version(
        name=args.model_name,
        version=version,
        description=(
            "Ten-epoch CPU baseline packaged with its verified YOLO weights and "
            "evaluation artifacts."
        ),
    )
    client.set_model_version_tag(
        args.model_name, version, "validation_status", "experimental"
    )
    client.set_model_version_tag(
        args.model_name, version, "weights_sha256", weights_sha256
    )
    client.set_registered_model_alias(args.model_name, args.alias, version)

    result = {
        "status": "logged_and_registered",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracking_uri": tracking_uri,
        "database": str(database_path),
        "artifact_root": str(artifact_root),
        "experiment_name": args.experiment_name,
        "experiment_id": str(experiment_id),
        "run_name": args.run_name,
        "run_id": run_id,
        "logged_metric_count": len(metrics),
        "registered_model": args.model_name,
        "registered_version": version,
        "registered_alias": args.alias,
        "model_uri": f"models:/{args.model_name}@{args.alias}",
        "logged_model_uri": model_info.model_uri,
        "readiness": "experimental_not_production",
        "weights_sha256": weights_sha256,
        "dataset_archive_sha256": DATASET_ARCHIVE_SHA256,
        "dataset_config_sha256": dataset_config_sha256,
    }
    write_json_atomic(result, output_summary)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Log and register an existing SafeSite PPE training run in MLflow."
    )
    parser.add_argument("--training-dir", type=Path, required=True)
    parser.add_argument("--dataset-config", type=Path, required=True)
    parser.add_argument("--dataset-audit", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=Path("data/mlflow/mlflow.db"))
    parser.add_argument(
        "--artifact-root", type=Path, default=Path("data/mlflow/artifacts")
    )
    parser.add_argument(
        "--output-summary",
        type=Path,
        default=Path("data/mlflow/block29-proof.json"),
    )
    parser.add_argument("--experiment-name", default="SafeSite-PPE-Experiments")
    parser.add_argument("--run-name", default="ppe-baseline-e10-full-img320")
    parser.add_argument("--model-name", default="SafeSite-PPE-Detector")
    parser.add_argument("--alias", default="candidate")
    parser.add_argument("--overwrite-summary", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = log_experiment(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
