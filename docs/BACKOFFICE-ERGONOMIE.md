# Refonte du back-office — issue #57

## Audit préalable (base V1.329 / 8fbc2a5)

Le back-office natif partage les panneaux et filtres entre le dashboard et les statistiques (`app.js`). Les collections paginées, graphiques accessibles, index quotidien, regroupements de sources et associations partenaires existent déjà. Les réutiliser ; ne pas déplacer les calculs vers un nouveau moteur.

| Parcours actuel | Friction constatée | Organisation retenue |
| --- | --- | --- |
| Dashboard → statistiques → jour → fiche (3 actions) | Jour séparé du graphique par une grille de classements ; catégorie publique présélectionnée | Tendance puis détail quotidien pleine largeur ; catégories d'événements explicites et raccourcis de métrique |
| Trouver un résultat | Recherche et tri repliés ; filtre actif annoncé uniquement aux lecteurs d'écran | Recherche visible, contexte visible et remise à zéro ; accès aux sections |
| Créer/copier un lien | Navigation, création, saisie, sauvegarde puis recherche dans la liste pour copier | Création directe depuis l'accueil ; réutilisation du parcours de copie après création ; source et destination clairement nommées |
| Gérer une campagne | Planning et simulateur avant la liste ; flèche du dashboard ouvre la liste générale | Liste avant les outils de planification ; accès direct à la fiche et statistiques contextualisées |
| Composer la page | Composition, liens, boutons et apparence mélangés aux outils de tracking | Groupe Composition et raccourcis vers les éditeurs existants |
| Administrer un partenaire | Navigation vers liens suivis puis défilement sous toute la bibliothèque | Accès partenaire explicite depuis la bibliothèque et le groupe de gestion |
| Navigation mobile | Menu obligatoire même entre statistiques et liens suivis | Accès directs aux destinations fréquentes, menu complet conservé |

## Inventaire à conserver

- Dashboard : cinq indicateurs historiques, filtre période/source, trafic, campagnes en cours.
- Statistiques : six métriques distinctes, courbes, histogramme, sélection quotidienne, trois catégories d'événements, sources/plateformes/historiques, classements liens/campagnes/partenaires, impressions, CTR, copies, recherche/tri/pagination, fiches et archives.
- Liens suivis : unitaire/lot, titres automatiques modifiables, partenaires/détection/aperçu URL, doublons/réutilisation, copie par source, édition, suspension, archives, titres par lot et gestion des sources.
- Campagnes : tous les champs, création/édition/duplication, partage, priorité, planning et conflits, simulateur, archives, affiliation et doublons.
- Page publique : composition en brouillon, ordre, aperçus, enregistrer/annuler ; liens permanents ; réseaux/raccourcis ; thèmes et assets.
- Administration : tous les paramètres, authentification, stockage, sauvegardes et confirmations destructives ; thème clair/sombre/système.

## Phases et vérification

1. Statistiques : hiérarchie, filtres visibles, raccourcis, parcours quotidien. Tests de chiffres, sources, partenaires, graphiques et navigateur.
2. Navigation et gestion : groupes, accès mobile, actions directes, listes et formulaires. Tests de création/lot/titres/doublons/campagnes/éditeur.
3. Finition et recette : 320/360/390/768/1024/1440 px, clavier, thèmes, vide/chargement/erreur, non-régression publique, intégration PulSe et suite CI complète.
4. Une PR de synthèse et une seule publication via le workflow documenté, après validation intégrale. Aucun accès au VPS.

Les fichiers `site/`, API, stockage, sécurité, migrations, instrumentation et calculs restent hors périmètre. Les tests utilisent exclusivement des bases jetables. Les changements de présentation peuvent adapter les assertions de disposition, jamais les valeurs métier attendues.
