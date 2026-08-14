# Décisions d'architecture — couche données

Ce document consigne les arbitrages structurants du pipeline de données, au format ADR (*Architecture Decision Record*) : contexte observé, alternatives écartées, décision, conséquences.

Il complète les documents de vision à la racine du dépôt, qui traitent d'un autre niveau :

| Document | Portée |
|---|---|
| `chesspulse_decision_architecture_finale.md` | Découpage en deux dépôts, Pipeline API, infrastructure |
| `chesspulse_architecture_app.md` | Interface de `chess-pulse-app` (NiceGUI) |
| `chesspulse_phase2_strategie.md` | Modèles ML et feature engineering |
| **`docs/decisions.md`** *(ce fichier)* | **Modélisation et intégrité de la couche données** |

Toutes les décisions ci-dessous datent du **2026-08-14** et sont **actives**.

---

## ADR 001 — Le périmètre analytique est limité au format `rapid`

### Contexte

Chess.com maintient un **classement séparé par format** (bullet, blitz, rapid, daily). L'historique contenait 1573 parties `rapid` et 5 parties `daily`, ces dernières avec un Elo de 236 contre ~700 en rapid — deux échelles sans rapport.

Le problème dépasse le classement. La date d'une partie est dérivée de son horodatage de fin :

```python
date_partie = datetime.fromtimestamp(partie["end_time"])
```

Pour une partie live, cet horodatage correspond au moment où elle a été jouée. Pour une partie **par correspondance**, qui s'étale sur des jours ou des semaines, il correspond au dernier coup. Les colonnes `date`, `heure`, `heure_int` et `moment_journee` étaient donc dénuées de sens pour ces parties — alors que `moment_journee` alimente l'analyse « à quelle heure de la journée mes résultats sont-ils les meilleurs ? ».

### Alternatives écartées

**Conserver tous les formats et gérer la distinction dans chaque requête.** Rejeté : impose de se souvenir du piège à chaque nouvelle analyse, et le premier oubli produit un résultat faux sans aucun signal.

**Supprimer les parties `daily` de la base.** Rejeté : `raw.games` doit rester une copie fidèle de la source. Le filtrage relève du périmètre d'analyse, pas de l'ingestion.

### Décision

`raw.games` continue d'ingérer tous les formats. Le filtre `format = 'rapid'` est appliqué dans `stg_games` (voir ADR 006).

### Conséquences

- Les analyses temporelles portent uniquement sur des parties dont l'horodatage a un sens.
- Les agrégats d'Elo ne mélangent plus deux échelles.
- Élargir le périmètre plus tard ne demande qu'une modification de `stg_games`, sans réingestion.

---

## ADR 002 — Le curseur d'ingestion est scopé par `(compte, format)`

### Contexte

L'ingestion est incrémentale : elle lit la date de la dernière partie connue, puis ne télécharge que les archives mensuelles postérieures. Ce curseur était global :

```sql
SELECT MAX(date) FROM raw.games;
```

Deux défauts, tous deux provoquant une perte **silencieuse** de données :

**Changement de compte.** Le nouveau compte hérite du curseur de l'ancien. Mesuré sur le cas réel : la bascule vers un second compte aurait ignoré 23 parties, sans erreur ni avertissement.

**Parties par correspondance.** Une partie `daily` terminée après la dernière partie live pousse le curseur au mois suivant, faisant sauter une archive mensuelle entière. Dans les faits, 2 parties `daily` suffisaient à provoquer la perte décrite ci-dessus.

### Alternatives écartées

**Filtrer sur `mon_username`, colonne déjà existante.** Rejeté : cette colonne provient de la réponse de l'API et conserve la casse renvoyée par Chess.com. La comparaison aurait dépendu d'une normalisation implicite. `compte` exprime explicitement « le compte interrogé » et est stocké en minuscules.

**Repartir d'une base vide à chaque changement de compte.** Rejeté : détruit l'historique, qui constitue le jeu d'entraînement de la Phase 2.

### Décision

Ajout d'une colonne `compte`. Le curseur devient :

```sql
SELECT MAX(date) FROM raw.games
WHERE compte = %s AND format = ANY(%s);
```

### Conséquences

- Le pipeline supporte N comptes sans interférence entre eux.
- L'idempotence reste assurée par `ON CONFLICT (uuid) DO NOTHING`.
- Un index `(compte, format, date)` soutient le curseur.

---

## ADR 003 — Les parties sont exclues par marquage, jamais par suppression

### Contexte

Une période de l'historique a été jugée non représentative du jeu de l'auteur et devait sortir du périmètre analytique, afin de ne pas biaiser les modèles de la Phase 2.

Le réflexe — supprimer les lignes — est ici **auto-annulant**. Supprimer les parties les plus récentes fait *reculer* `MAX(date)` ; la prochaine exécution du pipeline retélécharge le mois concerné et réinsère exactement ce qui venait d'être effacé. Le nettoyage se défait tout seul, sans que rien ne l'indique.

### Alternatives écartées

**`DELETE` + arrêt définitif de l'interrogation du compte concerné.** Fonctionne, mais par accident : la correction ne tient qu'à une configuration externe, pas à une propriété du schéma. Réinterroger ce compte un jour ramènerait les lignes.

**`ON CONFLICT DO UPDATE` pour forcer l'état à chaque ingestion.** Rejeté : écraserait tout marquage manuel à chaque exécution.

### Décision

Deux colonnes : `exclu_analyse BOOLEAN NOT NULL DEFAULT FALSE` et `motif_exclusion TEXT`. Le filtrage a lieu dans `stg_games` (ADR 006). Un script dédié, `ingestion/exclure_parties.py`, applique le marquage et propose systématiquement un mode `--simulation`.

`ON CONFLICT DO NOTHING` — et non `DO UPDATE` — garantit qu'une ligne existante n'est jamais réécrite : le marquage survit à toutes les réingestions.

### Conséquences

- L'exclusion est **réversible** (`--annuler`) et **traçable** (`motif_exclusion`).
- `raw.games` reste une copie fidèle de la source ; le jugement analytique est un attribut, pas une amputation.
- Réviser la borne d'exclusion coûte deux commandes, contre un retéléchargement complet avec un `DELETE`.

---

## ADR 004 — Le grain de l'Elo mensuel est `(compte, format, mois)`

### Contexte

Le modèle `mart_elo_mensuel` **n'agrégeait rien**. Son `GROUP BY` était :

```sql
GROUP BY TO_CHAR(date, 'YYYY-MM'), mon_rating, date, heure
```

Le couple `(date, heure)` étant quasi unique par partie, chaque groupe ne contenait qu'une seule partie. Une table nommée « mensuelle » produisait une ligne **par partie** : `total_parties` valait 1 partout et `elo_min = elo_max = elo_moyen`. Après correction, la table passe de ~1573 lignes à 11.

La cause est un piège SQL courant : `FIRST_VALUE`/`LAST_VALUE` ne peuvent pas référencer de colonnes non groupées. Pour faire compiler la requête, ces colonnes ont été ajoutées au `GROUP BY` — ce qui change le grain de la table sans qu'aucune erreur ne le signale.

S'ajoutait l'absence de dimension `format` : les 5 parties `daily` à 236 d'Elo s'agrégeaient avec le rapid.

### Alternatives écartées

**Sous-requête ordonnée avec `DISTINCT ON`.** Correct, mais impose une jointure supplémentaire pour recoller les agrégats.

**Conserver les fonctions fenêtre et post-filtrer.** Rejeté : conserve un grain trompeur dans la table intermédiaire.

### Décision

Grain `(compte, format, mois)`. Les premier et dernier Elo du mois sont obtenus par agrégat ordonné, qui n'impose rien au `GROUP BY` :

```sql
(ARRAY_AGG(mon_rating ORDER BY date,      heure))[1] AS elo_debut_mois,
(ARRAY_AGG(mon_rating ORDER BY date DESC, heure DESC))[1] AS elo_fin_mois
```

### Conséquences

- La table porte enfin le grain annoncé par son nom.
- Toute future analyse de classement doit respecter le couple `(compte, format)`.
- **Règle de vérification** : après modification d'un modèle agrégé, comparer le nombre de lignes produites au nombre attendu. Un écart d'un ordre de grandeur révèle un `GROUP BY` trop fin.

---

## ADR 005 — La progression relative est la seule mesure comparable entre comptes

### Contexte

Deux comptes ne démarrent pas au même Elo, et les premières parties d'un compte sont en classement provisoire (facteur K élevé, forte volatilité). Une courbe continue afficherait une chute artificielle au changement de compte ; deux courbes séparées empêcheraient de répondre à « est-ce que je progresse ? ».

### Décision

Le mart expose les deux lectures :

- `elo_debut_mois` / `elo_fin_mois` / `progression_mois` — niveaux absolus, valables **à l'intérieur** d'un compte ;
- `progression_depuis_debut_compte` — chaque compte indexé sur son propre point de départ.

Les **niveaux** ne sont pas comparables entre comptes ; les **trajectoires** le sont.

### Conséquences pour la Phase 2 (ML)

C'est la conséquence la plus importante de ce document.

| Feature | Transférable entre comptes ? |
|---|---|
| `diff_elo`, `niveau_adversaire` | **Oui** — relatives, calculées au sein d'une même partie |
| `moment_journee`, `famille_ouverture`, `ma_couleur` | **Oui** — indépendantes du classement |
| `mon_rating`, `adversaire_rating` **absolus** | **Non** — propres à un compte et à un format |

Un modèle entraîné sur les ratings absolus d'un dataset multi-comptes apprendrait à **distinguer les comptes** plutôt qu'à décrire le jeu. `chesspulse_phase2_strategie.md` liste pourtant les deux ratings bruts comme features : **cette liste est à réviser avant l'entraînement.**

---

## ADR 006 — Le périmètre d'analyse est appliqué en un point unique

### Contexte

Les décisions 001 et 003 définissent chacune un filtre. Répliqués dans chaque mart, chaque endpoint d'API et chaque script ML, ces filtres finissent par diverger — et une omission ne produit pas d'erreur, seulement un résultat faux.

Le cas s'était déjà présenté : l'endpoint `/stats` de la Pipeline API interrogeait `raw.games` directement, contournant tous les filtres appliqués par la couche staging.

### Décision

`stg_games` est le point unique d'application du périmètre :

```sql
WHERE format = 'rapid'
  AND exclu_analyse = FALSE
```

**Règle qui en découle : aucun consommateur ne lit `raw.games` directement.** Marts, Pipeline API et futurs modèles ML passent par `stg_games` ou par les marts qui en dérivent. Un accès direct à `raw.games` depuis un consommateur est un bug, pas un raccourci.

### Conséquences

- Modifier le périmètre — ajouter un format, réviser une exclusion — se fait à un seul endroit.
- `raw.games` conserve son rôle de copie fidèle de la source.
- Cette règle est consignée dans `CLAUDE.md` pour survivre aux sessions futures.

---

## ADR 007 — La syntaxe dbt cible la version du conteneur, pas celle de `requirements.txt`

### Contexte

`stg_games.yml` déclarait ses tests sous la clé `data_tests:`, introduite en **dbt 1.8**. Le conteneur qui exécute dbt tourne en **1.5.0** (installé par le `Dockerfile`), où la clé attendue est `tests:`.

Conséquence : dbt annonçait `Found 3 models, 0 tests` et la tâche `dbt_test` du DAG Airflow **passait au vert chaque jour sans rien vérifier**. Un test qui ne s'exécute pas est plus dangereux qu'un test absent — il produit un faux signal de sécurité.

### Décision

La syntaxe cible est celle de la version **installée dans le conteneur**, seule à exécuter réellement dbt. Clé `tests:` retenue ; 8 tests s'exécutent désormais.

**Règle de vérification** : toujours lire le nombre de tests trouvés dans la sortie de `dbt test`, jamais se fier au seul code de sortie.

### Dette identifiée, non traitée

`ingestion/requirements.txt` déclare `dbt-core==1.8.0` tandis que le `Dockerfile` installe `1.5.0`. Cet écart est la cause première du problème. Le résoudre — en alignant les deux sur une version unique — reste à faire.
