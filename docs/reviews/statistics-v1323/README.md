# Fidélité graphique des statistiques

Comparaison avec la maquette validée et la V1.322 : icônes trop petites, chiffres peu liés aux pictogrammes et accents trop discrets. Ce correctif agit uniquement sur la présentation existante : pictogrammes plus grands sur fonds teintés, couleurs sémantiques cohérentes, légendes lisibles, anneau et barres en couleurs unies, hiérarchie et relief discrets. Le logo officiel n’est pas modifié.

La structure HTML, les composants JavaScript, les données, les filtres, les API, les historiques, les redirections et PulSe ne changent pas. Le test navigateur existant vérifie désormais aussi que les chiffres des KPI restent sur une ligne aux six largeurs de référence.

Les parcours statistiques, contrastes, largeur des pages et des graphiques, clavier et tactile ont réussi à 320, 390, 768, 1024, 1440 et 1920 px en clair et sombre. Les captures ci-dessous utilisent les mêmes historiques temporaires du test : ces chiffres ne sont pas des données de production et ne proviennent pas de la maquette. Le numéro affiché dans les captures correspond à la version de base V1.322, avant la réservation de V1.323.

| Vue | V1.322 | Correctif |
|---|---|---|
| Ordinateur sombre, 1920 px | [Avant](avant-overview-1920-dark.png) | [Après](apres-overview-1920-dark.png) |
| Ordinateur clair, 1920 px | [Avant](avant-overview-1920-light.png) | [Après](apres-overview-1920-light.png) |
| Mobile sombre, 390 px | [Avant](avant-overview-390-dark.png) | [Après](apres-overview-390-dark.png) |
| Mobile clair, 390 px | [Avant](avant-overview-390-light.png) | [Après](apres-overview-390-light.png) |

Notes de release préparées dans `docs/releases/V1.323.md`. La CI et le workflow existant valident la publication AMD64/ARM64 ; aucun déploiement VPS ni changement de `/data`, Compose ou `.env`.
