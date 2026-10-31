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

## Parcours livrés et contrôle

| Action depuis son écran de départ | Avant | Après |
| --- | --- | --- |
| Accueil → formulaire de lien suivi | Navigation puis création : 2 clics | Création directe : 1 clic |
| Accueil → fiche d'une campagne en cours | Gestion puis recherche de la ligne et modification : 2 clics | Modifier sur la carte : 1 clic |
| Mobile → statistiques depuis une autre page | Menu puis destination : 2 clics | Accès fréquent : 1 clic |
| Lien créé → copie | Retrouver la ligne et choisir sa source | Bloc de partage immédiatement disponible, même si la liste est filtrée |
| Bibliothèque → partenaires | Défilement sous la liste | Raccourci avec focus sur le titre |
| Indicateur de clics/ouvertures → fiche du jour | Choisir la section et sa catégorie | Indicateur → catégorie quotidienne correspondante → fiche |

Les modes de calcul, les requêtes métier, les identifiants et la classification des sources sont inchangés. Le bloc de partage réutilise `copyTracked` (contrôle de destination, confirmation, source et presse-papiers) ; aucune logique parallèle de création de token. La mémorisation du sélecteur de source est uniquement en mémoire dans l'interface.

Les assertions de disposition et de focus des tests existants ont été adaptées : recherche désormais visible, détail quotidien avant les classements, URL ciblée à la création. Les valeurs de référence statistiques et les assertions métier sont conservées. La recette `ergonomics-browser-test.cjs`, intégrée à la CI, ajoute les raccourcis réels, le partage après création, la reprise après erreur, 120 combinaisons écran/largeur/thème et la conservation du rendu configuré de la page publique. Les suites existantes couvrent le contenu réel de l'éditeur, les titres, lots, doublons, sources, archives et PulSe.

Le chargement et la reprise du rapport sont des changements d'état d'interface ; une réponse d'erreur devenue obsolète ne remplace plus le message d'une requête plus récente. Cela n'affecte ni les calculs ni les appels métier.
