import psycopg2
import json
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

# Charger les parties depuis le fichier JSON
print("📂 Chargement du fichier JSON...")
with open("ingestion/parties_raw.json", "r", encoding="utf-8") as f:
    parties = json.load(f)
print(f"✅ {len(parties)} parties chargées depuis le JSON")

# Insérer chaque partie dans la base
print("\n⏳ Insertion dans PostgreSQL...")
insertions = 0
doublons   = 0

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
        insertions += 1

    except Exception as e:
        print(f"❌ Erreur sur la partie {partie['uuid']} : {e}")
        conn.rollback()
        continue

# Valider toutes les insertions
conn.commit()

print(f"\n📊 RÉSULTAT :")
print(f"  ✅ Parties insérées : {insertions}")
print(f"  ➖ Doublons ignorés : {doublons}")

# Vérifier dans la base
cursor.execute("SELECT COUNT(*) FROM raw.games;")
total = cursor.fetchone()[0]
print(f"  🗄️  Total en base    : {total} parties")

# Aperçu des premières lignes
print(f"\n🔍 APERÇU DES 5 PREMIÈRES PARTIES EN BASE :")
cursor.execute("""
    SELECT date, heure, format, ma_couleur, mon_rating,
           adversaire_rating, mon_resultat, ouverture
    FROM raw.games
    ORDER BY date DESC, heure DESC
    LIMIT 5;
""")

lignes = cursor.fetchall()
print(f"  {'Date':<12} {'Heure':<8} {'Format':<8} {'Couleur':<8} {'MonElo':<8} {'AdvElo':<8} {'Résultat':<12} Ouverture")
print("  " + "-" * 90)
for ligne in lignes:
    date, heure, fmt, couleur, mon_elo, adv_elo, resultat, ouverture = ligne
    ouverture_court = str(ouverture)[:30] if ouverture else "N/A"
    print(f"  {str(date):<12} {heure:<8} {fmt:<8} {couleur:<8} {str(mon_elo):<8} {str(adv_elo):<8} {resultat:<12} {ouverture_court}")

cursor.close()
conn.close()