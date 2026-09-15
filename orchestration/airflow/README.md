# SafeSite Gold Airflow DAG

`dags/safesite_gold_daily.py` describes the daily analytics workflow:

1. Read tracking-worker Gold JSON records.
2. Build compressed Parquet tables.
3. Run the data-quality gate.
4. Stop the workflow if quality checks fail.

## Runtime contract

The Airflow worker must provide:

- the SafeSite ingestion Python environment, including `pyarrow`;
- this repository's `services/ingestion/app` package on `PYTHONPATH`;
- a shared `/data` mount containing the Gold records and analytics output;
- `SAFESITE_GOLD_RECORDS_DIR` and `SAFESITE_GOLD_PARQUET_DIR` when the default paths are not used.

The DAG runs once per day, does not replay historical dates, and allows only one active run. The local path is exposed through the lighter `gold-analytics` Compose service rather than a full Airflow server. The same Python modules can also be run directly to test the task logic before the DAG is deployed.
