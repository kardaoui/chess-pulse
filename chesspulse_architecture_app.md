# ChessPulse — Architecture App Desktop

## 🎯 Vision

Une application desktop **tout-en-un** qui centralise toutes les fonctionnalités ChessPulse dans une interface moderne et colorée. L'objectif est d'avoir un **cockpit personnel** pour piloter ses données d'échecs, analyser ses parties et exploiter les modèles ML — sans jongler entre plusieurs outils.

> Metabase reste disponible pour les démonstrations portfolio, mais l'app desktop est l'outil du quotidien.

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
| Frontend | React + Electron | Interface desktop moderne |
| Backend | FastAPI (Python) | API REST + logique métier |
| Base de données | PostgreSQL | Stockage des parties et features |
| ML | scikit-learn + MLflow | Modèles + tracking |
| Analyse | Stockfish + python-chess | Analyse des coups |
| Communication | REST API + WebSocket | Frontend ↔ Backend |

**Choix frontend** : React géré par Claude Code (pas l'axe d'apprentissage prioritaire), Python géré manuellement (cœur du projet).

---

## 🏛️ Architecture — Feature-based

Chaque fonctionnalité est **isolée dans son propre module**. Ajouter une nouvelle zone ne nécessite pas de modifier l'existant.

```
chesspulse-app/
├── backend/                        ← FastAPI Python
│   ├── main.py                     ← point d'entrée FastAPI
│   ├── features/                   ← une feature = un dossier isolé
│   │   ├── pipeline/               ← Zone 1 : sync Chess.com
│   │   │   ├── router.py           ← endpoints API
│   │   │   └── service.py          ← logique métier
│   │   ├── dashboard/              ← Zone 2 : KPIs
│   │   │   ├── router.py
│   │   │   └── service.py
│   │   ├── board/                  ← Zone 3 : échiquier + analyse
│   │   │   ├── router.py
│   │   │   └── service.py
│   │   └── ml/                     ← Zone 4 : modèles ML
│   │       ├── router.py
│   │       └── service.py
│   └── core/                       ← partagé par toutes les features
│       ├── database.py             ← connexion PostgreSQL
│       ├── config.py               ← variables d'environnement
│       └── stockfish.py            ← connexion Stockfish
│
└── frontend/                       ← React + Electron
    ├── src/
    │   ├── App.jsx                 ← point d'entrée React
    │   ├── features/               ← miroir de la structure backend
    │   │   ├── pipeline/
    │   │   ├── dashboard/
    │   │   ├── board/
    │   │   └── ml/
    │   └── shared/                 ← composants réutilisables
    │       ├── components/         ← boutons, cards, graphiques...
    │       └── hooks/              ← logique React partagée
    └── electron/                   ← configuration app desktop
```

---

## 🔌 API REST — Contrat Frontend / Backend

Le frontend React ne sait pas comment fonctionne Python. Le backend Python ne sait pas comment fonctionne React. Ils communiquent uniquement via ces endpoints :

### Zone 1 — Pipeline
```
POST /api/pipeline/sync
  → Lance la synchronisation Chess.com
  → Retourne : { nouvelles_parties: 15, total: 1027, statut: "success" }

GET  /api/pipeline/status
  → Statut de la dernière synchronisation
  → Retourne : { derniere_sync: "2026-06-13", total_parties: 1012 }
```

### Zone 2 — Dashboard
```
GET  /api/dashboard/stats
  → KPIs globaux
  → Retourne : { total_parties, victoires, defaites, nulles, winrate }

GET  /api/dashboard/elo
  → Évolution Elo par mois
  → Retourne : [{ mois: "2025-09", elo_moyen: 727 }, ...]

GET  /api/dashboard/ouvertures
  → Winrate par ouverture
  → Retourne : [{ ouverture, parties, winrate }, ...]

GET  /api/dashboard/moments
  → Winrate par moment de la journée
  → Retourne : [{ moment, parties, winrate }, ...]
```

### Zone 3 — Échiquier
```
GET  /api/board/games
  → Liste des parties avec filtres optionnels
  → Params : ?resultat=defaite&format=rapid&limit=20
  → Retourne : [{ uuid, date, adversaire, resultat, ouverture }, ...]

GET  /api/board/game/{uuid}
  → Détail complet d'une partie + analyse Stockfish
  → Retourne : { pgn, coups, evaluations, blunders, accuracy }
```

### Zone 4 — ML
```
POST /api/ml/predict
  → Prédit le résultat d'une partie
  → Body : { ma_couleur, adversaire_rating, moment_journee, ouverture }
  → Retourne : { prediction, probabilites, features_importantes }

POST /api/ml/coach
  → Analyse LLM d'une partie
  → Body : { uuid }
  → Retourne : { analyse_texte, erreurs_principales, conseils }

GET  /api/ml/recommandations
  → Ouvertures recommandées selon le profil
  → Retourne : [{ ouverture, score_compatibilite, raison }, ...]

GET  /api/ml/clusters
  → Profil des défaites récentes
  → Retourne : { cluster_principal, description, parties_similaires }
```

---

## ⚡ Temps réel — WebSocket

Pour la progression de la synchronisation et l'analyse Stockfish (opérations longues), on utilise WebSocket :

```
WS /ws/pipeline/sync    ← progression en temps réel
  → { etape: "ingestion", progression: 45, message: "450/1012 parties" }

WS /ws/board/analyze    ← analyse Stockfish coup par coup
  → { coup: 15, evaluation: 0.8, meilleur_coup: "Nf3" }
```

---

## 🔄 Principe d'évolutivité

Ajouter une **Zone 5** (ex: Agenda d'entraînement) :

```
1. Créer backend/features/training/router.py
2. Créer backend/features/training/service.py
3. Enregistrer le router dans main.py
4. Créer frontend/src/features/training/ (Claude Code)
```

**Aucun fichier existant n'est modifié.** Le module s'intègre naturellement.

---

## 🚀 Ordre de développement recommandé

```
Phase 1 (déjà fait)  → Pipeline de données + PostgreSQL + dbt + Airflow
Phase 2 (en cours)   → Modèles ML (classification, clustering, recommandation, LLM)
Phase 3 (à venir)    → Backend FastAPI (une feature à la fois)
Phase 4 (à venir)    → Frontend React + Electron (Claude Code)
Phase 5 (à venir)    → Intégration complète + tests + packaging
```

---

## 💼 Ce que ça raconte à un recruteur

*"J'ai conçu une application desktop full-stack avec une architecture feature-based évolutive — backend FastAPI Python exposant une API REST, frontend React packagé avec Electron, communication temps réel via WebSocket pour les opérations longues. Chaque fonctionnalité est isolée dans son propre module, ce qui permet d'ajouter de nouvelles features sans modifier l'existant."*
