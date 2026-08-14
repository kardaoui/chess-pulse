import os
import sys

# Ajouter le dossier ingestion au path pour importer load_chess
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from load_chess import get_nouvelles_parties, USERNAME
from db_utils import get_connexion, creer_tables_si_absentes


# Formats retenus pour l'analyse et pour le curseur incrémental.
# Chess.com tient un classement séparé par format : les mélanger dans un
# même agrégat d'Elo n'a pas de sens. Voir aussi le filtre de stg_games.
FORMATS_ANALYSES = ["rapid"]


def get_derniere_date(cursor, compte, formats=None):
    """
    Récupère la date de la dernière partie en base pour un compte donné.
    Retourne None si ce compte n'a aucune partie.

    Deux filtres, tous deux indispensables :

    - par `compte` : sans lui, le curseur d'un nouveau compte hérite de la
      dernière date de l'ancien et saute les archives antérieures.
    - par `format` : une partie `daily` se termine parfois des semaines
      après avoir commencé. Comme `date` dérive de son end_time, une seule
      partie par correspondance suffit à pousser le curseur un mois trop
      loin et à faire sauter une archive mensuelle entière.
    """
    formats = list(formats or FORMATS_ANALYSES)
    cursor.execute("""
        SELECT MAX(date) FROM raw.games
        WHERE compte = %s
          AND format = ANY(%s);
    """, (compte.lower(), formats))
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
                    uuid, url, compte, date, heure, heure_int,
                    format, time_control, rated,
                    ma_couleur, mon_username, mon_rating,
                    mon_resultat_brut, mon_resultat,
                    adversaire, adversaire_rating,
                    ouverture, fen_final, pgn
                ) VALUES (
                    %(uuid)s, %(url)s, %(compte)s, %(date)s, %(heure)s, %(heure_int)s,
                    %(format)s, %(time_control)s, %(rated)s,
                    %(ma_couleur)s, %(mon_username)s, %(mon_rating)s,
                    %(mon_resultat_brut)s, %(mon_resultat)s,
                    %(adversaire)s, %(adversaire_rating)s,
                    %(ouverture)s, %(fen_final)s, %(pgn)s
                )
                -- DO NOTHING et non DO UPDATE : une ligne déjà présente n'est
                -- jamais réécrite, ce qui préserve le marquage exclu_analyse
                -- posé manuellement, même si l'archive est re-téléchargée.
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


def verifier_base(cursor, compte, formats=None):
    """
    Vérifie l'état de la base pour un compte et retourne des statistiques.
    Les compteurs sont restreints aux formats analysés — mélanger les
    formats fausserait toute lecture de l'Elo.
    """
    formats = list(formats or FORMATS_ANALYSES)
    portee = (compte.lower(), formats)
    stats = {}

    cursor.execute("""
        SELECT COUNT(*), MIN(date), MAX(date)
        FROM raw.games
        WHERE compte = %s AND format = ANY(%s);
    """, portee)
    stats["total"], stats["date_min"], stats["date_max"] = cursor.fetchone()

    cursor.execute("""
        SELECT mon_resultat, COUNT(*)
        FROM raw.games
        WHERE compte = %s AND format = ANY(%s)
        GROUP BY mon_resultat;
    """, portee)
    stats["resultats"] = {r: c for r, c in cursor.fetchall()}

    cursor.execute("""
        SELECT COUNT(*)
        FROM raw.games
        WHERE compte = %s AND format = ANY(%s) AND exclu_analyse = TRUE;
    """, portee)
    stats["exclues"] = cursor.fetchone()[0]

    return stats


def run_pipeline(depuis_date=None, compte=None):
    """
    Fonction principale du pipeline.
    Peut être appelée depuis Airflow ou en ligne de commande.

    `compte` vaut par défaut CHESS_USERNAME. Le curseur incrémental est
    propre à ce compte : changer de compte Chess.com ne fait donc plus
    sauter silencieusement les archives antérieures à l'ancien compte.
    """
    compte = (compte or USERNAME).lower()

    creer_tables_si_absentes()

    conn   = get_connexion()
    cursor = conn.cursor()

    print(f"👤 Compte : {compte}")
    print(f"🎯 Formats analysés : {', '.join(FORMATS_ANALYSES)}")

    # Étape 1 : dernière date en base pour CE compte
    if depuis_date is None:
        depuis_date = get_derniere_date(cursor, compte)

    if depuis_date:
        print(f"📅 Dernière partie en base : {depuis_date}")
    else:
        print("📅 Aucune partie pour ce compte — récupération complète")

    # Étape 2 : récupérer les nouvelles parties depuis l'API
    print("\n⏳ Récupération des nouvelles parties...")
    nouvelles_parties = get_nouvelles_parties(depuis_date=depuis_date)
    print(f"📦 {len(nouvelles_parties)} parties récupérées depuis l'API")

    # Étape 3 : insérer en base
    print("\n⏳ Insertion dans PostgreSQL...")
    inserees, doublons = inserer_parties(cursor, nouvelles_parties)
    conn.commit()

    # Étape 4 : résumé
    stats = verifier_base(cursor, compte)

    print(f"\n📊 RÉSUMÉ DU PIPELINE")
    print(f"  ✅ Nouvelles parties insérées : {inserees}")
    print(f"  ➖ Doublons ignorés           : {doublons}")
    print(f"  🗄️  Total pour {compte:<15} : {stats['total']} parties")
    print(f"  📅 Période couverte           : {stats['date_min']} → {stats['date_max']}")
    if stats["exclues"]:
        print(f"  🚫 Exclues de l'analyse       : {stats['exclues']} parties")

    victoires = stats["resultats"].get("victoire", 0)
    defaites  = stats["resultats"].get("defaite", 0)
    nulles    = stats["resultats"].get("nulle", 0)
    total     = stats["total"]

    if total:
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
