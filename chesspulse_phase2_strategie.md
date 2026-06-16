# ChessPulse — Stratégie Phase 2 : Modèles ML

## 🎯 Objectif général

Construire 4 modèles ML par-dessus le pipeline de données (Phase 1) pour extraire de la valeur réelle depuis les parties Chess.com. L'objectif est **double** :
- **Portfolio** : montrer des compétences ML avancées (feature engineering, classification, clustering, recommandation, LLM)
- **Personnel** : apprendre aux échecs grâce à des insights basés sur ses propres données

---

## 🤖 Les 4 modèles

### Modèle 1 — Prédicteur de résultat (Classification)
**Question** : *"Quels facteurs expliquent le mieux mes résultats ?"*

Ce n'est pas juste prédire une victoire — c'est comprendre **quelles conditions me font gagner ou perdre** et construire un portrait de mon jeu basé sur 1012+ parties.

### Modèle 2 — Détecteur de patterns perdants (Clustering)
**Question** : *"Dans quelles situations est-ce que je m'effondre systématiquement ?"*

Regrouper automatiquement les défaites par profil sans supervision — "perdu en zeitnot", "perdu avec les noirs contre adversaire plus fort", etc.

### Modèle 3 — Recommandeur d'ouvertures
**Question** : *"Quelle ouverture devrais-je apprendre pour progresser ?"*

Basé sur le style de jeu et les scores par type de position — recommander ce qui convient **à ce joueur spécifiquement**, pas des conseils génériques.

### Modèle 4 — Coach IA personnel (LLM + Stockfish)
**Question** : *"Pourquoi ai-je perdu cette partie précisément ?"*

Combinaison données structurées + LLM : Stockfish analyse les coups, détecte les erreurs, un LLM génère un commentaire pédagogique personnalisé en français.

---

## 📊 Features — Modèle 1

### 4 sources de features

**Source 1 — Contexte** (déjà dans `stg_games`)
```
ma_couleur
mon_rating
adversaire_rating
diff_elo
moment_journee
ouverture
famille_ouverture
niveau_adversaire
```

**Source 2 — Structure de la partie** (python-chess sur PGN)
```
nb_coups             → durée de la partie
as_roque             → as-tu roqué ?
nb_captures          → agressivité
phase_finale         → la partie a-t-elle atteint une finale ?
coups_de_pion        → style positionnel ?
coups_de_piece       → style tactique ?
promotions           → une promotion a-t-elle eu lieu ?
repetitions          → positions répétées (indécision ?)
```

**Source 3 — Timing des coups** (annotations `[%clk]` dans le PGN)
```
temps_reflexion_moyen    → secondes de réflexion par coup en moyenne
temps_reflexion_max      → coup le plus long (hésitation ?)
temps_reflexion_min      → coup le plus rapide (automatisme ?)
temps_restant_final      → temps restant à la fin de la partie
en_zeitnot               → moins de 60 secondes restantes en fin de partie
ratio_temps_utilise      → % du temps total utilisé
acceleration_fin         → joue-t-on plus vite en fin de partie ?
```

**Source 4 — Qualité de jeu** (Stockfish, depth=10)
```
nb_blunders          → grosses erreurs (perte > 2 pions)
nb_mistakes          → erreurs moyennes
nb_inaccuracies      → imprécisions
accuracy_score       → score de précision global (0-100)
pire_coup            → pire erreur en centipawns
evaluation_ouverture → évaluation après les 10 premiers coups
evaluation_milieu    → évaluation en milieu de partie
evaluation_finale    → évaluation en finale
```

### Stockage des features
Toutes les features extraites sont stockées dans une **nouvelle table PostgreSQL** :
```sql
CREATE TABLE public.features_games (
    uuid TEXT PRIMARY KEY,
    -- toutes les features ci-dessus
    -- + target : mon_resultat
    extracted_at TIMESTAMP DEFAULT NOW()
);
```
L'extraction se fait **une seule fois** et est stockée — pas besoin de réanalyser à chaque entraînement.

---

## 🧠 Techniques ML choisies

### Algorithmes — 3 modèles en parallèle

| Modèle | Pourquoi |
|--------|----------|
| **Logistic Regression** | Baseline interprétable — coefficients clairs par feature |
| **Random Forest** | Capture les interactions entre features |
| **XGBoost** | Le plus performant sur petits datasets tabulaires |

Le meilleur devient le modèle de production. Les deux autres restent dans MLflow.

### Gestion du déséquilibre des classes
```
victoire : 48.5%
defaite  : 48.9%
nulle    :  2.5%  ← très peu représentée
```
Solutions retenues :
- `class_weight='balanced'` sur tous les modèles
- Envisager de regrouper `nulle` + `defaite` → `non-victoire` si les nulles restent trop rares

### Métriques d'évaluation
- **F1-score macro** — métrique principale (gère le déséquilibre)
- **Matrice de confusion** — visualise les erreurs par classe
- **ROC-AUC** — capacité discriminante globale
- ~~Accuracy~~ — trompeuse ici, à éviter

### Validation temporelle — TimeSeriesSplit
Les parties ne peuvent pas être mélangées aléatoirement — le temps compte.
```
Train : parties 2025-09 → 2026-04
Test  : parties 2026-05 → 2026-06
```
On utilise `TimeSeriesSplit` de scikit-learn pour respecter l'ordre chronologique.

---

## 🔄 Modèle évolutif — stratégie de réentraînement

### Le problème
Un modèle entraîné sur des parties à 700 Elo devient obsolète quand le joueur atteint 1000 Elo — les patterns changent.

### Solution retenue : Réentraînement mensuel + pondération temporelle
- **Réentraînement automatique** via Airflow chaque mois
- **Pondération temporelle** : les parties récentes ont plus de poids que les anciennes
- **Toutes les parties conservées** : l'historique complet est gardé pour voir l'évolution

### Tracking avec MLflow
Chaque version du modèle est loggée avec :
- Date d'entraînement
- Nombre de parties utilisées
- Hyperparamètres
- Métriques (F1, AUC, accuracy)

Comparaison possible dans le temps :
```
Modèle v1 (sept 2025, 1012 parties) : F1=0.52
Modèle v2 (déc 2025, 1500 parties)  : F1=0.58
Modèle v3 (juin 2026, 2000 parties)  : F1=0.63
```

---

## 🏗️ Architecture complète Phase 2

```
raw.games (PostgreSQL)
      ↓
public_staging.stg_games (dbt)
      ↓
Feature Engineering (Python + python-chess + Stockfish)
      ↓
public.features_games (PostgreSQL)
      ↓
┌─────────────────────────────────────┐
│  Entraînement (scikit-learn)        │
│  - Logistic Regression              │
│  - Random Forest                    │
│  - XGBoost                          │
└─────────────────────────────────────┘
      ↓
MLflow (tracking + model registry)
      ↓
FastAPI (endpoint de prédiction)
      ↓
Streamlit (interface utilisateur)
```

---

## 📅 Plan d'exécution

### Étape 1 — Features rapides (python-chess)
Extraire structure de la partie + timing depuis le PGN sans Stockfish.
Rapide — quelques secondes par partie.

### Étape 2 — Features Stockfish
Analyser chaque partie avec Stockfish (depth=10).
Plus lent — prévoir 2-3h pour 1012 parties.
Stockage immédiat en base pour ne pas refaire l'analyse.

### Étape 3 — Entraînement et comparaison
Entraîner les 3 modèles, comparer dans MLflow, sélectionner le meilleur.

### Étape 4 — Déploiement
Exposer le modèle via FastAPI + interface Streamlit.

### Étape 5 — Intégration Airflow
Ajouter le réentraînement mensuel au DAG existant.

---

## 💼 Ce que ça raconte à un recruteur

*"J'ai construit un pipeline de feature engineering depuis des données PGN brutes — analyse structurelle avec python-chess, analyse temporelle des coups, analyse tactique avec Stockfish — pour créer un dataset de 30+ features sur 1000+ parties. J'ai comparé 3 algorithmes de classification dans MLflow avec une validation temporelle stricte, et déployé le meilleur via FastAPI. Le modèle se réentraîne automatiquement chaque mois via Airflow au fur et à mesure que je joue de nouvelles parties."*
