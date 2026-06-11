FROM apache/airflow:2.8.0

USER root

RUN apt-get update && apt-get install -y git

USER airflow

RUN pip install --no-cache-dir \
    dbt-core==1.5.0 \
    dbt-postgres==1.5.0 \
    psycopg2-binary \
    python-dotenv \
    requests \
    python-chess