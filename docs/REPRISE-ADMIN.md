# Reprise du travail sur l’administration LinKs

Branche de travail, `codex/admin-interface-reference`.
Base, commit `5a050df` de `main`, avec réservation de V1.4.16.

## Décisions validées

La page Statistiques est la référence graphique et ergonomique de toute
l’administration. Le périmètre a été confirmé par l’utilisateur.
Les règles communes sont dans `docs/ADMIN-INTERFACE.md` et les instructions
de contribution dans `AGENTS.md`.

Reprendre les couleurs, cartes, onglets, espacements, contrôles, animations,
interactions de sélection, états de chargement et d’erreur, accessibilité
et présentation des données de Statistiques.

Les analyses affichent 30 jours par défaut. Une journée choisie au calendrier
ou sur une courbe s’applique à tous les onglets du même espace.

## Travail contenu dans cette branche

- Correctif du tableau des taux de copie. Seules les campagnes actuellement
  éligibles avec un code promo renseigné y figurent. Les totaux et le
  dénominateur suivent ce périmètre. Les campagnes sans code, avec un code vide,
  désactivées, en brouillon, expirées, futures, archivées ou introuvables
  sont exclues de ce tableau.
- Test Python de ce périmètre et contrôle navigateur des totaux et des lignes.
- Socle partagé `admin/workspace.css`, chargé par l’administration et servi par
  `scripts/analytics.py`. Il reprend les surfaces, dimensions, contrôles,
  onglets existants et mouvement réduit de la référence.
- Consignes durables et documentation de cette référence.

Cette branche constitue une étape de travail. L’harmonisation fonctionnelle
des différentes pages reste à réaliser et à valider vue par vue.

## Harmonisation poursuivie le 4 novembre 2026

- Cadre de lecture, navigation latérale, titres et surfaces alignés sur
  Statistiques dans toute l’administration. Les listes de campagnes, liens
  permanents, raccourcis et archives réutilisent les cartes du socle commun.
- Réglages : rubriques horizontales sur ordinateur, sélecteur conservé sur
  mobile, cartes de statut et retour du focus après ouverture d’une rubrique.
- Apparence : rubriques nommées et sélection annoncée, cartes de thèmes,
  panneau de contrôles et régions de contenu. Les thèmes publics et leurs
  aperçus restent indépendants de l’apparence de l’administration.
- Descriptions : même barre de rubriques et largeur de lecture, régions de
  contenu nommées. Le rendu YouTube de l’aperçu garde sa typographie dédiée.
- Affiliation : barres de partenaires et de rubriques communes, couleurs
  sémantiques du thème. La barre des partenaires conserve son défilement interne.
- Navigation clavier commune dans `admin/navigation.js` : Tab et Entrée
  conservent leur fonctionnement natif ; les flèches gauche/droite et
  Début/Fin déplacent le focus sans charger une autre rubrique. Le focus est
  restauré si une barre est reconstruite après activation.
- Fenêtres d’édition : typographie, contrôles et angles communs. Le mouvement
  réduit couvre aussi la navigation et les fenêtres. Les contrôles tactiles
  sont agrandis ; les événements du planning conservent leur géométrie horaire.

Aucune migration ni modification des règles de publication, redirection,
archivage ou statistiques n’accompagne ce lot. Aucun nouveau numéro de version,
tag, déploiement ou release ne doit être publié sans demande explicite.

### Suite du chantier

Le socle visuel couvre désormais les vues existantes. Les évolutions
fonctionnelles de Liens suivis ci-dessous restent à confirmer. Les futures
refontes de parcours doivent continuer à examiner les composants existants et
leurs règles métier avant de changer l’organisation des tâches.

## Page Liens suivis

L’utilisateur demande une organisation adaptée à une bibliothèque volumineuse.
Les propositions suivantes ont été présentées et restent à confirmer avant
leur mise en œuvre fonctionnelle.

- Quatre onglets, Bibliothèque, Partenaires, Sources et Archives.
- Liste compacte avec recherche globale, filtres par partenaire, état et domaine.
- Tri, compteur de résultats et choix de 20, 50 ou 100 lignes.
- Copie accessible sur la ligne, autres actions dans un menu contextuel.
- Source commune pour la copie, affichée au-dessus de la liste.
- Favoris et conservation de la recherche, des filtres et de la position.

Le rendu actuel utilise `admin/tracking.js` et `StudioCollection`.
La pagination existante est de 20 lignes.

## Vérifications

Le correctif des codes promos a passé 11 tests Python et la suite navigateur
`statistics-workspace-browser-test.cjs`, avec deux thèmes et cinq tailles.
Après ajout du socle graphique, relancer les parcours de toutes les vues
modifiées, notamment les réglages, l’apparence, l’affiliation et les descriptions.

Le socle partagé a déjà passé les suites
`statistics-workspace-browser-test.cjs` et `ergonomics-browser-test.cjs`.

Le lot d’harmonisation ajoute `admin-workspace-browser-test.cjs` à la CI :
dix modules, sous-rubriques de Réglages/Apparence/Descriptions/Affiliation,
fenêtres de création, cinq largeurs (320, 390, 768, 1024 et 1440), deux thèmes,
clavier, focus, commandes tactiles et mouvement réduit. Les réponses publiques,
liens, jetons suivis, statistiques, thèmes et descriptions sont comparés avant
et après navigation ; seuls les calculs d’aperçu et de disponibilité des
campagnes sont autorisés en POST. Aucune requête vers les marchands n’est nécessaire.

Validations locales réussies pour ce lot : les 11 tests Python de
`statistics_workspace_test.py`, puis les suites navigateur `admin-workspace`,
`statistics-workspace`, `ergonomics`, `appearance`, `settings`, `descriptions`,
`descriptions-editor`, `affiliation-overview`, `page-editor`, `conservation`,
`calendar`, `shortcuts`, `campaign-management` et `tracked-library` (suffixe
`-browser-test.cjs`). Les scripts JavaScript modifiés et le diff sont vérifiés.
Ces contrôles utilisent Chrome sous Windows ; ils ne remplacent pas
la validation Docker multiarchitecture du workflow de publication. Le commit
de départ `59ea271` n’avait aucun statut ni parcours de PR retourné par GitHub.

Les tests utilisent des bases temporaires. Le runtime Python peut être fourni
avec `PYTHON_PATH`, et Chromium avec `CHROMIUM_PATH` lorsque nécessaire.
La CI du dépôt décrit les commandes de validation complètes.

## Reprendre sur un autre PC

Dans un clone du dépôt, exécuter

```sh
git fetch origin
git switch --track origin/codex/admin-interface-reference
```

Puis demander à Codex

> Reprends le travail de LinKs sur la branche codex/admin-interface-reference.
> Lis AGENTS.md, docs/REPRISE-ADMIN.md et docs/ADMIN-INTERFACE.md.
> La page Statistiques est la référence de toute l’administration.

La publication d’une prochaine version pourra regrouper le correctif et les
refontes validées, selon la procédure du dépôt.
