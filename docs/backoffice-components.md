# Socle de back-office V1.311

## Plan retenu

1. Réutiliser `/api/stats` et `/api/content`, conserver les calculs et les identités V1.310.
2. Garder cinq KPI, le graphique quotidien et les campagnes actives sur le dashboard. Déplacer les analyses dans Statistiques et le planning dans Liens & campagnes.
3. Extraire les primitives DOM réellement réutilisées, borner les listes à vingt lignes, tester les historiques et les sources séparées.
4. Actualiser uniquement le carrousel public aux transitions programmées, nettoyer ses ressources et conserver un seul collecteur de métriques.

## Interfaces réutilisables

- `StudioNavigation.activate(id, views, buttons)` sélectionne les vues et boutons fournis, met à jour `aria-current`. Le chargement des données reste à l'application appelante.
- `StudioCollection.select(rows, {query, sort, page, pageSize})` filtre sans modifier l'entrée, trie par `name` ou `total`, borne la pagination. Les lignes ont `name`, `total`, `details` (textes de recherche facultatifs).
- `StudioCollection.create(node, {renderRow, pageSize, empty})` expose `setRows(rows)` et `filter({query, sort})`. Le rendu de ligne appartient à l'appelant ; la pagination et les annonces sont communes. Aucune dépendance réseau, SQLite, campagne, jeton ou source LinKs.
- `StudioCharts.donut(node, [[label, value], ...])` affiche la répartition et fournit les interactions clavier, focus et pointeur. Les libellés sont échappés. Le graphique quotidien conserve son adaptateur LinKs existant.

Les fichiers sont des scripts autonomes sans dépendances. Halloween Map pourra les reprendre avec son adaptateur de données et ses styles. Aucun rapprochement de bases, conteneurs ou authentifications. Les modules plus spécifiques (planning, suivi, réglages, apparence) restent dans LinKs.

## Règles analytiques

Le même DOM de synthèse (filtres, cinq KPI, graphique) est déplacé entre les deux vues. Aucun identifiant ni graphique dupliqué. La période et la source s'appliquent à la synthèse et aux listes. La recherche et le tri s'appliquent aux listes détaillées. Les dates personnalisées permettent de consulter toute période historique, avec la limite existante de 400 jours par requête.

Les visites et clics publics alimentent le CTR de page. Les ouvertures de liens partagés et copies de codes restent des compteurs séparés. Les sources combinent visites et ouvertures, sans ajouter les clics publics. Le graphique de sources regroupe au-delà des cinq premières sources ; leur liste détaillée reste complète et paginée. Les campagnes archivées et retirées restent consultables.

Les analyses des liens suivis sont centralisées dans Statistiques. Leur gestion conserve les actions et totaux historiques avec un accès contextuel à l'analyse. Le sélecteur de période et le second graphique de répartition de cette ancienne interface sont retirés, avec leurs styles dédiés. Les sources restent administrables dans leur dialogue existant.

## Audit des contrôles hérités

- Le texte « via /go/ » est remplacé par une description indépendante du format des URL.
- `cta`, `badge`, `description` et `icon` restent utilisés par les rendus historiques de `site/cards.js` (notamment les liens avec image). Les champs ne sont pas supprimés ni réinitialisés. L'éditeur minimal des campagnes garde son masquage existant.
- Les fonctions de sauvegarde, restauration, jetons, liens courts, migrations et authentification externe/locale restent celles de V1.310.
- Aucun nouvel export CSV : pas de besoin distinct établi pour cette version. La sauvegarde complète existante conserve l'historique ; un export analytique dédié reste une extension possible.
- Seuls le rendu de barres remplacé et les styles de détails de suivi devenus inutilisés sont retirés. Aucun nettoyage global de CSS.

## Actualisation publique

La configuration expose seulement `next_campaign_change`, la prochaine borne d'une campagne non privée. Le navigateur recharge les offres à cette borne, au retour au premier plan et au plus toutes les trente secondes lorsque l'onglet est visible. Les autres éléments publics et le collecteur restent en place. Chaque reconstruction déconnecte l'observateur, annule les temporisateurs et retire les écouteurs du carrousel précédent. Une campagne visible produit au maximum une impression par chargement de page ; aucun identifiant visiteur ni stockage n'est ajouté.

Aucune migration de schéma, suppression de données ou intervention sur un volume de production n'est nécessaire.
