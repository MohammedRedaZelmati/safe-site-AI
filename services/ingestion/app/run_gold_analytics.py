import argparse
import json
import sys
from pathlib import Path

from app.aggregate_gold import aggregate_gold
from app.validate_gold_quality import validate_quality


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate SafeSite Gold records and run the quality gate."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    aggregation = aggregate_gold(args.input_dir, args.output_dir, args.overwrite)
    quality = validate_quality(args.output_dir)
    result = {
        "status": "passed" if quality["status"] == "passed" else "failed",
        "aggregation": aggregation,
        "quality": {
            "status": quality["status"],
            "check_count": quality["check_count"],
            "failed_checks": quality["failed_checks"],
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
