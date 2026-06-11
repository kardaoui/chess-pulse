-- models/staging/stg_games.sql
-- Couche staging : on enrichit les données raw avec des colonnes calculées
-- Ce modèle est matérialisé en VIEW (recalculé à chaque fois)

WITH source AS (
    -- On lit depuis la table raw qu'on a chargée avec Python
    SELECT * FROM raw.games
),

enriched AS (
    SELECT
        -- Identifiants
        uuid,
        url,

        -- Temporel
        date,
        heure,
        heure_int,

        -- Catégoriser l'heure de la journée
        CASE
            WHEN heure_int BETWEEN 6  AND 11 THEN 'matin'
            WHEN heure_int BETWEEN 12 AND 17 THEN 'apres-midi'
            WHEN heure_int BETWEEN 18 AND 22 THEN 'soiree'
            ELSE 'nuit'
        END AS moment_journee,

        -- Format
        format,
        time_control,
        rated,

        -- Moi
        ma_couleur,
        mon_username,
        mon_rating,
        mon_resultat,

        -- Calculer la différence d'Elo avec l'adversaire
        -- Positif = adversaire plus fort, Négatif = adversaire plus faible
        (adversaire_rating - mon_rating) AS diff_elo,

        -- Catégoriser l'adversaire
        CASE
            WHEN (adversaire_rating - mon_rating) > 100  THEN 'bien_plus_fort'
            WHEN (adversaire_rating - mon_rating) > 0    THEN 'plus_fort'
            WHEN (adversaire_rating - mon_rating) = 0    THEN 'egal'
            WHEN (adversaire_rating - mon_rating) > -100 THEN 'plus_faible'
            ELSE 'bien_plus_faible'
        END AS niveau_adversaire,

        -- Adversaire
        adversaire,
        adversaire_rating,

        -- Ouverture
        ouverture,

        -- Extraire la famille d'ouverture
        -- Ex: "Sicilian-Defense-Najdorf" → "Sicilian-Defense"
        SPLIT_PART(ouverture, '-', 1) || '-' ||
        SPLIT_PART(ouverture, '-', 2) AS famille_ouverture,

        -- PGN et position
        fen_final,
        pgn,

        inserted_at

    FROM source
)

SELECT * FROM enriched