-- Bases de métadonnées, créées au premier démarrage de PostgreSQL.
--
-- L'image postgres ne crée que la base POSTGRES_DB (chesspulse). Airflow
-- pointe sur airflow_meta : sans ce script, `airflow db init` échoue sur
-- un clone neuf et le conteneur airflow-init boucle indéfiniment.
--
-- Ce script ne s'exécute que sur un volume de données vierge. Sur une
-- installation existante, créer la base à la main :
--   docker exec chesspulse_postgres psql -U chesspulse -c "CREATE DATABASE airflow_meta;"

CREATE DATABASE airflow_meta;
