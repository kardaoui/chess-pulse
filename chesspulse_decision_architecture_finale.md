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
  ├── Great Expectations (qualité)
  └── Pipeline API (FastAPI) ← NOUVEAU
        Expose : /games, /stats, /elo, /ouvertures...
                ↓ HTTP
chess-pulse-app (même environnement WSL2)
  └── NiceGUI (sur FastAPI) ← interface unique, tout en Python
        → Appelle la Pipeline API pour lire les données
        → Exploration de données (Zone Dashboard)
        → Échiquier interactif + coach (Zone Board, composant JS intégré)
        → Modèles ML (Zone ML)
        → Packaging desktop natif (remplace Electron)
```

Metabase est retiré du projet (déjà couvert par un autre projet de l'auteur, sans valeur portfolio additionnelle ici).

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
   (Airflow, dbt, Great Expectations)
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

## 🎯 Interface de `chess-pulse-app` : historique de la réflexion et décision finale

Cette section trace le cheminement réel de la décision — utile pour comprendre pourquoi on n'est pas parti directement sur la solution retenue.

**Point de départ.** L'app devait combiner exploration de données (comprendre le jeu) et échiquier interactif (s'exercer, coach). Une distinction entre "explorer" et "s'exercer" a été formulée, ce qui a fait envisager deux outils différents (Streamlit pour l'un, React pour l'autre), puis temporairement trois projets séparés (`chess-pulse-dash` + `chess-pulse-app`).

**Correction de trajectoire.** Cette séparation en deux ou trois surfaces contredisait un critère plus important, exprimé explicitement : une seule interface, simple, pour gérer les deux usages. Le choix de deux technos différentes (Python pour l'un, JS pour l'autre) était la vraie cause du tiraillement, pas une nécessité produit.

**Recherche et décision.** Évaluation des frameworks Python capables de couvrir exploration de données ET interface réactive (échiquier fluide) dans une seule techno : Streamlit (écarté — réexécute tout le script à chaque interaction, inadapté à un échiquier fluide), Dash, Reflex, **NiceGUI (retenu)**.

**Décision finale : NiceGUI, une seule interface, tout en Python.**
- Construit sur FastAPI/Starlette/Uvicorn — cohérent avec la Pipeline API déjà en FastAPI
- Rendu réactif par WebSocket natif, pas de réexécution de script (contrairement à Streamlit) — adapté à un échiquier fluide
- Composants natifs pour les graphiques d'exploration (`ui.plotly`, intégration Pandas/Matplotlib)
- Mode desktop natif disponible — remplace le rôle d'Electron, sans dépendre de React/JS pour l'essentiel de l'app
- Seul point de sortie du pur Python, assumé : l'échiquier interactif nécessite l'intégration d'une librairie JS dédiée (ex. chessboard.js) via le mécanisme d'extension de NiceGUI

**Pourquoi pas React (finalement).** React avait été choisi initialement comme "le meilleur sur le papier" pour une app desktop, indépendamment d'un attachement à apprendre cette techno précise. Une fois établi que NiceGUI couvre les deux besoins (exploration + échiquier fluide) en restant en Python — la techno que l'auteur veut réellement approfondir pour son objectif MLOps/Data Engineer — React n'apportait plus d'avantage décisif, seulement une complexité supplémentaire (deux langages, contrat API interne, dépendance forte à Claude Code pour tout le front).

**Metabase.** Retiré du projet — déjà utilisé sur un autre projet de l'auteur, donc sans valeur portfolio additionnelle ici.

---

## 💬 Pitch portfolio condensé (mis à jour)

*"J'ai structuré le projet en deux composants distincts communiquant via une API REST plutôt qu'un partage direct de base de données — un pattern d'architecture orientée services. Pour l'interface de l'app, j'ai évalué plusieurs frameworks Python (Streamlit, Dash, NiceGUI) avant de retenir NiceGUI : il couvre à la fois l'exploration de données et un échiquier interactif fluide dans une seule interface réactive par WebSocket, en restant intégralement en Python — cohérent avec mon objectif MLOps/Data Engineer. Le tout sur une infrastructure Docker Engine/WSL2 légère, migrée depuis Docker Desktop pour réduire l'empreinte mémoire."*
