import requests
import json
from datetime import datetime

USERNAME = "midounesk"

HEADERS = {
    "User-Agent": "ChessPulse/1.0 portfolio-project"
}


def get_archives(username):
    """Récupère la liste de tous les mois disponibles."""
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = requests.get(url, headers=HEADERS)
    return response.json()["archives"]


def get_games_by_month(archive_url):
    """Récupère toutes les parties d'un mois donné."""
    response = requests.get(archive_url, headers=HEADERS)
    return response.json()["games"]


def extraire_infos(partie, mon_username):
    """
    Transforme une partie brute de l'API en dictionnaire propre.
    C'est ici qu'on fait le travail de la couche STAGING :
    - on aplatit les objets imbriqués (white, black)
    - on convertit le timestamp en date lisible
    - on extrait le nom de l'ouverture depuis l'URL eco
    - on détermine si j'ai gagné, perdu ou fait nulle
    """

    # Identifier ma couleur dans cette partie
    if partie["white"]["username"].lower() == mon_username.lower():
        ma_couleur = "white"
        couleur_adverse = "black"
    else:
        ma_couleur = "black"
        couleur_adverse = "white"

    mon_resultat_brut = partie[ma_couleur]["result"]

    # Normaliser le résultat en 3 catégories simples
    if mon_resultat_brut == "win":
        mon_resultat = "victoire"
    elif mon_resultat_brut in ["agreed", "stalemate", "repetition", "insufficient", "50move"]:
        mon_resultat = "nulle"
    else:
        mon_resultat = "defaite"

    # Convertir le timestamp Unix en date lisible
    # Unix timestamp = nombre de secondes depuis le 1er janvier 1970
    date_partie = datetime.fromtimestamp(partie["end_time"])

    # Extraire le nom de l'ouverture depuis l'URL
    # Ex: ".../Italian-Game-Two-Knights" → "Italian-Game-Two-Knights"
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


if __name__ == "__main__":

    # Récupérer toutes les parties de tous les mois
    print("⏳ Récupération de toutes tes parties...")
    archives = get_archives(USERNAME)
    toutes_les_parties = []

    for archive_url in archives:
        mois = archive_url.split("/")[-2] + "/" + archive_url.split("/")[-1]
        parties_du_mois = get_games_by_month(archive_url)
        parties_extraites = [extraire_infos(p, USERNAME) for p in parties_du_mois]
        toutes_les_parties.extend(parties_extraites)
        print(f"  ✅ {mois} : {len(parties_du_mois)} parties récupérées")

    print(f"\n🎯 TOTAL : {len(toutes_les_parties)} parties sur {len(archives)} mois")

    # Statistiques globales
    victoires = sum(1 for p in toutes_les_parties if p["mon_resultat"] == "victoire")
    defaites  = sum(1 for p in toutes_les_parties if p["mon_resultat"] == "defaite")
    nulles    = sum(1 for p in toutes_les_parties if p["mon_resultat"] == "nulle")
    winrate   = round(victoires / len(toutes_les_parties) * 100, 1)

    print(f"\n📊 STATISTIQUES GLOBALES")
    print(f"  ✅ Victoires : {victoires}")
    print(f"  ❌ Défaites  : {defaites}")
    print(f"  ➖ Nulles    : {nulles}")
    print(f"  🎯 Winrate   : {winrate}%")

    # Afficher un exemple de partie transformée
    print(f"\n🔍 EXEMPLE — partie transformée prête pour la base de données :")
    exemple = toutes_les_parties[0]
    for cle, valeur in exemple.items():
        if cle != "pgn":  # Le PGN est trop long
            print(f"  {cle:20s} : {valeur}")

    # Sauvegarder en JSON pour l'étape suivante
    with open("ingestion/parties_raw.json", "w", encoding="utf-8") as f:
        json.dump(toutes_les_parties, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 Données sauvegardées dans ingestion/parties_raw.json")