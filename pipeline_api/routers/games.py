from fastapi import APIRouter, HTTPException, Query
from db import get_connexion

router = APIRouter()


@router.get("/")
def get_games(
    limit:  int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    format: str = Query(default=None),
    couleur: str = Query(default=None),
    resultat: str = Query(default=None),
):
    """
    Liste des parties avec filtres optionnels et pagination.
    - limit  : nombre de parties retournées (1-500, défaut 50)
    - offset : décalage pour la pagination (défaut 0)
    - format : blitz, bullet, rapid...
    - couleur : white, black
    - resultat : victoire, defaite, nulle
    """
    conn = get_connexion()
    cursor = conn.cursor()
    try:
        conditions = []
        params = []

        if format:
            conditions.append("format = %s")
            params.append(format)
        if couleur:
            conditions.append("ma_couleur = %s")
            params.append(couleur)
        if resultat:
            conditions.append("mon_resultat = %s")
            params.append(resultat)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        cursor.execute(f"""
            SELECT uuid, date, format, ma_couleur, mon_rating,
                   adversaire, adversaire_rating, mon_resultat,
                   ouverture, famille_ouverture, moment_journee,
                   diff_elo, niveau_adversaire
            FROM public_staging.stg_games
            {where_clause}
            ORDER BY date DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])

        rows = cursor.fetchall()
        return [
            {
                "uuid":              row[0],
                "date":              str(row[1]),
                "format":            row[2],
                "ma_couleur":        row[3],
                "mon_rating":        row[4],
                "adversaire":        row[5],
                "adversaire_rating": row[6],
                "mon_resultat":      row[7],
                "ouverture":         row[8],
                "famille_ouverture": row[9],
                "moment_journee":    row[10],
                "diff_elo":          row[11],
                "niveau_adversaire": row[12]
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@router.get("/{uuid}")
def get_game_detail(uuid: str):
    """
    Détail complet d'une partie, incluant le PGN.
    Utilisé par la Zone Board pour le replay coup par coup.
    """
    conn = get_connexion()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT uuid, date, heure, format, time_control, rated,
                   ma_couleur, mon_username, mon_rating, mon_resultat,
                   adversaire, adversaire_rating, ouverture, famille_ouverture,
                   moment_journee, diff_elo, niveau_adversaire,
                   fen_final, pgn
            FROM public_staging.stg_games
            WHERE uuid = %s
        """, (uuid,))

        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Partie {uuid} introuvable")

        return {
            "uuid":              row[0],
            "date":              str(row[1]),
            "heure":             row[2],
            "format":            row[3],
            "time_control":      row[4],
            "rated":             row[5],
            "ma_couleur":        row[6],
            "mon_username":      row[7],
            "mon_rating":        row[8],
            "mon_resultat":      row[9],
            "adversaire":        row[10],
            "adversaire_rating": row[11],
            "ouverture":         row[12],
            "famille_ouverture": row[13],
            "moment_journee":    row[14],
            "diff_elo":          row[15],
            "niveau_adversaire": row[16],
            "fen_final":         row[17],
            "pgn":               row[18]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()