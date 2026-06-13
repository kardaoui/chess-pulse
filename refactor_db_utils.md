# Refactoring — Centraliser la connexion PostgreSQL + Ajouter quality_checks.py

## Contexte

Le projet `ingestion/` contient `load_chess.py`, `load_to_postgres.py`, et un nouveau fichier `quality_checks.py` à créer.

`load_to_postgres.py` contient déjà une fonction `get_connexion()` qui se connecte à PostgreSQL via les variables d'environnement (`.env`). Cette fonction est dupliquée — on veut la centraliser dans un module partagé.

---

## Tâches à réaliser

### 1. Créer `ingestion/db_utils.py`

Nouveau fichier contenant **uniquement** cette fonction :

```python
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()


def get_connexion():
    """
    Retourne une connexion PostgreSQL.
    Utilisée par tous les scripts du projet.
    """
    return psycopg2.connect(
        host     = os.getenv("POSTGRES_HOST"),
        port     = os.getenv("POSTGRES_PORT"),
        dbname   = os.getenv("POSTGRES_DB"),
        user     = os.getenv("POSTGRES_USER"),
        password = os.getenv("POSTGRES_PASSWORD")
    )
```

---

### 2. Modifier `ingestion/load_to_postgres.py`

- Supprimer la définition locale de `get_connexion()` et ses imports associés (`psycopg2`, `load_dotenv`, `os` ne sont plus nécessaires **sauf** si utilisés ailleurs dans le fichier — vérifier avant de supprimer).
- Ajouter l'import : `from db_utils import get_connexion`
- Garder le `sys.path.append` existant pour l'import de `load_chess`
- Vérifier que le reste du fichier fonctionne toujours avec cette fonction importée (le code qui appelle `get_connexion()` ne doit pas changer)

---

### 3. Créer `ingestion/quality_checks.py`

```python
import great_expectations as gx
import pandas as pd
import sys
from db_utils import get_connexion


def charger_donnees():
    """
    Charge la table raw.games dans un DataFrame pandas.
    Great Expectations va vérifier ce DataFrame.
    """
    conn = get_connexion()
    df = pd.read_sql("SELECT * FROM raw.games", conn)
    conn.close()
    return df


def run_quality_checks():
    """
    Lance toutes les vérifications de qualité sur raw.games.
    Retourne True si tout est OK, False sinon.
    """
    print("📂 Chargement des données depuis PostgreSQL...")
    df = charger_donnees()
    print(f"✅ {len(df)} lignes chargées\n")

    context = gx.get_context()

    data_source = context.sources.add_or_update_pandas(name="chesspulse_source")
    data_asset = data_source.add_dataframe_asset(name="raw_games", dataframe=df)

    batch_request = data_asset.build_batch_request()

    suite_name = "chesspulse_raw_games_suite"
    context.add_or_update_expectation_suite(suite_name)

    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=suite_name,
    )

    print("🧪 RÈGLES DE QUALITÉ — DÉFINITION")
    print("=" * 55)

    print("  1. uuid ne doit jamais être null")
    validator.expect_column_values_to_not_be_null("uuid")

    print("  2. uuid doit être unique")
    validator.expect_column_values_to_be_unique("uuid")

    print("  3. mon_resultat doit être victoire/defaite/nulle")
    validator.expect_column_values_to_be_in_set(
        "mon_resultat", ["victoire", "defaite", "nulle"]
    )

    print("  4. ma_couleur doit être white/black")
    validator.expect_column_values_to_be_in_set(
        "ma_couleur", ["white", "black"]
    )

    print("  5. mon_rating doit être entre 100 et 3000")
    validator.expect_column_values_to_be_between(
        "mon_rating", min_value=100, max_value=3000
    )

    print("  6. adversaire_rating doit être entre 100 et 3000")
    validator.expect_column_values_to_be_between(
        "adversaire_rating", min_value=100, max_value=3000
    )

    print("  7. date ne doit jamais être null")
    validator.expect_column_values_to_not_be_null("date")

    print("  8. heure_int doit être entre 0 et 23")
    validator.expect_column_values_to_be_between(
        "heure_int", min_value=0, max_value=23
    )

    print("\n🔍 EXÉCUTION DES VÉRIFICATIONS...")
    print("=" * 55)

    results = validator.validate()

    total_checks = len(results.results)
    success_checks = sum(1 for r in results.results if r.success)
    failed_checks = total_checks - success_checks

    print(f"\n📊 RÉSULTATS")
    print(f"  ✅ Règles passées : {success_checks}/{total_checks}")
    print(f"  ❌ Règles échouées : {failed_checks}/{total_checks}")

    if failed_checks > 0:
        print(f"\n⚠️  DÉTAIL DES ÉCHECS :")
        for r in results.results:
            if not r.success:
                expectation_type = r.expectation_config.expectation_type
                column = r.expectation_config.kwargs.get("column", "")
                unexpected_count = r.result.get("unexpected_count", "N/A")
                print(f"  - {expectation_type} sur '{column}'")
                print(f"    → {unexpected_count} valeurs invalides")

    return results.success


if __name__ == "__main__":
    print("=" * 55)
    print("🧪 CHESSPULSE — QUALITÉ DES DONNÉES")
    print("=" * 55 + "\n")

    success = run_quality_checks()

    print("\n" + "=" * 55)
    if success:
        print("✅ TOUTES LES VÉRIFICATIONS SONT PASSÉES")
        print("=" * 55)
        sys.exit(0)
    else:
        print("❌ CERTAINES VÉRIFICATIONS ONT ÉCHOUÉ")
        print("=" * 55)
        sys.exit(1)
```

---

### 4. Mettre à jour `ingestion/requirements.txt`

Ajouter ces lignes si elles n'existent pas déjà :

```
great-expectations==0.18.0
pandas
```

---

### 5. Vérification finale

**Après** toutes les modifications, lancer ces commandes pour vérifier que rien n'est cassé :

```powershell
python ingestion/load_to_postgres.py
```
→ doit afficher le résumé du pipeline comme avant

```powershell
python ingestion/quality_checks.py
```
→ doit afficher les 8 règles et leurs résultats

Si une des deux commandes échoue, afficher l'erreur complète avant de continuer.

---

## ⚠️ Restrictions

**Ne pas toucher** aux fichiers suivants :
- `load_chess.py` (sauf si l'import `get_connexion` y était présent par erreur, ce qui n'est pas censé être le cas)
- `create_tables.py`
- `explore_data.py`
- tous les fichiers `dbt/` et `airflow/`
