#!/usr/bin/env bash
# Launch Airflow locally (no Docker) to see and run the electronics_catalog_etl DAG.
#
# First run installs everything into airflow/.venv (a few minutes). Subsequent
# runs are instant. The UI comes up at http://localhost:8080 — the generated
# admin password is printed once and also saved to airflow/.airflow/.
#
#   bash airflow/run-local.sh        # start the UI + scheduler
#
# Both .venv and .airflow are gitignored. The real production refresh still runs
# via GitHub Actions cron; this is the orchestration demo.
set -euo pipefail

AF_VERSION="2.9.3"
PY_BIN="python3.11"                                  # Airflow 2.9.3 needs Python <=3.11

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" # the airflow/ dir
REPO_ROOT="$(cd "$HERE/.." && pwd)"
VENV="$HERE/.venv"

export AIRFLOW_HOME="$HERE/.airflow"
export PROJECT_ROOT="$REPO_ROOT"                     # so the `etl` package imports
export AIRFLOW__CORE__DAGS_FOLDER="$HERE/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False

# macOS only: gunicorn forks workers that crash (SIGSEGV) when system libs are
# touched after fork. These two env vars are the standard fix.
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export no_proxy="*"

# --- one-time setup -------------------------------------------------------
if [ ! -d "$VENV" ]; then
  echo ">> Creating Airflow virtualenv at $VENV"
  "$PY_BIN" -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip

  PYV="$("$VENV/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  CONSTRAINTS="https://raw.githubusercontent.com/apache/airflow/constraints-${AF_VERSION}/constraints-${PYV}.txt"

  echo ">> Installing apache-airflow==$AF_VERSION (constraints: $CONSTRAINTS)"
  "$VENV/bin/pip" install "apache-airflow==${AF_VERSION}" --constraint "$CONSTRAINTS"

  # macOS fix: setproctitle 1.3.x crashes gunicorn webserver workers with SIGSEGV
  # on fork — it calls a fork-unsafe CoreFoundation/LaunchServices API. 1.2.2
  # uses plain argv rewriting (no CoreFoundation), so the workers survive and
  # Airflow's worker-readiness monitor still sees their titles. Harmless on Linux.
  echo ">> Pinning setproctitle==1.2.2 (macOS gunicorn fork-safety)"
  "$VENV/bin/pip" install "setproctitle==1.2.2"

  # The DAG only imports the etl package, which needs just these three (not the
  # full app stack — streamlit/torch/chromadb would bloat the env and clash with
  # Airflow's pins). Versions match requirements-dev.txt.
  echo ">> Installing etl deps inside the DAG env"
  "$VENV/bin/pip" install "pandas==2.3.3" "beautifulsoup4==4.12.3" "requests==2.32.5"
fi

# --- launch ---------------------------------------------------------------
# `airflow standalone` spawns the webserver and scheduler as child processes
# that call `airflow` from PATH, so the venv's bin must be on PATH (not just the
# absolute path to the binary).
export PATH="$VENV/bin:$PATH"
echo ">> AIRFLOW_HOME=$AIRFLOW_HOME"
echo ">> Starting Airflow — UI at http://localhost:8080 (Ctrl-C to stop)"
exec airflow standalone
