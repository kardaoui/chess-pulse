"""
Marque des parties comme exclues du périmètre d'analyse.

Les parties ne sont jamais supprimées, pour trois raisons :

  1. Une suppression ferait reculer MAX(date), et la prochaine exécution de
     run_pipeline() re-téléchargerait puis ré-insérerait les lignes effacées.
  2. Un marquage se corrige par un UPDATE ; une suppression impose de tout
     re-télécharger depuis l'API.
  3. ON CONFLICT DO NOTHING ne réécrit jamais une ligne existante : le
     marquage survit à toutes les ré-ingestions.

Les parties marquées restent dans raw.games mais sont filtrées par
stg_games — elles ne remontent donc ni aux marts, ni aux modèles ML.

Exemples :

    # Écarter les N dernières parties d'un compte
    python ingestion/exclure_parties.py --compte midounesk --dernieres 50

    # Écarter tout ce qui suit une date (bornes incluses)
    python ingestion/exclure_parties.py --compte midounesk --depuis 2026-06-12
    python ingestion/exclure_parties.py --compte midounesk --depuis 2026-06-12 --jusqu-a 2026-07-01

    # Voir ce qui serait marqué, sans rien écrire
    python ingestion/exclure_parties.py --compte midounesk --dernieres 50 --simulation

    # Tout réinitialiser pour un compte
    python ingestion/exclure_parties.py --compte midounesk --annuler
"""
import argparse
import sys

from db_utils import get_connexion
from load_to_postgres import FORMATS_ANALYSES

MOTIF_DEFAUT = "periode_non_representative"


def _selection(cursor, args):
    """Retourne les uuid visés, du plus ancien au plus récent."""
    formats = list(FORMATS_ANALYSES)

    if args.dernieres:
        cursor.execute("""
            SELECT uuid, date, heure, mon_rating
            FROM raw.games
            WHERE compte = %s AND format = ANY(%s)
            ORDER BY date DESC, heure DESC
            LIMIT %s;
        """, (args.compte, formats, args.dernieres))
        return list(reversed(cursor.fetchall()))

    cursor.execute("""
        SELECT uuid, date, heure, mon_rating
        FROM raw.games
        WHERE compte = %s
          AND format = ANY(%s)
          AND date >= %s::date
          AND (%s::date IS NULL OR date <= %s::date)
        ORDER BY date, heure;
    """, (args.compte, formats, args.depuis, args.jusqu_a, args.jusqu_a))
    return cursor.fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compte", required=True,
                        help="compte Chess.com concerné (ex. midounesk)")
    parser.add_argument("--dernieres", type=int,
                        help="écarter les N dernières parties")
    parser.add_argument("--depuis",
                        help="écarter à partir de cette date (AAAA-MM-JJ, incluse)")
    parser.add_argument("--jusqu-a", dest="jusqu_a",
                        help="borne de fin optionnelle (AAAA-MM-JJ, incluse)")
    parser.add_argument("--motif", default=MOTIF_DEFAUT,
                        help=f"motif enregistré (défaut : {MOTIF_DEFAUT})")
    parser.add_argument("--annuler", action="store_true",
                        help="lever toutes les exclusions du compte")
    parser.add_argument("--simulation", action="store_true",
                        help="afficher sans écrire en base")
    args = parser.parse_args()
    args.compte = args.compte.lower()

    if not args.annuler and not args.dernieres and not args.depuis:
        parser.error("préciser --dernieres, --depuis ou --annuler")
    if args.dernieres and args.depuis:
        parser.error("--dernieres et --depuis s'excluent mutuellement")

    conn   = get_connexion()
    cursor = conn.cursor()

    print("=" * 55)
    print("🚫 CHESSPULSE — EXCLUSIONS D'ANALYSE")
    print("=" * 55)
    print(f"  Compte  : {args.compte}")
    print(f"  Formats : {', '.join(FORMATS_ANALYSES)}\n")

    if args.annuler:
        cursor.execute("""
            UPDATE raw.games
            SET exclu_analyse = FALSE, motif_exclusion = NULL
            WHERE compte = %s AND exclu_analyse = TRUE;
        """, (args.compte,))
        print(f"  ↩️  {cursor.rowcount} exclusions levées")
        if args.simulation:
            conn.rollback()
            print("  🧪 Simulation — aucune écriture")
        else:
            conn.commit()
        cursor.close()
        conn.close()
        return

    visees = _selection(cursor, args)

    if not visees:
        print("  ⚠️  Aucune partie ne correspond — rien à faire")
        cursor.close()
        conn.close()
        sys.exit(1)

    premiere, derniere = visees[0], visees[-1]
    print(f"  📦 {len(visees)} parties visées")
    print(f"  📅 {premiere[1]} {premiere[2]} → {derniere[1]} {derniere[2]}")
    print(f"  📈 Elo {premiere[3]} → {derniere[3]}")
    print(f"  🏷️  Motif : {args.motif}")

    cursor.execute("""
        UPDATE raw.games
        SET exclu_analyse = TRUE, motif_exclusion = %s
        WHERE uuid = ANY(%s);
    """, (args.motif, [v[0] for v in visees]))
    marquees = cursor.rowcount

    if args.simulation:
        conn.rollback()
        print(f"\n  🧪 Simulation — {marquees} lignes auraient été marquées")
    else:
        conn.commit()
        print(f"\n  ✅ {marquees} parties marquées")

        cursor.execute("""
            SELECT COUNT(*) FROM raw.games
            WHERE compte = %s AND format = ANY(%s) AND exclu_analyse = FALSE;
        """, (args.compte, list(FORMATS_ANALYSES)))
        print(f"  📊 Parties restantes pour l'analyse : {cursor.fetchone()[0]}")
        print("\n  ⏭️  Relance ensuite : dbt run")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
