# Airflow orchestration

The `electronics_catalog_etl` DAG schedules the same `etl` pipeline used
everywhere else (`scrape_flipkart → build_catalog`, `@daily`). It's the
"how I'd orchestrate this on a team" artifact. In production the daily run
actually happens via a GitHub Actions cron (no always-on server needed) — see
`.github/workflows/refresh-data.yml`.

## Run locally (no Docker)

```bash
bash run-local.sh         # from the airflow/ dir
```

First run creates `airflow/.venv` (Airflow 2.9.3 + the libs the `etl` package
needs) and starts everything; later runs are instant. The UI comes up at
http://localhost:8080 and the admin password is printed once (also saved to
`airflow/.airflow/standalone_admin_password.txt`). Both `.venv` and `.airflow`
are gitignored.

Then enable the `electronics_catalog_etl` DAG in the UI and hit ▶, or trigger it:

```bash
airflow dags trigger electronics_catalog_etl
```

The script sets `PROJECT_ROOT` (so `etl` imports), disables example DAGs, and
applies two macOS fixes: it puts the venv on `PATH` (Airflow spawns child
processes that call `airflow`) and pins `setproctitle==1.2.2` — the 1.3.x
release crashes the webserver's forked gunicorn workers with SIGSEGV because it
calls a fork-unsafe CoreFoundation API.
