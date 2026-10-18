# Socle de back-office V1.312

## Plan retenu

1. Réutiliser `/api/stats` et `/api/content`, conserver les calculs et les identités V1.310.
2. Garder cinq KPI, le graphique quotidien et les campagnes actives sur le dashboard. Déplacer les analyses dans Statistiques et le planning dans Liens & campagnes.
3. Extraire les primitives DOM réellement réutilisées, borner les listes à vingt lignes, tester les historiques et les sources séparées.
4. Actualiser uniquement le carrousel public aux transitions programmées, nettoyer ses ressources et conserver un seul collecteur de métriques.

## Interfaces réutilisables

- `StudioNavigation.activate(id, views, buttons)` sélectionne les vues et boutons fournis, met à jour `aria-current`. Le chargement des données reste à l'application appelante.
- `StudioCollection.select(rows, {query, sort, page, pageSize})` filtre sans modifier l'entrée, trie par `name` ou `total`, borne la pagination. Les lignes ont `name`, `total`, `details` (textes de recherche facultatifs).
- `StudioCollection.create(node, {renderRow, pageSize, empty})` expose `setRows(rows, options)` (mise à jour atomique) et `filter(options)`. Les options comprennent `query`, `sort` (`total`, `name` ou `input`), `pageSize` et `preview`. Une seule page ne génère aucune commande de pagination. Le contexte de `renderRow(row, {max, seriesMax, preview})` permet des classements proportionnels sans connaître les métriques métier. Le rendu de ligne appartient à l'appelant ; la pagination et les annonces sont communes. Aucune dépendance réseau, SQLite, campagne, jeton ou source LinKs.
- `StudioCharts.ranking([{label, value}, ...], maximum)` retourne un nœud de barres proportionnelles accessibles. Une série sert aux classements ; deux séries servent à une comparaison, avec des libellés et échelles explicites.
- `StudioCharts.donut(node, [[label, value], ...], {preview, query, sort})` affiche un diagramme statique accessible et sa légende unique, paginée avec `StudioCollection`. La vue globale présente quatre sources et les autres regroupées ; la légende détaillée conserve toutes les sources. Aucun faux bouton ni répétition de valeurs au focus.
- `StudioCharts.timeline(node, detailNode, [[dateISO, a, b], ...], [labelA, labelB])` reprend le graphique chronologique existant avec des données et libellés fournis par l'appelant. Les interactions clavier et le survol révèlent les valeurs journalières. Un libellé vide masque la première série dans les descriptions. Aucune API ni dépendance aux campagnes LinKs.

Les fichiers sont des scripts autonomes sans dépendances. Halloween Map pourra les reprendre avec son adaptateur de données et ses styles. Aucun rapprochement de bases, conteneurs ou authentifications. Les modules plus spécifiques (planning, suivi, réglages, apparence) restent dans LinKs.

## Règles analytiques

Le dashboard conserve ses cinq KPI et sa synthèse temporelle. Seul le formulaire commun de période/source change de vue. Statistiques ne reproduit pas les KPI : sa vue globale contient des classements limités à cinq entrées et masque les cellules sans activité, tout en conservant les accès détaillés. La grille utilise deux colonnes indépendantes puis une colonne sur mobile. Le même graphique temporel rejoint une analyse détaillée uniquement lorsque plusieurs jours comportent une activité exploitable. Aucun identifiant ni graphique dupliqué. La période et la source s'appliquent à la synthèse et aux listes. La recherche et le tri s'appliquent aux listes détaillées. Les dates personnalisées permettent de consulter toute période historique, avec la limite existante de 400 jours par requête.

Les visites et clics publics alimentent le CTR de page. Les ouvertures de liens partagés et copies de codes restent des compteurs séparés. Les sources combinent visites et ouvertures, sans ajouter les clics publics. La légende unique des sources est complète et paginée dans le détail. Sa recherche ne change ni le total ni le dénominateur des pourcentages de la période. Les quantités y représentent des événements, jamais des visiteurs uniques. Le classement des campagnes utilise explicitement les clics publics, les ouvertures partagées, les impressions ou les copies selon le choix de l’utilisateur ; les barres de clics et d’ouvertures restent séparées. Les campagnes archivées et retirées restent consultables.

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

## Optimisations V1.312

Les rapports et métadonnées déjà demandés sont réutilisés pendant quinze secondes, avec déduplication des requêtes en cours et une limite de quatre entrées en mémoire. Toute mutation réussie invalide ce cache local ; aucune donnée n'est conservée dans le stockage du navigateur. Les filtres et tris côté client ne déclenchent pas de requête dédiée. Le rendu évite une seconde passe `setRows` puis `filter`, ne retrace pas une chronologie inchangée et ne reconstruit que la liste concernée par la recherche. Les détails dépliables sont matérialisés à leur ouverture.

Retraits ciblés : seconde liste des sources, répétitions au focus du diagramme, anciens styles interactifs du diagramme statique, duplication de la synthèse dans Statistiques. Aucune nouvelle bibliothèque, API, migration ou mécanique de collecte. Les fichiers de la page publique restent identiques à V1.311.
