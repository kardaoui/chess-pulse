-- models/mart/mart_winrate_ouverture.sql
-- Mart : winrate par ouverture
-- Ce modèle est matérialisé en TABLE (stocké physiquement)

WITH base AS (
    SELECT * FROM {{ ref('stg_games') }}
    WHERE ouverture IS NOT NULL
    AND rated = TRUE
)

SELECT
    ouverture,
    famille_ouverture,
    COUNT(*)                                               AS total_parties,
    SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 END)   AS victoires,
    SUM(CASE WHEN mon_resultat = 'defaite'  THEN 1 END)   AS defaites,
    SUM(CASE WHEN mon_resultat = 'nulle'    THEN 1 END)   AS nulles,
    ROUND(
        SUM(CASE WHEN mon_resultat = 'victoire' THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*), 1
    )                                                      AS winrate

FROM base
GROUP BY ouverture, famille_ouverture
HAVING COUNT(*) >= 3
ORDER BY total_parties DESC