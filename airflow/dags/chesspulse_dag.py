from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import sys
import os

# Ajouter le dossier ingestion au path
sys.path.insert(0, '/opt/airflow/ingestion')

# Arguments par défaut pour toutes les tâches
default_args = {
    'owner'           : 'chesspulse',
    'retries'         : 2,
    'retry_delay'     : timedelta(minutes=5),
    'email_on_failure': False,
}

# Définition du DAG
with DAG(
    dag_id            = 'chesspulse_pipeline',
    description       = 'Pipeline ChessPulse : ingestion Chess.com + dbt',
    default_args      = default_args,
    start_date        = datetime(2026, 1, 1),
    schedule_interval = '@daily',
    catchup           = False,
    tags              = ['chesspulse', 'chess', 'mlops'],
) as dag:

    # ─────────────────────────────────────────
    # Tâche 1 — Ingestion Chess.com → PostgreSQL
    # ─────────────────────────────────────────
    def task_ingestion():
        """
        Récupère les nouvelles parties Chess.com
        et les insère dans PostgreSQL.
        """
        from load_to_postgres import run_pipeline
        nouvelles = run_pipeline()
        print(f"✅ Pipeline terminé — {nouvelles} nouvelles parties insérées")

    ingestion = PythonOperator(
        task_id         = 'ingestion_chess_com',
        python_callable = task_ingestion,
    )

    # ─────────────────────────────────────────
    # Tâche 2 — Quality checks (Great Expectations)
    # ─────────────────────────────────────────
    def task_quality_checks():
        """
        Vérifie la qualité des données dans raw.games
        avant de lancer les transformations dbt.
        """
        from quality_checks import run_quality_checks
        success = run_quality_checks()
        if not success:
            raise ValueError("❌ Les vérifications de qualité ont échoué")
        print("✅ Toutes les vérifications de qualité sont passées")

    quality_checks = PythonOperator(
        task_id         = 'quality_checks',
        python_callable = task_quality_checks,
    )

    # ─────────────────────────────────────────
    # Tâche 3 — dbt run (transformations)
    # ─────────────────────────────────────────
    dbt_run = BashOperator(
        task_id         = 'dbt_run',
        bash_command    = 'cd /opt/airflow && dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt',
    )

    # ─────────────────────────────────────────
    # Tâche 4 — dbt test (qualité des données)
    # ─────────────────────────────────────────
    dbt_test = BashOperator(
        task_id         = 'dbt_test',
        bash_command    = 'cd /opt/airflow && dbt test --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt',
    )

    # ─────────────────────────────────────────
    # Ordre d'exécution des tâches
    # ─────────────────────────────────────────
    ingestion >> quality_checks >> dbt_run >> dbt_test