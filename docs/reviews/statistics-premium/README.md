# Refonte ergonomique des statistiques

Base : `main` / V1.321 (`7eea062`). Le cahier des charges `04_SPEC_TECHNIQUE_WORK.md` a été lu avant modification. La maquette sert de référence visuelle ; aucune de ses statistiques n’est intégrée.

## Composition et composants réutilisés

- `index.html`, `style.css` : six KPI compacts, icônes sémantiques, courbe et provenance côte à côte, détail quotidien central, classements rapprochés sur grand écran. Les quatre sections et leurs ancres sont conservées.
- `app.js`, `charts.js` : quatre séries indépendantes sur la courbe initiale, même rapport et mêmes événements. La sélection d’un jour synchronise calendrier, histogramme et détail. Le gros curseur redondant est retiré de la courbe ; il reste sur l’histogramme des longues périodes.
- `daily-report.js`, `source-platforms.js`, `partner-report.js`, `collection.js` : réutilisés sans modification. Les listes sont paginées par cinq, leurs détails et fiches restent accessibles. Un filtre de catégorie masque seulement les autres catégories quotidiennes.
- Les classements publics et suivis restent séparés, plutôt que mélanger clics et ouvertures dans un classement ambigu. Les partenaires conservent leur attribution explicite. Histogramme public et provenance des campagnes restent disponibles dans des volets.
- `brand-official.png` reproduit **exactement** le PNG du kit, sans recadrage, recoloration ni recomposition. Empreinte SHA-256 : `2aed7e131718a5b4072c49e5efacc845f65769a90d150a8d91288b431434a25d`. Son fond opaque reste présent en clair et sombre. Les SVG existants, la favicon et la page publique sont préservés.
- Côté serveur : ajout de la ressource du logo uniquement. Aucun changement des API métier, calculs serveur, événements, schéma, redirections, identifiants, associations ou échanges PulSe. Aucun accès au VPS ni à un volume de production.

## Contrôles locaux

- 126 tests Python réussis : analytique, conservation, historiques, redirections, sauvegardes, PulSe, authentification et autres contrats du serveur.
- 29 tests JavaScript réussis : métriques, dates, graphiques, collections, sources, partenaires et détail quotidien.
- Parcours statistiques : filtres partagés, quatre séries et valeurs exactes, couleurs distinctes, provenance, archives et campagnes à zéro, recherche, tris, pagination, fiches et retour du focus, données absentes, sources longues/inconnues, périodes de 400 jours, sélection quotidienne sans requête supplémentaire.
- 320, 390, 768, 1024, 1440 et 1920 px, thèmes clair et sombre : aucun débordement de page ni de conteneur statistique ; courbe sans défilement horizontal ; contraste du texte et des graphiques contrôlé. Navigation clavier, toucher et réduction des animations vérifiés.
- Parcours back-office et éditeurs : thèmes système/clair/sombre, persistance, dialogues, duplication, paramètres et configuration publique inchangée.
- Parcours calendrier réussi : création, déplacement, redimensionnement, chevauchements et mobile. Le scénario tactile passe désormais au mois suivant lorsque sa date de test le nécessite, comme le faisait déjà le scénario ordinateur ; aucun changement du calendrier applicatif.
- La CI du dépôt doit également réussir ses parcours complets, son démarrage Docker et ses validations AMD64/ARM64 avant fusion et publication.

## Captures comparatives

Captures du vrai back-office avec **le même jeu de régression temporaire**, comprenant volontairement de gros volumes, historiques incomplets et sources inconnues. Ces valeurs ne sont pas des statistiques de production ; elles ne proviennent pas de la maquette. État initial, filtres identiques, volets secondaires fermés. La nouvelle courbe initiale montre les quatre séries.

| Vue | Avant | Après |
|---|---|---|
| Ordinateur sombre, 1920 px | [Avant](before-overview-1920-dark.png) | [Après](after-overview-1920-dark.png) |
| Ordinateur clair, 1920 px | [Avant](before-overview-1920-light.png) | [Après](after-overview-1920-light.png) |
| Mobile sombre, 390 px | [Avant](before-overview-390-dark.png) | [Après](after-overview-390-dark.png) |
| Mobile clair, 390 px | [Avant](before-overview-390-light.png) | [Après](after-overview-390-light.png) |

Sur ce jeu de test, la page initiale passe de 8 477 à 3 013 px à 1920 px, et de 12 235 à 6 837 px à 390 px. Ce sont des mesures de mise en page, pas des évolutions d’activité. L’intégralité des résultats reste accessible par pagination.

## Publication

Notes V1.322 préparées dans `docs/releases/V1.322.md`. La réservation de version, le changelog, les tags Docker et la GitHub Release restent gérés par le workflow existant après validation. Aucune migration ni modification de Compose ou `.env` ; conserver `/data`, configurations et historiques.
