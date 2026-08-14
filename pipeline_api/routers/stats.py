from fastapi import APIRouter, HTTPException
from db import get_connexion

router = APIRouter()


@router.get("/")
def get_stats_globales():
    """
    KPIs globaux : total parties, victoires, défaites, nulles.

    Lit stg_games et non raw.games : c'est stg_games qui porte le périmètre
    d'analyse (format rapid, parties non exclues). Interroger raw.games
    directement exposerait les parties écartées.
    """
    conn = get_connexion()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                COUNT(*)                                                   AS total_parties,
                SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 ELSE 0 END) AS victoires,
                SUM(CASE WHEN mon_resultat = 'defaite'  THEN 1 ELSE 0 END) AS defaites,
                SUM(CASE WHEN mon_resultat = 'nulle'    THEN 1 ELSE 0 END) AS nulles
            FROM public_staging.stg_games
        """)
        row = cursor.fetchone()
        return {
            "total_parties": row[0],
            "victoires":     row[1],
            "defaites":      row[2],
            "nulles":        row[3]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@router.get("/elo")
def get_elo_mensuel():
    """
    Évolution de l'Elo par mois, ventilée par compte.

    Le classement Chess.com est propre à un compte : deux comptes ne
    démarrent pas au même Elo, donc leurs niveaux absolus ne se comparent
    pas. `progression_depuis_debut_compte` est la seule mesure qui, elle,
    reste comparable d'un compte à l'autre.
    """
    conn = get_connexion()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT compte, mois, elo_moyen, elo_debut_mois, elo_fin_mois,
                   elo_min, elo_max, total_parties,
                   progression_mois, progression_depuis_debut_compte
            FROM public_mart.mart_elo_mensuel
            ORDER BY compte ASC, mois ASC
        """)
        rows = cursor.fetchall()
        return [
            {
                "compte":         row[0],
                "mois":           row[1],
                "elo_moyen":      float(row[2]),
                "elo_debut_mois": row[3],
                "elo_fin_mois":   row[4],
                "elo_min":        row[5],
                "elo_max":        row[6],
                "total_parties":  row[7],
                "progression_mois":                 row[8],
                "progression_depuis_debut_compte":  row[9]
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@router.get("/ouvertures")
def get_winrate_ouvertures():
    """
    Winrate par ouverture.
    """
    conn = get_connexion()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ouverture, famille_ouverture, total_parties,
                   victoires, defaites, nulles, winrate
            FROM public_mart.mart_winrate_ouverture
            ORDER BY total_parties DESC
        """)
        rows = cursor.fetchall()
        return [
            {
                "ouverture":         row[0],
                "famille_ouverture": row[1],
                "total_parties":     row[2],
                "victoires":         row[3],
                "defaites":          row[4],
                "nulles":            row[5],
                "winrate":           float(row[6])
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@router.get("/moments")
def get_winrate_moments():
    """
    Winrate par moment de la journée, calculé depuis stg_games.
    mart_winrate_ouverture ne contient pas cette dimension.
    """
    conn = get_connexion()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                moment_journee,
                COUNT(*)                                                   AS total_parties,
                SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 ELSE 0 END) AS victoires,
                SUM(CASE WHEN mon_resultat = 'defaite'  THEN 1 ELSE 0 END) AS defaites,
                SUM(CASE WHEN mon_resultat = 'nulle'    THEN 1 ELSE 0 END) AS nulles,
                ROUND(
                    100.0 * SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2
                )                                                          AS winrate
            FROM public_staging.stg_games
            GROUP BY moment_journee
            ORDER BY total_parties DESC
        """)
        rows = cursor.fetchall()
        return [
            {
                "moment_journee": row[0],
                "total_parties":  row[1],
                "victoires":      row[2],
                "defaites":       row[3],
                "nulles":         row[4],
                "winrate":        float(row[5]) if row[5] is not None else 0.0
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()