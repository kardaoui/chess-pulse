import requests
from datetime import datetime, date
from dotenv import load_dotenv
import os

load_dotenv()

USERNAME = os.getenv("CHESS_USERNAME")

HEADERS = {
    "User-Agent": "ChessPulse/1.0 portfolio-project"
}


def get_archives_manquantes(username, depuis_date):
    """
    Récupère uniquement les mois entre la dernière partie
    en base et aujourd'hui.
    """
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = requests.get(url, headers=HEADERS)
    toutes_archives = response.json()["archives"]

    if depuis_date is None:
        return toutes_archives

    archives_manquantes = []
    for archive_url in toutes_archives:
        annee = int(archive_url.split("/")[-2])
        mois  = int(archive_url.split("/")[-1])
        if date(annee, mois, 1) >= date(depuis_date.year, depuis_date.month, 1):
            archives_manquantes.append(archive_url)

    return archives_manquantes


def get_games_by_month(archive_url):
    """Récupère toutes les parties d'un mois donné."""
    response = requests.get(archive_url, headers=HEADERS)
    return response.json()["games"]


def extraire_infos(partie, mon_username):
    """
    Transforme une partie brute de l'API en dictionnaire propre.
    """
    if partie["white"]["username"].lower() == mon_username.lower():
        ma_couleur = "white"
        couleur_adverse = "black"
    else:
        ma_couleur = "black"
        couleur_adverse = "white"

    mon_resultat_brut = partie[ma_couleur]["result"]

    if mon_resultat_brut == "win":
        mon_resultat = "victoire"
    elif mon_resultat_brut in ["agreed", "stalemate", "repetition", "insufficient", "50move"]:
        mon_resultat = "nulle"
    else:
        mon_resultat = "defaite"

    date_partie = datetime.fromtimestamp(partie["end_time"])

    ouverture = None
    if "eco" in partie:
        ouverture = partie["eco"].split("/")[-1]

    return {
        "uuid"              : partie["uuid"],
        "url"               : partie["url"],
        "date"              : date_partie.strftime("%Y-%m-%d"),
        "heure"             : date_partie.strftime("%H:%M"),
        "heure_int"         : date_partie.hour,
        "format"            : partie["time_class"],
        "time_control"      : partie["time_control"],
        "rated"             : partie["rated"],
        "ma_couleur"        : ma_couleur,
        "mon_username"      : partie[ma_couleur]["username"],
        "mon_rating"        : partie[ma_couleur]["rating"],
        "mon_resultat_brut" : mon_resultat_brut,
        "mon_resultat"      : mon_resultat,
        "adversaire"        : partie[couleur_adverse]["username"],
        "adversaire_rating" : partie[couleur_adverse]["rating"],
        "ouverture"         : ouverture,
        "fen_final"         : partie.get("fen", None),
        "pgn"               : partie.get("pgn", None),
    }


def get_nouvelles_parties(depuis_date=None):
    """
    Fonction principale — récupère toutes les nouvelles parties.
    Retourne une liste de parties prêtes à être insérées.
    """
    archives_utiles = get_archives_manquantes(USERNAME, depuis_date)

    toutes_parties = []
    for archive_url in archives_utiles:
        mois = archive_url.split("/")[-2] + "/" + archive_url.split("/")[-1]
        parties_du_mois = get_games_by_month(archive_url)
        parties_extraites = [extraire_infos(p, USERNAME) for p in parties_du_mois]
        toutes_parties.extend(parties_extraites)
        print(f"  📥 {mois} : {len(parties_du_mois)} parties récupérées")

    return toutes_parties


if __name__ == "__main__":
    """
    Mode test — permet de tester l'API sans toucher à PostgreSQL.
    Lance : python load_chess.py
    """
    from datetime import date

    print("=" * 50)
    print("🧪 TEST API CHESS.COM")
    print("=" * 50)

    # Test 1 : vérifier que l'API répond
    print(f"\n👤 Username : {USERNAME}")
    url = f"https://api.chess.com/pub/player/{USERNAME}/games/archives"
    response = requests.get(url, headers=HEADERS)
    archives = response.json()["archives"]
    print(f"📅 Mois disponibles : {len(archives)}")
    print(f"   → Premier : {archives[0].split('/')[-2]}/{archives[0].split('/')[-1]}")
    print(f"   → Dernier : {archives[-1].split('/')[-2]}/{archives[-1].split('/')[-1]}")

    # Test 2 : récupérer le mois le plus récent
    print(f"\n⏳ Récupération du mois le plus récent...")
    parties = get_games_by_month(archives[-1])
    print(f"♟️  Parties ce mois : {len(parties)}")

    # Test 3 : transformer une partie
    exemple = extraire_infos(parties[0], USERNAME)
    print(f"\n🔍 Exemple de partie transformée :")
    for cle, valeur in exemple.items():
        if cle != "pgn":
            print(f"  {cle:20s} : {valeur}")

    # Test 4 : simuler une récupération incrémentale
    print(f"\n📦 Test récupération incrémentale :")
    print(f"  Simulation — dernière partie en base : 2026-03-01")
    depuis = date(2026, 3, 1)
    archives_utiles = get_archives_manquantes(USERNAME, depuis)
    print(f"  Mois à traiter : {len(archives_utiles)}/{len(archives)}")
    for a in archives_utiles:
        print(f"    → {a.split('/')[-2]}/{a.split('/')[-1]}")