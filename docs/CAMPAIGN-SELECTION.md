# Moteur de sélection des campagnes — étape 1

Base : `main`, V1.324. Cette étape conserve la version de production et l’affiliation. Le formulaire garde sa structure ; seul le message de disponibilité indique désormais que les chevauchements sont autorisés. Le [cycle de vie automatique de l’étape 2](CAMPAIGN-LIFECYCLE.md) complète désormais les règles d’archivage et de suppression.

La [gestion visuelle de l’étape 3](CAMPAIGN-MANAGEMENT.md) adapte ensuite le formulaire, le visuel par défaut et le planning à ce moteur.

## Données et ordre

Les campagnes restent dans `content_blocks`, avec leurs identifiants, URL, statistiques et liens suivis. `promo` et `featured` restent des types visuels historiques acceptés ; ils participent tous les deux au même moteur. Aucune conversion de type, réécriture de dates, suppression de données ou migration de schéma n’est nécessaire.

La durée est calculée à partir des dates existantes :

- `one_off` (ponctuelle) : `end_at` défini ;
- `permanent` (permanente) : aucune fin. Un début futur reste possible.

Les anciens intervalles ouverts sont conservés : une fin seule est ponctuelle, un début seul est permanent et programmé jusqu’à son début. Cette compatibilité évite de rendre invalides les anciennes campagnes et sauvegardes.

Le tri utilise successivement la durée (ponctuelles d’abord), `position`, l’instant `created_at`, puis `id` dans l’ordre lexical. Le mécanisme existant attribue une position croissante à chaque création : l’ordre initial suit donc la création, de la plus ancienne à la plus récente. L’API existante `POST /api/content/reorder` persiste l’ordre manuel dans `position`. Les positions historiques sont conservées. `priority=high` reste stocké, mais ne contourne plus la durée et le classement manuel des campagnes. Les liens classiques gardent leur fonctionnement existant.

## Éligibilité et affichage

Une campagne est éligible si elle n’est ni brouillon, ni désactivée, ni archivée, ni retirée, et si `start_at <= instant < end_at` (une borne absente est ouverte). La sélection est recalculée à chaque lecture, sans tâche planifiée, mutation ou archivage. Les trois premières éligibles sont affichées ; toutes les suivantes sont en attente. À la fin ou à la désactivation d’une campagne, la suivante prend la place à la lecture suivante. La page publique utilise son rafraîchissement existant, à la prochaine borne connue et au plus toutes les 30 secondes quand elle est visible.

Les réponses d’administration ajoutent ces champs sans modifier l’ancien `status` :

| Champ | Sens |
| --- | --- |
| `duration_type` | `one_off` ou `permanent` |
| `eligible` | Peut participer à la sélection à cet instant, y compris si elle attend |
| `visible` | Occupe une des trois places |
| `selection_state=scheduled` | Programmée, son début est futur |
| `selection_state=visible` | Éligible et affichée |
| `selection_state=waiting` | Éligible, en attente d’une place |
| `selection_state=ended` | Terminée, sa fin est atteinte |
| Autres `selection_state` | `draft`, `disabled`, `archived`, `retired` |

L’éligibilité est une propriété distincte de l’état d’affichage : une campagne affichée et une campagne en attente ont toutes deux `eligible=true`.

## Aperçu futur privé

`GET /api/promotions/selection?at=2099-01-02T12%3A00%3A00Z` utilise l’authentification d’administration existante. Sans `at`, il calcule la sélection actuelle. Il retourne `at` en UTC, `limit=3`, `items` avec les champs d’état ci-dessus et les listes ordonnées `eligible_ids`, `visible_ids`, `waiting_ids`. Ce calcul ne modifie aucune donnée et n’est pas accessible sur le serveur public. Une date vide, invalide ou répétée renvoie HTTP 400.

Les dates avec `Z` ou décalage explicite sont normalisées en UTC. Sans décalage, les nouvelles saisies et aperçus utilisent le fuseau de l’instance. Une heure locale ambiguë ou inexistante lors d’un changement d’heure exige un décalage explicite. Les dates historiques déjà enregistrées et les restaurations conservent leur interprétation antérieure.

## Contrat public et PulSe

`GET /api/public-config` conserve **toutes les campagnes éligibles dans `links`**, sans limite de trois, pour les clients PulSe existants. Le champ ajouté `visible_campaign_ids` contient uniquement les trois campagnes choisies par le serveur. La page publique utilise ce champ. Aucun contenu futur ou privé n’est ajouté à cette réponse.

`POST /api/pulse/story-link` accepte toujours toute campagne éligible, même en attente. Les URL courtes, jetons et compteurs existants restent indépendants du classement. `/api/pulse/links` garde son contrat consacré aux liens suivis indépendants.

Le secours statique existant conserve les campagnes publiques actives, dont celles programmées, dans le même ordre calculé par le serveur. Il ne fige aucun identifiant d’affichage : le navigateur filtre les dates puis prend les trois premières, permettant les relèves même pendant une indisponibilité temporaire du serveur. Les brouillons et campagnes désactivées sont exclus de ce secours.

`POST /api/promotions/check` reste disponible avec ses champs historiques : `allowed` est toujours vrai, les chevauchements deviennent indicatifs et `next_start` est nul. Création, modification et restauration n’imposent plus de plafond de campagnes.

## Validation

`python3 scripts/campaign_selection_test.py` couvre quatre ponctuelles simultanées et leur relève, priorité des durées, ordre manuel persistant, égalités, états exclus, aperçu privé sans mutation, douze créations simultanées, modification/restauration/duplication, changements d’heure, sauvegardes, `featured`, secours statique et publication PulSe d’une campagne en attente.

Cette suite rejoint le workflow GitHub existant. Les anciens tests de blocage sont adaptés au nouveau comportement. Les contrôles de PR ne publient aucune release et ne déclenchent aucun déploiement.
