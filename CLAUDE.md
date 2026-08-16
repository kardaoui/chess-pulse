# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Le projet est francophone : code, commentaires et échanges sont en français. Réponds en français.

## Vue d'ensemble

ChessPulse est un pipeline analytique sur les parties Chess.com de l'auteur : ingestion API → PostgreSQL → transformations dbt → Pipeline API (FastAPI). Orchestré par Airflow, dans Docker Compose.

**Ce dépôt vit dans WSL2** (`/home/kardaoui/chess-pulse`), sur Docker Engine natif — pas Docker Desktop. Une copie Windows obsolète existe sous `C:\Users\kardaoui\Desktop\Portfolio\chess-pulse` : **ce n'est pas le projet actif**, ne rien y modifier.

## Commandes

Toutes les commandes s'exécutent depuis WSL2. Depuis Windows, préfixer par `wsl.exe -- bash -lc '...'` — le CLI Docker de Windows cherche le pipe Docker Desktop et échouera.

### Infrastructure

```bash
docker compose up -d
docker compose logs -f airflow-scheduler
```

Services : Airflow `localhost:8080`, Pipeline API `localhost:8000`, PostgreSQL `localhost:5432`.

Les identifiants Airflow sont lus dans `.env` (`AIRFLOW_ADMIN_USER`, `AIRFLOW_ADMIN_PASSWORD`), non versionné. Le couple `admin/admin` mentionné ici auparavant a été révoqué.

Metabase a été retiré du `docker-compose.yml`, mais un conteneur `chesspulse_metabase` orphelin peut encore tourner (`docker rm -f chesspulse_metabase` pour l'éliminer).

### Scripts d'ingestion

Un venv existe à la racine : `source venv/bin/activate`.

```bash
python ingestion/load_to_postgres.py    # pipeline d'ingestion (incrémental, par compte)
python ingestion/load_chess.py          # mode test : API Chess.com sans toucher à Postgres
python ingestion/quality_checks.py      # Great Expectations sur raw.games (exit 1 si échec)
python ingestion/create_tables.py       # bootstrap manuel (rarement utile, voir ci-dessous)

python ingestion/migrate_001_compte_exclusion.py                        # migration de schéma
python ingestion/exclure_parties.py --compte X --dernieres 50 --simulation
```

`--simulation` affiche la plage visée sans rien écrire — **toujours l'utiliser avant d'exclure**.

### dbt

dbt tourne **dans le conteneur** : `profiles.yml` code en dur `host: postgres`, un nom résolu uniquement sur le réseau Docker.

```bash
docker compose exec -T airflow-scheduler dbt run  --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt
docker compose exec -T airflow-scheduler dbt test --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt

# un seul modèle
... dbt run --select stg_games --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt
```

### Airflow

```bash
docker compose exec airflow-scheduler airflow dags trigger chesspulse_pipeline
docker compose exec airflow-scheduler airflow tasks test chesspulse_pipeline ingestion_chess_com 2026-01-01
```

`airflow tasks test` exécute une tâche isolée sans planifier de DAG run — le moyen le plus rapide de déboguer.

Il n'y a **ni tests unitaires Python, ni linter**. La vérification passe par les blocs `if __name__ == "__main__"`, `dbt test` et `quality_checks.py`.

## Architecture

```
API Chess.com
  → load_chess.py        (extraction + normalisation)
  → load_to_postgres.py  (insertion incrémentale par compte)
  → raw.games            (PostgreSQL — fidèle à la source, tous formats)
  → quality_checks.py    (Great Expectations, bloquant)
  → public_staging.stg_games   (dbt, vue — applique le périmètre d'analyse)
  → public_mart.mart_*         (dbt, tables)
  → pipeline_api/              (FastAPI, port 8000)
```

DAG `chesspulse_pipeline` (`airflow/dags/chesspulse_dag.py`, `@daily`) :
`ingestion_chess_com >> quality_checks >> dbt_run >> dbt_test`. Il importe les fonctions de `ingestion/` via `sys.path.insert('/opt/airflow/ingestion')` — garder `run_pipeline()` et `run_quality_checks()` appelables sans argument.

### Séparation des responsabilités

- `db_utils.get_connexion()` — **unique** point de connexion PostgreSQL. Tout nouveau script doit l'utiliser.
- `load_chess.py` — ne parle qu'à l'API HTTP.
- `load_to_postgres.py` — ne parle qu'à la base.
- `pipeline_api/` — expose la donnée en REST ; ne réimplémente aucune logique d'ingestion.

### Le périmètre d'analyse est appliqué en un seul endroit

`stg_games` filtre `format = 'rapid' AND exclu_analyse = FALSE`. Marts, Pipeline API et futurs modèles ML en héritent sans avoir à le savoir.

**Corollaire : aucun consommateur ne doit lire `raw.games` directement.** Un endpoint qui le fait ré-expose les parties exclues et les parties `daily` — c'est un bug, pas un raccourci.

### Ingestion incrémentale

`run_pipeline()` lit `MAX(date)` filtré sur `(compte, format)`. Les deux filtres sont indispensables, et leur absence provoque une perte **silencieuse** :

- **par compte** — sinon un nouveau compte hérite du curseur de l'ancien et toutes ses archives antérieures sont ignorées ;
- **par format** — une partie `daily` se termine parfois des semaines après son premier coup. Comme `date` dérive de `end_time`, une seule partie par correspondance pousse le curseur un mois trop loin.

L'idempotence vient de `ON CONFLICT (uuid) DO NOTHING` — jamais `DO UPDATE`, sinon le marquage `exclu_analyse` posé manuellement serait écrasé à chaque ré-ingestion.

### Multi-comptes et exclusions

`raw.games.compte` (minuscules) identifie le compte interrogé — distinct de `mon_username`, qui reprend la casse de l'API.

`exclu_analyse` / `motif_exclusion` écartent des parties du périmètre. **On ne supprime jamais de ligne** : une suppression ferait reculer `MAX(date)` et la ré-ingestion suivante restaurerait les lignes effacées.

### L'Elo n'a de sens qu'à (compte, format) constants

Chess.com tient un classement **séparé par format**, et deux comptes ne démarrent pas au même Elo. Agréger `mon_rating` au-delà du couple `(compte, format)` produit des moyennes qui ne décrivent rien — c'est le grain de `mart_elo_mensuel`, et toute nouvelle analyse de classement doit le respecter. `progression_depuis_debut_compte` est la seule mesure comparable d'un compte à l'autre.

Corollaire pour la Phase 2 ML : `mon_rating` et `adversaire_rating` **absolus** ne sont pas transférables entre comptes — un modèle entraîné dessus apprendrait à séparer les comptes. Les features **relatives** (`diff_elo`, `niveau_adversaire`) le sont. Les premières parties d'un compte sont en classement provisoire (facteur K élevé) : leur `mon_rating` est volatil par construction.

`mart_elo_mensuel` calcule les premier/dernier Elo du mois via `ARRAY_AGG` ordonné, et non `FIRST_VALUE`/`LAST_VALUE` : une fonction fenêtre imposerait d'ajouter `date`, `heure` et `mon_rating` au `GROUP BY`, ce qui ramènerait le grain à une ligne par partie et annulerait l'agrégation mensuelle.

## Pièges connus

### Le DDL de raw.games existe en double

`db_utils.creer_tables_si_absentes()` (appelé au début de chaque `run_pipeline()`) **et** `create_tables.py` contiennent chacun un `CREATE TABLE IF NOT EXISTS raw.games`. Toute nouvelle colonne doit être ajoutée **aux deux**, sinon un déploiement neuf crée une table incomplète et l'`INSERT` échoue.

`IF NOT EXISTS` n'altère jamais une table existante : sur une base déjà peuplée, il faut un script `migrate_NNN_*.py` dédié.

### Deux fichiers d'environnement

`.env` et `.env.docker` sont identiques **sauf `POSTGRES_HOST`** (`localhost` vs `postgres`). Toute nouvelle variable — et tout changement de `CHESS_USERNAME` — doit être répercuté **dans les deux**.

### dbt : 1.5.0 dans le conteneur, 1.8.0 dans requirements.txt

C'est le conteneur qui exécute dbt, donc **la syntaxe cible est celle de 1.5**. En particulier, la clé des tests est `tests:` et non `data_tests:` (introduite en 1.8). Avec la mauvaise clé, dbt annonce `Found 3 models, 0 tests` et `dbt test` passe sans rien vérifier — un faux vert silencieux.

Vérifier systématiquement le nombre de tests trouvés dans la sortie de `dbt test`.

### Le dossier `great_expectations/` n'est pas versionné

Le contexte GE est régénéré localement. **Les règles de qualité qui font foi sont écrites en Python dans `quality_checks.py`** (`add_or_update_expectation_suite` + les appels `validator.expect_*`), pas dans les JSON du dossier. GE est épinglé en **0.18.0** (API "fluent datasources") et valide un DataFrame pandas, pas un datasource SQL.

### Bases de métadonnées séparées

Une seule instance PostgreSQL héberge `chesspulse` (données) et `airflow_meta` (métadonnées Airflow). Ne jamais faire pointer un outil sur `chesspulse` pour ses métadonnées.

### Dépendances du DAG

Elles sont installées dans le `Dockerfile`, pas via `ingestion/requirements.txt`. Ajouter une dépendance utilisée par le DAG implique de modifier le `Dockerfile` puis `docker compose build`.

## Documents d'architecture : cible ≠ état actuel

Les trois documents Markdown à la racine décrivent des décisions planifiées. À lire avant tout travail structurel, sans supposer qu'ils reflètent le dépôt.

- `chesspulse_decision_architecture_finale.md` — deux dépôts (`chess-pulse` = données + Pipeline API ; `chess-pulse-app` = ML + interface NiceGUI), migration WSL2, retrait de Metabase. **Fait :** migration WSL2, Pipeline API, retrait de Metabase du compose. **Reste :** le dépôt `chess-pulse-app`.
- `chesspulse_phase2_strategie.md` — les 4 modèles ML, features PGN (python-chess, `[%clk]`, Stockfish), table `public.features_games`, MLflow, `TimeSeriesSplit`. **Le chiffre de « 1012 parties » est périmé.** État réel : `midounesk` 1573 rapid (dont 50 exclues) + `midounesk26`, en croissance. `ml/` ne contient que des dossiers vides.
- `chesspulse_architecture_app.md` — architecture feature-based de la future app et endpoints attendus de la Pipeline API.

## Conventions

- Code, docstrings et commentaires en **français**, y compris les noms métier (`ma_couleur`, `mon_resultat`, `adversaire_rating`) — ne pas les angliciser.
- Alignement vertical des `=` dans les dicts et appels de configuration (voir `db_utils.py`, `chesspulse_dag.py`).
- Sorties console avec emojis et séparateurs `"=" * 55`.
- Messages de commit : préfixe conventionnel (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).
