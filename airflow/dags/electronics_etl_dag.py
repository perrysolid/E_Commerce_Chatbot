"""Airflow DAG: refresh the electronics catalog.

A deliberately thin orchestration layer. All the real work lives in the
framework-agnostic ``etl`` package, so the pipeline is testable and runs without
Airflow too — Airflow just schedules it and gives a visual task graph.

    scrape_flipkart  ->  build_catalog

The project root is mounted at /opt/airflow/project (see docker-compose).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_ROOT = "/opt/airflow/project"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _scrape():
    from etl.scrape import scrape
    scrape(pages=20)


def _build_catalog():
    from etl.pipeline import run_etl
    run_etl()


default_args = {
    "owner": "data",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="electronics_catalog_etl",
    description="Scrape Flipkart electronics and load the catalog into SQLite",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["etl", "electronics"],
) as dag:
    scrape_flipkart = PythonOperator(task_id="scrape_flipkart", python_callable=_scrape)
    build_catalog = PythonOperator(task_id="build_catalog", python_callable=_build_catalog)

    scrape_flipkart >> build_catalog
