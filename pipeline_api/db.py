import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()


def get_connexion():
    """
    Retourne une connexion PostgreSQL.
    Même logique que ingestion/db_utils.py,
    mais isolée ici pour que l'API n'ait aucune dépendance
    vers le module d'ingestion.
    """
    return psycopg2.connect(
        host     = os.getenv("POSTGRES_HOST"),
        port     = os.getenv("POSTGRES_PORT"),
        dbname   = os.getenv("POSTGRES_DB"),
        user     = os.getenv("POSTGRES_USER"),
        password = os.getenv("POSTGRES_PASSWORD")
    )