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
