"""
Migration 001 — Ajoute le suivi multi-comptes et le marquage d'exclusion.

`create_tables.py` utilise CREATE TABLE IF NOT EXISTS : il ne modifie jamais
une table déjà créée. Ce script applique les changements de schéma sur une
base existante. Il est idempotent — le relancer ne fait rien de plus.

Lance : python ingestion/migrate_001_compte_exclusion.py
"""
from db_utils import get_connexion


INSTRUCTIONS = [
    # Compte Chess.com interrogé pour cette partie.
    # Distinct de `mon_username` (qui vient de la réponse API et garde la
    # casse de Chess.com) : `compte` est normalisé en minuscules et sert de
    # clé stable pour le curseur d'ingestion incrémentale.
    ("Colonne compte",
     "ALTER TABLE raw.games ADD COLUMN IF NOT EXISTS compte TEXT;"),

    # Marquage d'exclusion — on ne supprime jamais de partie : une suppression
    # ferait reculer MAX(date), et la prochaine ingestion re-téléchargerait
    # puis ré-insérerait les lignes effacées.
    ("Colonne exclu_analyse",
     "ALTER TABLE raw.games ADD COLUMN IF NOT EXISTS exclu_analyse BOOLEAN NOT NULL DEFAULT FALSE;"),

    ("Colonne motif_exclusion",
     "ALTER TABLE raw.games ADD COLUMN IF NOT EXISTS motif_exclusion TEXT;"),

    # Backfill : toutes les lignes existantes proviennent du compte historique.
    ("Backfill de compte",
     "UPDATE raw.games SET compte = LOWER(mon_username) WHERE compte IS NULL;"),

    # Le curseur incrémental filtre sur (compte, format) et trie par date.
    ("Index (compte, format, date)",
     "CREATE INDEX IF NOT EXISTS idx_games_compte_format_date "
     "ON raw.games (compte, format, date);"),
]


def migrer():
    conn = get_connexion()
    cursor = conn.cursor()

    print("=" * 55)
    print("🔧 MIGRATION 001 — compte + exclusion")
    print("=" * 55 + "\n")

    for libelle, sql in INSTRUCTIONS:
        cursor.execute(sql)
        print(f"  ✅ {libelle}")

    conn.commit()

    # Vérification : répartition des parties par compte
    cursor.execute("""
        SELECT compte, format, COUNT(*), MIN(date), MAX(date)
        FROM raw.games
        GROUP BY compte, format
        ORDER BY compte, COUNT(*) DESC;
    """)
    lignes = cursor.fetchall()

    print(f"\n📊 RÉPARTITION APRÈS MIGRATION")
    print(f"  {'compte':<15} {'format':<8} {'n':>6}  période")
    print("  " + "-" * 52)
    for compte, format_, n, dmin, dmax in lignes:
        print(f"  {str(compte):<15} {str(format_):<8} {n:>6}  {dmin} → {dmax}")

    cursor.execute("SELECT COUNT(*) FROM raw.games WHERE compte IS NULL;")
    orphelines = cursor.fetchone()[0]
    if orphelines:
        print(f"\n  ⚠️  {orphelines} parties sans compte renseigné")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    migrer()
    print("\n✅ Migration terminée")
