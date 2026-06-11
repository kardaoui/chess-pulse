import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host     = os.getenv("POSTGRES_HOST"),
    port     = os.getenv("POSTGRES_PORT"),
    dbname   = os.getenv("POSTGRES_DB"),
    user     = os.getenv("POSTGRES_USER"),
    password = os.getenv("POSTGRES_PASSWORD")
)
cursor = conn.cursor()

# --- Question 1 : Combien de parties par format ? ---
print("=" * 55)
print("🎮 PARTIES PAR FORMAT")
print("=" * 55)
cursor.execute("""
    SELECT format, COUNT(*) as total
    FROM raw.games
    GROUP BY format
    ORDER BY total DESC;
""")
for format, total in cursor.fetchall():
    print(f"  {format:<10} : {total} parties")

# --- Question 2 : Mon winrate global ---
print("\n" + "=" * 55)
print("🎯 WINRATE GLOBAL")
print("=" * 55)
cursor.execute("""
    SELECT
        mon_resultat,
        COUNT(*) as total,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pourcentage
    FROM raw.games
    GROUP BY mon_resultat
    ORDER BY total DESC;
""")
for resultat, total, pct in cursor.fetchall():
    emoji = "✅" if resultat == "victoire" else ("❌" if resultat == "defaite" else "➖")
    print(f"  {emoji} {resultat:<12} : {total:>4} parties ({pct}%)")

# --- Question 3 : Winrate par couleur ---
print("\n" + "=" * 55)
print("⚪⚫ WINRATE PAR COULEUR")
print("=" * 55)
cursor.execute("""
    SELECT
        ma_couleur,
        COUNT(*) as total,
        SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 ELSE 0 END) as victoires,
        ROUND(
            SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 1
        ) as winrate
    FROM raw.games
    GROUP BY ma_couleur
    ORDER BY ma_couleur;
""")
for couleur, total, victoires, winrate in cursor.fetchall():
    emoji = "⚪" if couleur == "white" else "⚫"
    print(f"  {emoji} {couleur:<8} : {victoires}/{total} victoires ({winrate}%)")

# --- Question 4 : Mes meilleures heures ---
print("\n" + "=" * 55)
print("🕐 WINRATE PAR HEURE DE LA JOURNÉE")
print("=" * 55)
cursor.execute("""
    SELECT
        heure_int,
        COUNT(*) as total,
        ROUND(
            SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 1
        ) as winrate
    FROM raw.games
    GROUP BY heure_int
    HAVING COUNT(*) >= 5
    ORDER BY winrate DESC
    LIMIT 5;
""")
print(f"  {'Heure':<8} {'Parties':<10} {'Winrate'}")
print("  " + "-" * 30)
for heure, total, winrate in cursor.fetchall():
    print(f"  {str(heure)+'h':<8} {total:<10} {winrate}%")

# --- Question 5 : Mes ouvertures les plus jouées ---
print("\n" + "=" * 55)
print("♟️  TOP 5 OUVERTURES LES PLUS JOUÉES")
print("=" * 55)
cursor.execute("""
    SELECT
        ouverture,
        COUNT(*) as total,
        ROUND(
            SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 1
        ) as winrate
    FROM raw.games
    WHERE ouverture IS NOT NULL
    GROUP BY ouverture
    ORDER BY total DESC
    LIMIT 5;
""")
print(f"  {'Ouverture':<45} {'Parties':<10} {'Winrate'}")
print("  " + "-" * 65)
for ouverture, total, winrate in cursor.fetchall():
    ouverture_court = str(ouverture)[:43]
    print(f"  {ouverture_court:<45} {total:<10} {winrate}%")

# --- Question 6 : Evolution de mon Elo ---
print("\n" + "=" * 55)
print("📈 ÉVOLUTION DE MON ELO PAR MOIS")
print("=" * 55)
cursor.execute("""
    SELECT
        TO_CHAR(date, 'YYYY-MM') as mois,
        MIN(mon_rating) as elo_min,
        MAX(mon_rating) as elo_max,
        ROUND(AVG(mon_rating), 0) as elo_moyen
    FROM raw.games
    GROUP BY TO_CHAR(date, 'YYYY-MM')
    ORDER BY mois;
""")
print(f"  {'Mois':<10} {'Elo min':<10} {'Elo max':<10} {'Elo moyen'}")
print("  " + "-" * 40)
for mois, elo_min, elo_max, elo_moyen in cursor.fetchall():
    print(f"  {mois:<10} {elo_min:<10} {elo_max:<10} {elo_moyen}")

cursor.close()
conn.close()