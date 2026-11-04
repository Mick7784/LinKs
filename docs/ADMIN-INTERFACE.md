# Référence commune de l’administration

Décision validée le 4 novembre 2026.
La page Statistiques définit la référence graphique et ergonomique de toutes
les vues de l’administration LinKs.

## Sources de référence

- `admin/statistics-workspace.js` pour les interactions et les états.
- `admin/statistics-workspace.css` pour la composition de la référence.
- `admin/style.css` pour les couleurs sémantiques des thèmes clair et sombre.
- `admin/workspace.css` pour les règles communes aux autres vues.
- `StudioNavigation.sectionBar` et `sectionFocus` dans `admin/navigation.js`
  pour les barres de rubriques existantes et la conservation du focus.
- `docs/STATISTICS-WORKSPACE.md` pour les périmètres analytiques.

## Présentation

Le titre, une courte description et les actions principales occupent l’en-tête.
Les rubriques de même niveau utilisent des onglets directement sous cet en-tête.
La rubrique sélectionnée emploie le fond cyan atténué, le contour accentué et
un état accessible explicite. Les filtres et actions de contexte sont regroupés.

La largeur de lecture est plafonnée à 1450 pixels. Les cartes utilisent les
surfaces du thème, un contour discret, des angles arrondis de 15 pixels et
18 pixels de marge intérieure. Les écarts principaux sont de 14 à 18 pixels.
La typographie suit Statistiques, avec un titre principal de 24 pixels,
des titres de cartes de 16 pixels et des légendes de 12 pixels.

Les couleurs expriment une fonction constante. Le cyan signale l’action et la
sélection, le violet une famille secondaire, l’ambre une information à examiner,
le vert une évolution favorable et le rouge une erreur ou une évolution négative.
Les libellés et les valeurs accompagnent les couleurs. Chaque thème fournit
ses variables de surface, texte, bordure et contraste.

Les listes présentent un nom lisible, les informations nécessaires au choix
et une action principale. Les autres actions sont regroupées. La recherche,
le tri, les filtres et la position de consultation sont conservés lors d’un
aller-retour vers une fiche. Une bibliothèque volumineuse utilise un rendu
borné et une recherche couvrant l’ensemble de ses résultats.

## Interactions et données

La sélection d’une ligne met en évidence cette ligne et actualise son contexte.
Un second clic rétablit le contexte global lorsque cette interaction est adaptée.
Les rubriques de gestion regroupent les tâches selon leur usage, comme les
liens, partenaires, sources et archives.

Les vues analytiques utilisent 30 jours par défaut. Choisir une journée au
calendrier ou dans une courbe applique cette journée aux compteurs et détails
du même espace. Les indicateurs précisent leurs unités, dates, origines et
dénominateurs. Les comparaisons portent sur des périmètres cohérents.
Les règles de périodes concernent les analyses. Les formulaires et bibliothèques
conservent leurs règles métier.

Les valeurs nulles, manquantes, vides et indisponibles ont des états distincts.
Les totaux suivent les filtres affichés. Une valeur ou une provenance incertaine
reste identifiée comme telle. Les réponses tardives sont invalidées quand
un contexte plus récent a été demandé. Les états de chargement et d’erreur
annoncent leur état et proposent une reprise adaptée.

Les courbes se dessinent à l’ouverture, les points sélectionnés affichent une
valeur et un repère pointillé, et les dates restent lisibles sur mobile.
Les changements de sélection actualisent le contenu concerné. Les animations
restent brèves et respectent le mouvement réduit.

Le clavier permet d’accéder aux onglets, filtres, lignes et graphiques.
Les contrôles ont des noms accessibles et un focus visible. Les vues s’adaptent
aux petits écrans, avec des actions accessibles et des défilements internes
identifiés lorsque leur contenu le nécessite.

## Application

Le socle commun applique les surfaces, dimensions, contrôles et onglets aux
composants déjà présents. Les refontes fonctionnelles de chaque vue reprennent
les règles ci-dessus et réutilisent les primitives de collections, graphiques
et navigation existantes. Les interfaces spécialisées, dont l’éditeur de page,
les imports et le planning, adaptent cette composition à leurs tâches.

Chaque livraison vérifie les thèmes clair et sombre, le mouvement réduit,
la navigation clavier, les états de données et les largeurs de bureau et mobiles.

Les barres `.workspace-tabs` utilisent une navigation nommée, des boutons
natifs et `aria-current="page"` pour indiquer la rubrique courante ;
`aria-controls` relie chaque bouton à son contenu. Elles ne déclarent pas
le rôle ARIA `tab` : tous les boutons restent accessibles par Tab. Les flèches
et Début/Fin déplacent uniquement le focus ; Entrée ou Espace active la rubrique.
Statistiques conserve son composant d’onglets spécialisé.

Le sélecteur mobile des neuf rubriques de Réglages et le défilement interne
des partenaires d’Affiliation adaptent cette navigation au volume de rubriques.
Les aperçus publics intégrés et le rendu YouTube gardent leurs propres styles.
