# Airflow orchestration

The `electronics_catalog_etl` DAG schedules the same `etl` pipeline used
everywhere else (`scrape_flipkart → build_catalog`, `@daily`). It's the
"how I'd orchestrate this on a team" artifact. In production the daily run
actually happens via a GitHub Actions cron (no always-on server needed) — see
`.github/workflows/refresh-data.yml`.

## Run locally (no Docker)

```bash
pip install "apache-airflow==2.9.3"

export AIRFLOW_HOME="$(pwd)/.airflow"
export PROJECT_ROOT="$(cd .. && pwd)"          # repo root, so `etl` is importable
export AIRFLOW__CORE__DAGS_FOLDER="$(pwd)/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False

airflow standalone        # UI at http://localhost:8080 (admin creds printed once)
```

Then enable the `electronics_catalog_etl` DAG in the UI, or trigger it:

```bash
airflow dags trigger electronics_catalog_etl
```
