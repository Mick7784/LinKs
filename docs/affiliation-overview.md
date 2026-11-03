# Vue d'ensemble Affiliation

## Contrat de consolidation

Le champ `overview` de la réponse privée `GET /api/affiliation/overview` est fourni
uniquement pour la vue globale (paramètre `account` vide). Les réponses et écrans
propres à un compte conservent leurs métriques, filtres, imports et synchronisations.
Aucune migration ni écriture financière n'est nécessaire.

La grandeur retenue est **Commissions observées / déclarées** (`observed_declared_commissions`).
Domadoo contribue avec ses commissions EUR présentes au statut `approved`, datées
par la vente du portail. Amazon contribue avec les commissions déclarées par ses
rapports de référence actifs, une seule fois par indicateur, période et périmètre.
Chaque partenaire conserve son `commission_status` dans les répartitions et la couverture.
Ce total n'est ni un solde retirable ni une somme de commissions toutes approuvées.
Les dates fournies restent civiles ; le jour courant utilise Europe/Paris.

Les statuts `not_approved`, les paiements, soldes, commandes et pertes ne contribuent
pas au total. Les corrections signées et changements de statut sont lus dans l'état
actuel des transactions, par compte et ID fournisseur ; les anciennes observations
ne sont pas additionnées. Une vente disparue n'est plus comptée. Une collecte tardive
peut donc corriger les journées antérieures.

Les vues Amazon complémentaires sont exclues des totaux. Les lignes portant une
date fiable peuvent alimenter les journées. Un rapport sans date quotidienne
contribue seulement si la sélection contient intégralement sa période confirmée :
son montant figure séparément dans `undated_cents`, jamais dans une barre artificielle.
Une sélection coupant ce rapport l'exclut avec une explication, sans prorata.
Les autres plateformes sans contrat comparable restent signalées et exclues.

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
- Les dates Amazon absentes restent inconnues, y compris entre deux dates présentes.
- Le KPI est la somme des montants journaliers connus et des totaux non ventilés admissibles ; il est qualifié de partiel
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
sur la période = KPI = somme des barres connues + part non ventilée, dans le même périmètre explicite.
Les comparaisons sont indisponibles en présence de montants non ventilés ; les
journées comparées doivent porter sur les mêmes Tracking IDs et être complètes.

## Vérification locale ciblée

```text
python -m unittest amazon_zip_test amazon_affiliation_test amazon_real_format_test amazon_report_views_test amazon_statistics_test affiliation_overview_test affiliation_test.FinancialTests
node scripts/amazon-zip-browser-test.cjs
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
