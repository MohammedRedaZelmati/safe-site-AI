import os
from datetime import datetime, timezone

from airflow import DAG

try:
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:
    from airflow.operators.bash import BashOperator


GOLD_RECORDS_DIR = os.environ.get(
    "SAFESITE_GOLD_RECORDS_DIR", "/data/workers/tracking/records"
)
GOLD_PARQUET_DIR = os.environ.get(
    "SAFESITE_GOLD_PARQUET_DIR", "/data/lake/gold/parquet"
)


with DAG(
    dag_id="safesite_gold_daily",
    description="Build and validate SafeSite Gold Parquet analytics tables.",
    schedule="@daily",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["safesite", "gold", "quality"],
) as dag:
    aggregate_gold = BashOperator(
        task_id="aggregate_gold_parquet",
        bash_command=(
            "python -m app.aggregate_gold "
            f"--input-dir '{GOLD_RECORDS_DIR}' "
            f"--output-dir '{GOLD_PARQUET_DIR}' --overwrite"
        ),
    )

    validate_gold = BashOperator(
        task_id="validate_gold_quality",
        bash_command=(
            "python -m app.validate_gold_quality "
            f"--output-dir '{GOLD_PARQUET_DIR}'"
        ),
    )

    aggregate_gold >> validate_gold
