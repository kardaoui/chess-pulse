-- models/mart/mart_elo_mensuel.sql
-- Mart : évolution de l'Elo par mois

WITH base AS (
    SELECT * FROM {{ ref('stg_games') }}
    WHERE rated = TRUE
)

SELECT
    TO_CHAR(date, 'YYYY-MM')        AS mois,
    COUNT(*)                         AS total_parties,
    MIN(mon_rating)                  AS elo_min,
    MAX(mon_rating)                  AS elo_max,
    ROUND(AVG(mon_rating), 0)        AS elo_moyen,
    -- Premier et dernier Elo du mois pour voir la progression
    FIRST_VALUE(mon_rating) OVER (
        PARTITION BY TO_CHAR(date, 'YYYY-MM')
        ORDER BY date, heure
    )                                AS elo_debut_mois,
    LAST_VALUE(mon_rating) OVER (
        PARTITION BY TO_CHAR(date, 'YYYY-MM')
        ORDER BY date, heure
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )                                AS elo_fin_mois

FROM base
GROUP BY TO_CHAR(date, 'YYYY-MM'), mon_rating, date, heure
ORDER BY mois