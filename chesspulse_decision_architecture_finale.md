# ChessPulse — Décision d'architecture finale : Deux projets + Pipeline API

## 🎯 Contexte de la décision

Le projet ChessPulse a démarré comme un projet unique (`chess-pulse`) couvrant pipeline de données ET modèles ML ET app desktop. En réfléchissant à l'évolution vers la Phase 2 (ML) et Phase 3 (App Desktop), plusieurs scénarios d'architecture ont été évalués avant de trancher.

---

## 🔍 Scénarios envisagés

### Scénario 1 — Un seul projet qui grossit
Tout reste dans `chess-pulse` : pipeline + ML + app desktop dans un seul repo.
**Rejeté** : dilue le message portfolio (un projet ne peut pas bien représenter deux disciplines aussi distinctes que Data Engineering et Data Science/Full-stack).

### Scénario 2 — Deux projets avec bases PostgreSQL séparées + synchronisation
`chess-pulse` garde sa base. `chess-pulse-app` a sa propre base, remplie par copie périodique depuis la première.
**Rejeté** : duplication de données, risque de divergence, complexité de synchronisation sans bénéfice clair.

### Scénario 3 — Deux projets, infrastructures Docker séparées
Chaque projet a son propre `docker-compose.yml` et sa propre base.
**Rejeté** : recrée les problèmes de cohérence déjà rencontrés (conflits de ports, de schémas, de bases de métadonnées).

### Scénario 4 — Infrastructure partagée via repo dédié (`chesspulse-infra`)
Un 3e repo gère uniquement Docker Compose, les deux projets applicatifs s'y connectent.
**Rejeté** : trop de repos à maintenir pour un projet solo, complexité de gouvernance disproportionnée.

### Scénario 5 — Deux projets + Pipeline API ✅ RETENU
`chess-pulse` expose ses données via une API FastAPI dédiée. `chess-pulse-app` consomme cette API au lieu d'accéder directement à PostgreSQL.

---

## ✅ Décision retenue

**Deux projets distincts, connectés par une Pipeline API, sur une infrastructure WSL2 + Docker Engine unifiée.**

```
chess-pulse (migré vers WSL2 + Docker Engine)
  ├── PostgreSQL (raw, staging, mart)
  ├── Airflow (orchestration pipeline)
  ├── Metabase (dashboard démo portfolio)
  ├── Great Expectations (qualité)
  └── Pipeline API (FastAPI) ← NOUVEAU
        Expose : /games, /stats, /elo, /ouvertures...
                ↓ HTTP
chess-pulse-app (même environnement WSL2)
  ├── Backend FastAPI (ML, Stockfish, Coach LLM)
  │     → Appelle la Pipeline API pour lire les données
  ├── Frontend React (4 zones : pipeline, dashboard, échiquier, ML)
  └── Electron (packaging desktop)
```

---

## 💼 Justification de la décision

### Pourquoi deux projets séparés
- Deux entrées de portfolio distinctes et lisibles : un projet "Data Engineering/MLOps", un projet "Data Science/Full-stack ML"
- Permet de raconter deux histoires différentes selon le poste visé en entretien
- Évite de diluer le message d'un projet unique trop large

### Pourquoi une Pipeline API plutôt qu'un accès direct à PostgreSQL
- **Apprentissage** : pratiquer FastAPI dès la Phase 2, en conditions réelles, plutôt que d'attendre la Phase 3
- **Architecture orientée services** : pattern reconnu en entreprise (découplage producteur/consommateur), bon signal pour un poste MLOps/Data Engineer
- **Une seule source de vérité** : pas de duplication de données entre les deux projets
- **Découplage** : si la structure de la base évolue dans `chess-pulse`, seule l'API doit être mise à jour, pas l'app entière

### Pourquoi migrer vers WSL2 + Docker Engine
- Résout le vrai problème initial : Docker Desktop trop lourd pour un usage quotidien (RAM, démarrage manuel)
- Une seule infrastructure légère sert les deux projets (pas de duplication de Docker Compose)
- Argument portfolio supplémentaire : migration consciente d'un environnement de dev pour l'optimiser

---

## ⚠️ Inconvénients assumés (décision consciente, pas accidentelle)

| Inconvénient | Pourquoi on l'accepte quand même |
|---|---|
| Complexité accrue (2 repos, 1 API en plus) | Investissement pédagogique voulu — pas un projet "juste pour livrer vite" |
| Latence réseau ajoutée (HTTP vs SQL direct) | Négligeable au volume d'usage personnel actuel |
| Risque de casser l'existant pendant la migration WSL2 | Migration faite étape par étape, avec validation à chaque étape, infra actuelle non détruite avant validation complète |
| Plus de surface à maintenir (sync API ↔ app si schéma change) | Accepté comme coût d'apprentissage du pattern d'architecture orientée services |
| Peut sembler être de la sur-ingénierie pour un usage solo | Justifié explicitement par l'objectif d'apprentissage + diversification du portfolio, pas par une nécessité technique pure |

---

## 🗺️ Plan de migration — étapes validées

```
1. Installer WSL2 + Ubuntu
2. Installer Docker Engine dans Ubuntu (sans Docker Desktop)
3. Cloner chess-pulse (clone frais, pas un déplacement) dans WSL2
4. Configurer le .env dans cette nouvelle copie
5. Relancer docker-compose et vérifier que tout fonctionne identique
   (Airflow, dbt, Great Expectations, Metabase, dashboard)
6. Construire la Pipeline API (nouveau service FastAPI léger dans chess-pulse)
7. Documenter la migration dans le README (section Infrastructure)
8. Commit dédié : "infra: migrate from Docker Desktop to Docker Engine on WSL2"
9. Désinstaller Docker Desktop seulement après validation complète de tout
10. Démarrer chess-pulse-app (Phase 2 ML + Phase 3 App Desktop) en consommant la Pipeline API
```

**Principe directeur de la migration** : ne rien supprimer de l'existant tant que la nouvelle configuration n'est pas validée à 100%. Docker Desktop reste le filet de sécurité jusqu'à l'étape 9.

---

## 📌 Note sur la non-nécessité de backup PostgreSQL

Décision annexe prise pendant la réflexion : aucun backup PostgreSQL n'est nécessaire avant la migration.
- `raw.games` est reconstructible en relançant `load_to_postgres.py` (source de vérité = API Chess.com)
- `stg_games` et les marts sont reconstructibles en relançant `dbt run`
- Les questions/dashboard Metabase sont déjà documentées dans l'historique du projet et re-créables en ~10 minutes si besoin

---

## 💬 Pitch portfolio condensé

*"J'ai structuré le projet en deux composants distincts communiquant via une API REST plutôt qu'un partage direct de base de données — un pattern d'architecture orientée services qui isole les responsabilités : le pipeline de données reste propriétaire de ses données, l'application ML/desktop les consomme via une interface stable. J'ai aussi migré l'infrastructure de Docker Desktop vers Docker Engine sur WSL2 pour réduire l'empreinte mémoire en développement local et fiabiliser le démarrage automatique."*
