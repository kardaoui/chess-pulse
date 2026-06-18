import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()


def get_connexion():
    """
    Retourne une connexion PostgreSQL.
    Utilisée par tous les scripts du projet.
    """
    return psycopg2.connect(
        host     = os.getenv("POSTGRES_HOST"),
        port     = os.getenv("POSTGRES_PORT"),
        dbname   = os.getenv("POSTGRES_DB"),
        user     = os.getenv("POSTGRES_USER"),
        password = os.getenv("POSTGRES_PASSWORD")
    )


def creer_tables_si_absentes():
    """
    Crée le schéma raw et la table raw.games s'ils n'existent pas.
    Rend le pipeline auto-suffisant : peut tourner sur une base
    neuve sans intervention manuelle préalable.
    """
    conn = get_connexion()
    cursor = conn.cursor()

    cursor.execute("CREATE SCHEMA IF NOT EXISTS raw;")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw.games (
            uuid                TEXT PRIMARY KEY,
            url                 TEXT,
            date                DATE,
            heure               TEXT,
            heure_int           INTEGER,
            format              TEXT,
            time_control        TEXT,
            rated               BOOLEAN,
            ma_couleur          TEXT,
            mon_username        TEXT,
            mon_rating          INTEGER,
            mon_resultat_brut   TEXT,
            mon_resultat        TEXT,
            adversaire          TEXT,
            adversaire_rating   INTEGER,
            ouverture           TEXT,
            fen_final           TEXT,
            pgn                 TEXT,
            inserted_at         TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()