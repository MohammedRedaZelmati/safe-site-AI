import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd


os.environ.setdefault("GX_ANALYTICS_ENABLED", "false")
ALLOWED_TYPES = ["NO_HELMET", "NO_VEST", "NO_MASK"]
REQUIRED_COLUMNS = [
    "id",
    "occurred_at",
    "camera_id",
    "track_id",
    "violation_type",
    "confidence",
    "frame_uri",
    "event_key",
    "created_at",
]


def fetch_events(api_url: str, limit: int) -> list[dict[str, Any]]:
    request = Request(
        f"{api_url.rstrip('/')}/violations?limit={limit}",
        headers={"Accept": "application/json"},
    )
    with urlopen(request, timeout=10) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, list):
        raise ValueError("Violation API did not return a JSON array")
    return value


def read_events(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("Violation export must be a JSON array")
    return value


def build_suite() -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name="safesite_violation_events")
    for column in REQUIRED_COLUMNS:
        suite.add_expectation(gxe.ExpectColumnToExist(column=column))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="id"))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="occurred_at"))
    suite.add_expectation(gxe.ExpectColumnValuesToMatchRegex(column="occurred_at", regex=r"^\d{4}-\d{2}-\d{2}T"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="camera_id"))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="camera_id", min_value=1, max_value=64))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="track_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(column="track_id", min_value=0, strict_min=False))
    suite.add_expectation(gxe.ExpectColumnValuesToBeInSet(column="violation_type", value_set=ALLOWED_TYPES))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(column="confidence", min_value=0.0, max_value=1.0))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="created_at"))
    suite.add_expectation(gxe.ExpectColumnValuesToMatchRegex(column="created_at", regex=r"^\d{4}-\d{2}-\d{2}T"))
    return suite


def validate_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    dataframe = pd.DataFrame(events)
    for column in REQUIRED_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = None
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="safesite_pandas")
    asset = data_source.add_dataframe_asset(name="violation_events")
    batch = asset.add_batch_definition_whole_dataframe(name="complete_export")
    suite = context.suites.add(build_suite())
    definition = context.validation_definitions.add(
        gx.ValidationDefinition(data=batch, suite=suite, name="safesite_violation_validation")
    )
    result = definition.run(batch_parameters={"dataframe": dataframe})
    failures = []
    checks = []
    for expectation_result in result.results:
        configuration = expectation_result.expectation_config
        check = {
            "expectation": configuration.type,
            "column": configuration.kwargs.get("column"),
            "success": bool(expectation_result.success),
        }
        checks.append(check)
        if not check["success"]:
            failures.append(check)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if result.success else "failed",
        "row_count": len(dataframe),
        "expectation_count": len(checks),
        "failed_expectation_count": len(failures),
        "checks": checks,
        "failures": failures,
        "suite": "safesite_violation_events",
        "framework": f"great_expectations_{gx.__version__}",
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate SafeSite violation events with Great Expectations.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--api-url")
    parser.add_argument("--limit", type=int, default=200, choices=range(1, 201), metavar="1-200")
    parser.add_argument("--output", type=Path, default=Path("data/monitoring/event-quality-report.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = read_events(args.input) if args.input else fetch_events(args.api_url, args.limit)
    report = validate_events(events)
    write_json_atomic(args.output, report)
    print(json.dumps(report, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
