# ChessPulse — Architecture App Desktop

## 🎯 Vision

Une application desktop **tout-en-un** qui centralise toutes les fonctionnalités ChessPulse dans une interface moderne et colorée. L'objectif est d'avoir un **cockpit personnel** pour piloter ses données d'échecs, analyser ses parties et exploiter les modèles ML — sans jongler entre plusieurs outils.

> Metabase est retiré du projet : déjà utilisé sur un autre projet de l'auteur, il n'apporte pas de valeur portfolio supplémentaire ici.

---

## 🔄 Décision technologique : NiceGUI plutôt que React + Electron

**Contexte de la décision.** L'app devait combiner deux besoins perçus comme contradictoires : explorer librement les données (comprendre le jeu) et s'exercer avec un échiquier fluide (pratique, coach). Cela a mené à envisager deux outils différents (Streamlit + React), puis jusqu'à trois projets séparés. Après évaluation, le vrai critère a été identifié : une seule interface cohérente, capable de couvrir l'exploration de données **et** un échiquier interactif fluide.

**Pourquoi pas Streamlit.** Réexécute tout le script à chaque interaction — excellent pour des dashboards simples, inadapté à une interface réactive comme un échiquier coup par coup avec annotations du coach.

**Pourquoi pas React + Electron.** Aurait rempli les deux besoins, mais imposait une deuxième techno (JS) entièrement déléguée à Claude Code, sans valeur d'apprentissage pour l'objectif MLOps/Data Engineer visé, et créait une vraie frontière frontend/backend à maintenir (deux langages, un contrat API interne, deux bases de code).

**Pourquoi NiceGUI.** Construit directement sur FastAPI/Starlette/Uvicorn côté serveur, avec un rendu réactif par WebSocket (pas de réexécution du script à chaque clic, contrairement à Streamlit). Couvre l'exploration de données (composants `ui.plotly`, intégration Pandas/Matplotlib) **et** une interface fluide pour l'échiquier, en restant intégralement en Python. Peut tourner en fenêtre desktop native (remplace le rôle d'Electron) ou en navigateur. Seul point de vigilance assumé : l'échiquier interactif n'est pas un composant natif et nécessite l'intégration d'une librairie JS d'échiquier (ex. chessboard.js) via le mécanisme d'extension de NiceGUI — c'est le seul endroit du projet où l'on sort du pur Python, et c'est délibéré.

---

## 🖥️ Les 4 zones de l'interface

### Zone 1 — Pipeline
Synchronisation des parties Chess.com en un clic.
- Bouton **"Sync mes parties"**
- Indicateur de progression en temps réel
- Résumé après sync ("15 nouvelles parties chargées")
- Historique des dernières synchronisations

### Zone 2 — Dashboard
KPIs personnels intégrés directement dans l'app.
- Évolution de l'Elo dans le temps
- Winrate par ouverture
- Winrate par moment de la journée
- Stats globales (total parties, victoires, défaites, nulles)

### Zone 3 — Échiquier
Visualisation et analyse des parties.
- Liste des parties jouées avec filtres
- Replay coup par coup sur un échiquier interactif
- Erreurs Stockfish annotées directement sur l'échiquier (blunders, mistakes, inaccuracies)
- Évaluation de la position après chaque coup

### Zone 4 — Modèles ML
Exploitation des modèles d'intelligence artificielle.
- **Prédicteur** : probabilité de victoire selon les conditions
- **Clustering** : dans quel profil de défaite tombent mes parties récentes
- **Recommandeur** : ouvertures suggérées selon mon style
- **Coach LLM** : analyse textuelle d'une partie en français

---

## 🏗️ Stack technique

| Couche | Technologie | Rôle |
|--------|-------------|------|
| Interface | NiceGUI | UI réactive, exploration + échiquier + ML, en pur Python |
| Backend / logique | FastAPI (sous-jacent à NiceGUI) + Python | Logique métier, ML, Stockfish |
| Base de données | PostgreSQL (dans `chess-pulse`) | Stockage des parties et features |
| Accès aux données | Pipeline API (`chess-pulse`) | `chess-pulse-app` ne touche jamais PostgreSQL directement |
| ML | scikit-learn + MLflow | Modèles + tracking |
| Analyse | Stockfish + python-chess | Analyse des coups |
| Échiquier | Librairie JS (ex. chessboard.js) intégrée via NiceGUI | Seul composant non-Python du projet |
| Packaging desktop | NiceGUI natif (`ui.run(native=True)`) | Remplace Electron |

**Choix techno** : tout le projet `chess-pulse-app` reste en Python, y compris l'interface — cohérent avec l'objectif d'apprentissage MLOps/Data Engineer et avec la Pipeline API déjà en FastAPI.

---

## 🏛️ Architecture — Feature-based

Chaque fonctionnalité est **isolée dans son propre module**. Ajouter une nouvelle zone ne nécessite pas de modifier l'existant. Avec NiceGUI, il n'y a plus de séparation frontend/backend en deux langages : chaque feature regroupe sa logique (`service.py`) et sa page d'interface (`page.py`) dans le même dossier, dans la même techno.

```
chess-pulse-app/
├── main.py                         ← point d'entrée NiceGUI/FastAPI
├── features/                       ← une feature = un dossier isolé
│   ├── pipeline/                   ← Zone 1 : sync Chess.com
│   │   ├── service.py              ← logique métier (appelle la Pipeline API)
│   │   └── page.py                 ← interface NiceGUI (bouton, progression)
│   ├── dashboard/                  ← Zone 2 : KPIs et exploration
│   │   ├── service.py
│   │   └── page.py                 ← graphiques ui.plotly
│   ├── board/                      ← Zone 3 : échiquier + analyse
│   │   ├── service.py              ← appel Stockfish, python-chess
│   │   ├── page.py                 ← intégration composant échiquier JS
│   │   └── chessboard_component.py ← extension NiceGUI (le seul JS du projet)
│   └── ml/                         ← Zone 4 : modèles ML
│       ├── service.py              ← prédiction, clustering, reco, coach
│       └── page.py
├── core/                           ← partagé par toutes les features
│   ├── pipeline_api_client.py      ← client HTTP vers la Pipeline API
│   ├── config.py                   ← variables d'environnement
│   └── stockfish.py                ← connexion Stockfish
└── mlflow/                         ← tracking des modèles
```

Le rôle des fichiers `service.py` (logique, données, ML) reste strictement séparé de `page.py` (affichage NiceGUI), pour garder une frontière claire à l'intérieur même d'un projet unifié — même sans frontière de langage, la séparation des responsabilités reste une bonne pratique.

---

## 🔌 Flux de données — Pipeline API (externe, vers `chess-pulse`)

Avec NiceGUI, il n'existe plus de frontière réseau *interne* entre interface et logique (tout tourne dans le même process Python). La seule API REST qui subsiste est **externe** : celle qui relie `chess-pulse-app` à `chess-pulse`, exactement comme prévu dans la décision d'architecture à deux projets.

```
features/*/service.py  →  core/pipeline_api_client.py  →  HTTP  →  Pipeline API (chess-pulse)  →  PostgreSQL
```

Endpoints attendus côté Pipeline API (construite dans `chess-pulse`, consommée ici) :

```
GET  /games                  → liste des parties avec filtres
GET  /games/{uuid}           → détail d'une partie (pgn, contexte)
GET  /stats                  → KPIs globaux
GET  /stats/elo              → évolution Elo par mois
GET  /stats/ouvertures       → winrate par ouverture
GET  /stats/moments          → winrate par moment de la journée
POST /sync                   → déclenche une synchronisation Chess.com
```

Chaque `service.py` de `chess-pulse-app` appelle ces endpoints via `core/pipeline_api_client.py` ; aucune feature ne se connecte directement à PostgreSQL.

---

## ⚡ Temps réel — natif à NiceGUI

NiceGUI maintient une connexion WebSocket par session de façon native (pas de configuration manuelle comme avec une API REST classique). Pour les opérations longues (sync Chess.com, analyse Stockfish), on met à jour les composants d'interface directement depuis le code Python pendant l'exécution :

```python
# features/pipeline/page.py
progress = ui.linear_progress(value=0)
label = ui.label("En attente...")

async def lancer_sync():
    async for etat in pipeline_service.sync_avec_progression():
        progress.value = etat.pourcentage
        label.text = etat.message
```

Pas de protocole à définir manuellement (pas de `WS /ws/...`) — NiceGUI pousse les mises à jour au navigateur dès que les variables Python liées à l'interface changent.

---

## 🔄 Principe d'évolutivité

Ajouter une **Zone 5** (ex: Agenda d'entraînement) :

```
1. Créer features/training/service.py (logique)
2. Créer features/training/page.py (interface NiceGUI)
3. Enregistrer la page dans main.py
```

**Aucun fichier existant n'est modifié.** Le module s'intègre naturellement — et plus besoin de coordonner deux bases de code (backend + frontend) pour une seule nouvelle fonctionnalité.

---

## 🚀 Ordre de développement recommandé

```
Phase 1 (déjà fait)  → Pipeline de données + PostgreSQL + dbt + Airflow (chess-pulse)
Phase 2 (en cours)   → Modèles ML (classification, clustering, recommandation, LLM)
                        + Pipeline API (FastAPI, dans chess-pulse)
                        + ChessPulse Dash (NiceGUI, exploration des données, dans chess-pulse-app)
Phase 3 (à venir)    → Zones Board (échiquier) et ML intégrées dans chess-pulse-app
Phase 4 (à venir)    → Packaging desktop (NiceGUI natif) + tests + polish
```

---

## 💼 Ce que ça raconte à un recruteur

*"J'ai conçu une application desktop avec une architecture feature-based évolutive, entièrement en Python (NiceGUI sur FastAPI) — exploration de données, échiquier interactif et modèles ML dans une seule interface réactive par WebSocket. J'ai consciemment évalué et écarté React/Electron : sur ce projet, une stack unifiée en Python servait mieux l'objectif d'apprentissage MLOps que de déléguer le frontend à un outil externe. La donnée reste découplée via une Pipeline API consommée en HTTP, jamais d'accès direct à la base depuis l'app."*
