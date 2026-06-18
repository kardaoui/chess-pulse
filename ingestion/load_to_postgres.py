import os
import sys

# Ajouter le dossier ingestion au path pour importer load_chess
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from load_chess import get_nouvelles_parties
from db_utils import get_connexion, creer_tables_si_absentes


def get_derniere_date(cursor):
    """
    Récupère la date de la dernière partie en base.
    Retourne None si la base est vide.
    """
    cursor.execute("SELECT MAX(date) FROM raw.games;")
    return cursor.fetchone()[0]


def inserer_parties(cursor, parties):
    """
    Insère une liste de parties en base.
    Retourne le nombre de parties insérées et de doublons ignorés.
    """
    inserees = 0
    doublons = 0

    for partie in parties:
        try:
            cursor.execute("""
                INSERT INTO raw.games (
                    uuid, url, date, heure, heure_int,
                    format, time_control, rated,
                    ma_couleur, mon_username, mon_rating,
                    mon_resultat_brut, mon_resultat,
                    adversaire, adversaire_rating,
                    ouverture, fen_final, pgn
                ) VALUES (
                    %(uuid)s, %(url)s, %(date)s, %(heure)s, %(heure_int)s,
                    %(format)s, %(time_control)s, %(rated)s,
                    %(ma_couleur)s, %(mon_username)s, %(mon_rating)s,
                    %(mon_resultat_brut)s, %(mon_resultat)s,
                    %(adversaire)s, %(adversaire_rating)s,
                    %(ouverture)s, %(fen_final)s, %(pgn)s
                )
                ON CONFLICT (uuid) DO NOTHING;
            """, partie)

            if cursor.rowcount == 1:
                inserees += 1
            else:
                doublons += 1

        except Exception as e:
            print(f"❌ Erreur sur la partie {partie['uuid']} : {e}")
            cursor.connection.rollback()
            continue

    return inserees, doublons


def verifier_base(cursor):
    """
    Vérifie l'état de la base et retourne des statistiques.
    """
    stats = {}

    cursor.execute("SELECT COUNT(*) FROM raw.games;")
    stats["total"] = cursor.fetchone()[0]

    cursor.execute("SELECT MIN(date), MAX(date) FROM raw.games;")
    row = cursor.fetchone()
    stats["date_min"] = row[0]
    stats["date_max"] = row[1]

    cursor.execute("""
        SELECT mon_resultat, COUNT(*)
        FROM raw.games
        GROUP BY mon_resultat;
    """)
    stats["resultats"] = {r: c for r, c in cursor.fetchall()}

    return stats


def run_pipeline(depuis_date=None):
    """
    Fonction principale du pipeline.
    Peut être appelée depuis Airflow ou en ligne de commande.
    """
    creer_tables_si_absentes()
    
    conn   = get_connexion()
    cursor = conn.cursor()

    # Étape 1 : dernière date en base
    if depuis_date is None:
        depuis_date = get_derniere_date(cursor)

    if depuis_date:
        print(f"📅 Dernière partie en base : {depuis_date}")
    else:
        print("📅 Base vide — récupération complète")

    # Étape 2 : récupérer les nouvelles parties depuis l'API
    print("\n⏳ Récupération des nouvelles parties...")
    nouvelles_parties = get_nouvelles_parties(depuis_date=depuis_date)
    print(f"📦 {len(nouvelles_parties)} parties récupérées depuis l'API")

    # Étape 3 : insérer en base
    print("\n⏳ Insertion dans PostgreSQL...")
    inserees, doublons = inserer_parties(cursor, nouvelles_parties)
    conn.commit()

    # Étape 4 : résumé
    stats = verifier_base(cursor)

    print(f"\n📊 RÉSUMÉ DU PIPELINE")
    print(f"  ✅ Nouvelles parties insérées : {inserees}")
    print(f"  ➖ Doublons ignorés           : {doublons}")
    print(f"  🗄️  Total en base              : {stats['total']} parties")
    print(f"  📅 Période couverte           : {stats['date_min']} → {stats['date_max']}")

    victoires = stats["resultats"].get("victoire", 0)
    defaites  = stats["resultats"].get("defaite", 0)
    nulles    = stats["resultats"].get("nulle", 0)
    total     = stats["total"]

    print(f"\n📈 STATISTIQUES EN BASE")
    print(f"  ✅ Victoires : {victoires} ({round(victoires/total*100, 1)}%)")
    print(f"  ❌ Défaites  : {defaites} ({round(defaites/total*100, 1)}%)")
    print(f"  ➖ Nulles    : {nulles} ({round(nulles/total*100, 1)}%)")

    cursor.close()
    conn.close()

    return inserees


if __name__ == "__main__":
    """
    Point d'entrée principal du pipeline d'ingestion.
    Lance : python ingestion/load_to_postgres.py
    """
    print("=" * 55)
    print("🚀 CHESSPULSE — PIPELINE D'INGESTION")
    print("=" * 55)

    run_pipeline()

    print("\n✅ Pipeline terminé avec succès !")
    