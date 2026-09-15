import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
LONG_RUNNING_SERVICES = {
    "agent",
    "airflow",
    "api",
    "camera-ingestion-worker",
    "candidate-api-worker",
    "dashboard",
    "kafka",
    "minio",
    "mlflow",
    "postgres",
    "ppe-inference-worker",
    "stream-monitor",
    "tracking-worker",
}
COMPOSE_PROFILES = ("agent", "mlops", "orchestration", "streaming", "ui")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def check(name: str, condition: bool, evidence: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if condition else "failed",
        "evidence": evidence,
    }


def mlflow_finished_runs(database: Path) -> int:
    with sqlite3.connect(database) as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM runs WHERE status = 'FINISHED'"
            ).fetchone()[0]
        )


def docker_runtime_status() -> dict[str, Any]:
    candidates = [
        shutil.which("docker"),
        str(Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe")),
        str(
            Path.home()
            / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
        ),
    ]
    executable = next(
        (candidate for candidate in candidates if candidate and Path(candidate).is_file()),
        None,
    )
    if executable is None:
        return {
            "docker_cli_available": False,
            "docker_engine_available": False,
            "docker_executable": None,
            "engine_check": "Docker CLI was not found.",
        }
    try:
        result = subprocess.run(
            [executable, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {
            "docker_cli_available": True,
            "docker_engine_available": False,
            "docker_executable": executable,
            "engine_check": "docker info timed out after 10 seconds.",
        }
    message = (result.stdout or result.stderr).strip() or (
        f"docker info exited with code {result.returncode} and no diagnostic text."
    )
    return {
        "docker_cli_available": True,
        "docker_engine_available": result.returncode == 0,
        "docker_executable": executable,
        "engine_check": message,
    }


def compose_runtime_status(executable: str | None) -> dict[str, Any]:
    if executable is None:
        return {
            "all_required_services_running": False,
            "running_services": [],
            "missing_services": sorted(LONG_RUNNING_SERVICES),
            "diagnostic": "Docker CLI was not found.",
        }
    command = [executable, "compose"]
    for profile in COMPOSE_PROFILES:
        command.extend(["--profile", profile])
    command.extend(["ps", "--services", "--filter", "status=running"])
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return {
            "all_required_services_running": False,
            "running_services": [],
            "missing_services": sorted(LONG_RUNNING_SERVICES),
            "diagnostic": "docker compose ps timed out after 20 seconds.",
        }
    running_services = {
        line.strip() for line in result.stdout.splitlines() if line.strip()
    }
    missing_services = LONG_RUNNING_SERVICES - running_services
    diagnostic = (result.stderr or "").strip()
    if result.returncode != 0 and not diagnostic:
        diagnostic = f"docker compose ps exited with code {result.returncode}."
    return {
        "all_required_services_running": result.returncode == 0 and not missing_services,
        "running_services": sorted(running_services),
        "missing_services": sorted(missing_services),
        "diagnostic": diagnostic,
    }


def build_report(full_compose_replay: bool = False) -> dict[str, Any]:
    stream = read_json(ROOT / "data/streaming/demo-lesson21-20260821/run-summary.json")
    mvp_publish = read_json(ROOT / "data/demo/mvp-20260815-223655/publish-send/summary.json")
    gold = read_json(ROOT / "data/lake/gold/block28-proof/quality-report.json")
    quality = read_json(ROOT / "data/monitoring/event-quality-report.json")
    drift = read_json(ROOT / "data/monitoring/drift-report.json")
    mlflow_proof = read_json(ROOT / "data/mlflow/block29-proof.json")
    comparison = read_json(ROOT / "data/mlflow/run-comparison.json")
    agent = read_json(ROOT / "data/agent/block31-database-proof.json")
    vision = read_json(ROOT / "data/agent/block31-vision-proof.json")
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = set(compose["services"])
    required_services = {
        "kafka",
        "minio",
        "postgres",
        "api",
        "ingestion",
        "ppe-inference-worker",
        "tracking-worker",
        "camera-ingestion-worker",
        "candidate-api-worker",
        "stream-monitor",
        "gold-analytics",
        "agent",
        "dashboard",
        "mlflow",
        "drift-monitor",
        "event-quality",
        "airflow",
    }
    airflow_dag = (ROOT / "orchestration/airflow/dags/safesite_gold_daily.py").read_text(
        encoding="utf-8"
    )
    dashboard = (ROOT / "services/dashboard/app.py").read_text(encoding="utf-8")

    checks = [
        check(
            "video_ingestion_kafka_minio",
            stream["status"] == "completed"
            and stream["topic_message_counts"]["raw"] == 30,
            {
                "run_id": stream["run_id"],
                "raw_messages": stream["topic_message_counts"]["raw"],
                "bronze_stage": stream["stages"]["bronze_publication"],
            },
        ),
        check(
            "cv_inference_tracking",
            stream["topic_message_counts"]["ppe"] == 30
            and stream["topic_message_counts"]["tracks"] == 30
            and stream["measurements"]["ppe_frames_processed"] == 30
            and stream["measurements"]["tracking_frames_processed"] == 30,
            stream["measurements"],
        ),
        check(
            "fastapi_postgresql_idempotent_delivery",
            stream["api_health"]["status"] == "healthy"
            and mvp_publish["status_counts"].get("published") == 2,
            {
                "api_health": stream["api_health"],
                "publish_statuses": mvp_publish["status_counts"],
            },
        ),
        check(
            "gold_parquet_quality",
            gold["status"] == "passed"
            and gold["check_count"] == 12
            and gold["failed_check_count"] == 0,
            {"rows": gold["row_counts"], "checks": gold["check_count"]},
        ),
        check(
            "great_expectations_event_quality",
            quality["status"] == "passed"
            and quality["expectation_count"] == 21
            and quality["failed_expectation_count"] == 0,
            {
                "rows": quality["row_count"],
                "expectations": quality["expectation_count"],
            },
        ),
        check(
            "distribution_drift",
            drift["minimum_confidence"] == 0.25
            and set(drift["comparisons"]) == {"brightness", "sharpness", "confidence"},
            {
                name: value["psi"]
                for name, value in drift["comparisons"].items()
            },
        ),
        check(
            "mlflow_tracking_registry_comparison",
            mlflow_proof["registered_alias"] == "candidate"
            and comparison["compared_run_count"] == 2
            and mlflow_finished_runs(ROOT / "data/mlflow/mlflow.db") >= 2,
            {
                "registered_model": mlflow_proof["registered_model"],
                "version": mlflow_proof["registered_version"],
                "alias": mlflow_proof["registered_alias"],
                "selected_run": comparison["selected_run"],
                "compared_runs": comparison["compared_run_count"],
            },
        ),
        check(
            "airflow_orchestration",
            "aggregate_gold" in airflow_dag
            and "validate_gold" in airflow_dag
            and "aggregate_gold >> validate_gold" in airflow_dag,
            "Daily aggregation precedes validation in safesite_gold_daily.py",
        ),
        check(
            "grounded_agent_read_only",
            agent["status"] == "passed"
            and agent["postgres"]["write_rejected"]
            and agent["agent"]["answer_provider"] == "ollama"
            and agent["agent"]["rejected_http_status"] == 422,
            {
                "role_query": agent["postgres"]["role_query"],
                "write_error": agent["postgres"]["write_error"],
                "sql": agent["agent"]["sql"],
                "answer": agent["agent"]["answer"],
            },
        ),
        check(
            "vision_language_evidence",
            vision["status"] == "passed"
            and vision["model"] == "qwen2.5vl:3b"
            and bool(vision["description"]),
            {
                "model": vision["model"],
                "elapsed_seconds": vision["elapsed_seconds"],
                "description": vision["description"],
            },
        ),
        check(
            "streamlit_observability_and_agent_ui",
            all(
                phrase in dashboard
                for phrase in (
                    "Safety decision",
                    "Visual evidence",
                    "Recorded violations to review",
                    "VISUAL PROOF IS NOT AVAILABLE",
                    "Technical system details",
                    "SafeSite assistant",
                )
            ),
            "Dashboard leads with a safety decision and honest evidence status while retaining optional technical and agent panels",
        ),
        check(
            "compose_and_one_command_launcher",
            required_services.issubset(services)
            and (ROOT / "scripts/run_final_architecture.ps1").is_file(),
            {
                "service_count": len(services),
                "required_services": sorted(required_services),
                "launcher": "scripts/run_final_architecture.ps1",
            },
        ),
    ]
    docker_status = docker_runtime_status()
    compose_status = (
        compose_runtime_status(docker_status.get("docker_executable"))
        if full_compose_replay
        else None
    )
    if compose_status is not None:
        compose_check = next(
            item for item in checks if item["name"] == "compose_and_one_command_launcher"
        )
        compose_check["evidence"]["runtime"] = compose_status
        if not compose_status["all_required_services_running"]:
            compose_check["status"] = "failed"
    failed = [item["name"] for item in checks if item["status"] != "passed"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if not failed else "failed",
        "check_count": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "runtime_boundary": {
            **docker_status,
            "full_compose_replay_performed_this_session": full_compose_replay,
            "compose_runtime": compose_status,
            "component_proof_strategy": (
                "Current full Compose replay with live-service verification plus saved component evidence"
                if full_compose_replay
                else "Saved component evidence without a full Compose replay in this session"
            ),
        },
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify evidence for every SafeSite architecture layer.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/final/final-architecture-proof.json",
    )
    parser.add_argument(
        "--full-compose-replay",
        action="store_true",
        help="Record that the complete Compose launcher succeeded in this session.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(full_compose_replay=args.full_compose_replay)
    write_json_atomic(args.output, report)
    print(json.dumps(report, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
