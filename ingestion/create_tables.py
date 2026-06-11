import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Connexion à PostgreSQL
conn = psycopg2.connect(
    host     = os.getenv("POSTGRES_HOST"),
    port     = os.getenv("POSTGRES_PORT"),
    dbname   = os.getenv("POSTGRES_DB"),
    user     = os.getenv("POSTGRES_USER"),
    password = os.getenv("POSTGRES_PASSWORD")
)
cursor = conn.cursor()

# Création du schéma raw
# Un schéma c'est comme un dossier dans la base de données
# On sépare raw / staging / mart comme dans dbt
cursor.execute("CREATE SCHEMA IF NOT EXISTS raw;")

# Création de la table raw_games
# C'est ici qu'on définit toutes les colonnes
cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw.games (

        -- Identifiants
        uuid            TEXT PRIMARY KEY,  -- identifiant unique de la partie
        url             TEXT,              -- lien vers la partie sur Chess.com

        -- Informations temporelles
        date            DATE,              -- date de la partie (2026-06-01)
        heure           TEXT,              -- heure de la partie (14:32)
        heure_int       INTEGER,           -- heure en chiffre (14) pour les calculs

        -- Format de la partie
        format          TEXT,              -- rapid, blitz, bullet
        time_control    TEXT,              -- durée en secondes (600 = 10 min)
        rated           BOOLEAN,           -- partie classée ou non

        -- Informations sur toi
        ma_couleur          TEXT,          -- white ou black
        mon_username        TEXT,          -- toujours midounesk
        mon_rating          INTEGER,       -- ton Elo au moment de la partie
        mon_resultat_brut   TEXT,          -- win, resigned, checkmated...
        mon_resultat        TEXT,          -- victoire, defaite, nulle

        -- Informations sur l'adversaire
        adversaire          TEXT,          -- username de l'adversaire
        adversaire_rating   INTEGER,       -- Elo de l'adversaire

        -- Informations sur la partie
        ouverture       TEXT,              -- nom de l'ouverture jouée
        fen_final       TEXT,              -- position finale sur l'échiquier
        pgn             TEXT,              -- tous les coups de la partie

        -- Métadonnées
        inserted_at     TIMESTAMP DEFAULT NOW()  -- date d'insertion en base
    );
""")

# Valider les changements
conn.commit()
print("✅ Schéma 'raw' créé")
print("✅ Table 'raw.games' créée")

# Vérifier que la table existe bien
cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'raw'
    AND table_name = 'games'
    ORDER BY ordinal_position;
""")

colonnes = cursor.fetchall()
print(f"\n📋 Colonnes de la table raw.games ({len(colonnes)} colonnes) :")
for nom, type_col in colonnes:
    print(f"  {nom:25s} : {type_col}")

cursor.close()
conn.close()