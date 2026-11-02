# Vue d'ensemble Affiliation

## Contrat de consolidation

Le champ `overview` de la réponse privée `GET /api/affiliation/overview` est fourni
uniquement pour la vue globale (paramètre `account` vide). Les réponses et écrans
propres à un compte conservent leurs métriques, filtres, imports et synchronisations.
Aucune migration ni écriture financière n'est nécessaire.

La grandeur retenue est **Commissions approuvées consolidées** : commissions EUR
actuellement présentes, avec le statut Domadoo `approved`, attribuées à la date de
vente fournie par le portail. Ce n'est ni un solde disponible, ni un historique des
dates d'approbation. Le portail ne documente pas le fuseau de ses dates de vente :
elles restent des dates civiles telles que fournies, sans conversion horaire inventée.
Le jour courant, les collectes et les fenêtres utilisent Europe/Paris.

Les statuts `not_approved`, les paiements, soldes, commandes et pertes ne contribuent
pas au total. Les corrections signées et changements de statut sont lus dans l'état
actuel des transactions, par compte et ID fournisseur ; les anciennes observations
ne sont pas additionnées. Une vente disparue n'est plus comptée. Une collecte tardive
peut donc corriger les journées antérieures.

**Amazon est exclu de cette grandeur** : ni les rémunérations, ni les rapports de
performance ne prouvent un statut équivalent à « approuvé ». Les imports et toutes
leurs vues restent disponibles dans la page Amazon. Aucun rapport, aucune vue
complémentaire (`category`, `tracking_id`, `daily_trends`, etc.) n'entre dans ce
total. L'exclusion évite à la fois le mélange de statuts et le double comptage. Les
autres plateformes sans contrat comparable sont également signalées et exclues.

Les données non EUR sont exclues sans conversion. Les nouveaux partenaires ne sont
pas limités à Domadoo/Amazon : la structure regroupe les comptes par partenaire
commercial. L'éligibilité d'une nouvelle plateforme exige un contrat documenté.
Comme dans l'existant, deux comptes doivent représenter des périmètres distincts :
aucun identifiant inter-comptes ne prouve qu'ils correspondent au même compte marchand.

## Couverture et zéros

- Chaque compte éligible et date reçoit `complete`, `partial` ou `unavailable`.
- Le relevé Domadoo accepté par l'ingestion doit être complet. La première date
  de vente connue, y compris une vente disparue ou non approuvée, est la borne
  inférieure prudente ; aucune date d'ouverture de compte n'est inventée.
- Entre cette borne et la veille de la collecte, une absence de commission
  approuvée dans le relevé complet vaut zéro connu, selon le statut actuel.
- Avant cette borne, après la collecte, dans le futur ou sans relevé : inconnu.
  Un relevé entièrement vide sans aucune vente historiquement connue ne suffit
  pas à prouver une couverture temporelle.
- La journée de collecte et le jour courant sont partiels. Les montants réellement
  observés peuvent être affichés ; une absence sur ces jours ne devient pas zéro.
- Une journée avec une devise exclue reste partielle. Les montants EUR admissibles
  restent affichés et rapprochables.
- Le KPI est la somme des montants journaliers connus ; il est qualifié de partiel
  si des jours/comptes sont incomplets ou des plateformes exclues. Aucune donnée
  admissible donne N/D. Le nombre de partenaires retenus inclut les vrais zéros
  mais exclut les partenaires entièrement inconnus.
- La date de collecte de référence la plus ancienne est affichée, avec le détail
  par compte. Un relevé de plus de 36 heures porte une invitation à actualiser ;
  ce seuil est un repère d'interface, pas une promesse de délai fournisseur.

## Comparaisons

Une sélection inclusive de N jours utilise les N jours civils immédiatement
précédents. N-1 associe chaque date à la même date de l'année précédente. Le
29 février n'est jamais rabattu sur le 28 : il produit un trou. Une fenêtre N-1
avec un nombre de jours calendaires différent invalide également la tendance.

Les tendances utilisent exactement tous les comptes éligibles de la sélection,
y compris un nouveau compte sans historique. Tous doivent avoir des journées
complètes dans les deux fenêtres. Sinon : N/D et raison explicite. Le jour
courant rend donc la tendance indisponible ; sélectionner une fin antérieure
permet de comparer des journées complètes. Une base nulle ou négative ne produit
pas de pourcentage. Les plateformes toujours exclues ne changent pas ce périmètre.

La ligne facultative peut afficher les seules paires de jours complètes pour ce
même périmètre ; elle est interrompue aux lacunes. Sans paire comparable, son
bouton est désactivé avec une explication. Son échelle inclut les barres et les
points visibles, avec zéro et graduations arrondies. Elle reste masquée au départ.

## Interactions et montants négatifs

Le filtre initial couvre 30 jours civils, aujourd'hui inclus. La modification
des champs ne déclenche rien avant Appliquer. « Tout l'historique observé »
commence à la première vente connue ; la vue journalière est bornée à 3 660 jours
pour limiter la charge de rendu, avec une erreur explicite au-delà.

Le clic, Entrée ou Espace sélectionne un jour sans reconstruire le donut de
période ni changer le KPI. Le focus reste sur la barre ; les flèches, Début et
Fin permettent aussi de parcourir les dates. Changer la comparaison conserve la
sélection. Un changement de période conserve la journée si elle reste dans la
fenêtre, sinon sélectionne la dernière date avec montant connu.

Les barres négatives passent sous zéro. Pour une répartition contenant un montant
partenaire négatif, le cercle reste neutre et les pourcentages sont masqués :
une part circulaire négative serait trompeuse. Le total net et tous les montants
signés restent affichés. Un total nul et une absence de données ont des messages
distincts. Les couleurs dépendent de l'identité du partenaire et restent stables.

Invariants : somme des partenaires du jour = barre du jour ; somme des partenaires
sur la période = KPI = somme des barres connues, dans le même périmètre explicite.

## Vérification locale ciblée

```text
python -m unittest affiliation_overview_test affiliation_test.FinancialTests amazon_report_views_test amazon_statistics_test
node scripts/affiliation-overview-browser-test.cjs
node scripts/affiliation-browser-test.cjs
node scripts/amazon-affiliation-browser-test.cjs
node scripts/amazon-statistics-browser-test.cjs
```

La commande Python s'exécute depuis `scripts/`, les commandes Node depuis la racine.
Les tests utilisent une base temporaire fictive, sans compte marchand. Les tests
navigateur acceptent `PYTHON_PATH`, `CHROMIUM_PATH` et, pour la nouvelle vue,
`AFFILIATION_QA_DIR` pour enregistrer les captures des thèmes clair/sombre en
1440 et 390 pixels. Le module Python est inclus explicitement dans l'image Docker.
Pas de publication, fusion, CI de publication ou release sans « OK pour release ».
