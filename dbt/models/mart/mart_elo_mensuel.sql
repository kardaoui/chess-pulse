-- models/mart/mart_elo_mensuel.sql
-- Mart : évolution de l'Elo par (compte, format, mois)
--
-- Le classement Chess.com est propre à un compte ET à un format : agréger
-- au-delà de ce couple produit des moyennes qui ne décrivent rien. Le grain
-- de cette table est donc (compte, format, mois) — une ligne par mois joué.

WITH base AS (
    SELECT * FROM {{ ref('stg_games') }}
    WHERE rated = TRUE
),

mensuel AS (
    SELECT
        compte,
        format,
        TO_CHAR(date, 'YYYY-MM')  AS mois,

        COUNT(*)                  AS total_parties,
        MIN(mon_rating)           AS elo_min,
        MAX(mon_rating)           AS elo_max,
        ROUND(AVG(mon_rating), 0) AS elo_moyen,

        -- Premier et dernier Elo du mois.
        -- ARRAY_AGG ordonné plutôt que FIRST_VALUE / LAST_VALUE : une fonction
        -- fenêtre imposerait d'ajouter date, heure et mon_rating au GROUP BY,
        -- ce qui ramènerait le grain à une ligne par partie et annulerait
        -- l'agrégation mensuelle.
        (ARRAY_AGG(mon_rating ORDER BY date,      heure))[1]      AS elo_debut_mois,
        (ARRAY_AGG(mon_rating ORDER BY date DESC, heure DESC))[1] AS elo_fin_mois

    FROM base
    GROUP BY compte, format, TO_CHAR(date, 'YYYY-MM')
)

SELECT
    compte,
    format,
    mois,
    total_parties,
    elo_min,
    elo_max,
    elo_moyen,
    elo_debut_mois,
    elo_fin_mois,

    -- Progression du mois
    elo_fin_mois - elo_debut_mois AS progression_mois,

    -- Progression cumulée depuis la première partie du compte.
    -- C'est la seule mesure comparable d'un compte à l'autre : deux comptes
    -- ne démarrent pas au même Elo, donc leurs niveaux absolus ne se
    -- superposent pas, mais leurs trajectoires si.
    elo_fin_mois - FIRST_VALUE(elo_debut_mois) OVER (
        PARTITION BY compte, format
        ORDER BY mois
    ) AS progression_depuis_debut_compte

FROM mensuel
ORDER BY compte, format, mois
