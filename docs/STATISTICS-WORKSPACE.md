# Statistiques : espace unifié (kit v1.2)

Intégration sur la base `6b03af3f6f2926545e63ef4467d9c45beaf2aed7` (V1.4.14).
Référence : `LinKs_Statistiques_Kit_Codex_v1_2.zip`, 3 novembre 2026.

## Audit et décisions

Confirmé dans le code : administration en JavaScript natif, vues sélectionnées
par `StudioNavigation`, thèmes partagés clair/sombre ; serveur Python
`analytics.py`, SQLite, authentification et sessions existantes. Aucune dépendance
de production ajoutée. Aucun schéma, compteur de collecte, historique ou jeton
de redirection modifié. La base locale de production n'a pas été consultée.

Les accès internes `activate('dashboard')` et les fragments `#dashboard` /
`#statistics` conservent leur accès à Statistiques. L'entrée Tableau de bord est
fusionnée avec Statistiques dans le menu. Les autres modules gardent leurs vues.
Le menu Actions rapides conserve la création de liens/campagnes et l'organisation
de la page. Les rapports de périodes, fiches, codes promo, partenaires et archives
restent accessibles sous les vues détaillées, dans un volet complémentaire fermé.
Ce volet conserve ses anciens composants de classement ; les nouvelles listes
quotidiennes sont virtualisées et ne comportent aucune pagination manuelle.

La période mensuelle est de 30 jours glissants par défaut, cohérente avec le kit et
le défaut serveur existant. Le mois civil est disponible et ce choix est mémorisé
dans le navigateur, sans nouveau paramètre de base. La date détaillée peut être
conservée entre onglets ; l'accueil présente toujours aujourd'hui. L'évolution
détaillée porte sur les 30 jours terminant à la journée choisie, toutes origines.

## Sources exactes des mesures

| Mesure | Source et identité |
| --- | --- |
| Visites | `counts.kind='view'`, journée enregistrée et source capturée ; aucune notion de visiteurs uniques inventée |
| Clics publics | `counts.kind='click'`, `counts.link`, aliases explicites de `metric_aliases()` ; métadonnées `content_blocks` / `top_buttons` |
| Ouvertures suivies | `counts.kind='tracked'` → `tracked_tokens.token` → `tracked_tokens.link_id` ; titre courant de `tracked_links.name` |
| Ouvertures de campagnes | `counts.kind='story'` → `story_links.token` → `promotion_id` ; `content_blocks.internal_name` ou nom historique capturé |
| Campagnes actives | `select_campaigns()` existant, ses `eligible_ids` ordonnés ; statut, retrait, archivage, brouillon et dates réels ; maximum trois cartes |
| Origines | `counts.source`, `source_labels()`, `tracking_sources` et leurs rattachements de plateforme existants ; les clés incertaines restent « Non identifiée » |

Le nouvel endpoint authentifié `GET /api/stats/workspace?date=YYYY-MM-DD&period=30`
(ou `period=month`) fournit accueil, journée détaillée, séries et métadonnées.
Les jointures et agrégats SQL sont groupés côté serveur, dans une transaction de
lecture. Il n'y a pas de requête par ligne ni d'appel marchand. Des jointures
externes conservent les compteurs dont le lien ou la campagne ne peuvent plus
être résolus, sous leur identité historique de jeton. Ces compteurs pouvaient
être absents de l'ancien rapport utilisant des jointures internes ; l'écart est
intentionnel, sans création ni réécriture d'événements.

Pour chaque famille : `total = somme(sources) = somme(items.total)`.
Les mêmes règles sont appliquées après recherche et filtrage. Deux titres
identiques restent deux lignes si leurs identifiants diffèrent. Un même lien
ayant plusieurs provenances conserve une seule ligne et toutes ses sources.

`counts.day` est déjà la date locale enregistrée lors de la collecte, et non un
instant UTC. Le fuseau effectif est celui de l'instance (`PARIS`, initialisé par
les réglages). Aucun recalcul rétroactif n'est effectué. Les instants UTC des
campagnes restent soumis à la logique métier existante. Changer le fuseau d'une
instance ne permet pas de reconstruire les instants absents des anciens compteurs.

La comparaison des visites concerne aujourd'hui et la veille complète ; une
référence nulle donne « Comparaison indisponible ». La collecte désactivée est
signalée. Les journées sans événement correspondent à zéro enregistré, sans
extrapolation. La nouvelle API reste interdite au serveur public et aux sessions
non authentifiées en mode local.

## Interface et accessibilité

- Quatre onglets sans rechargement : Vue d'ensemble, Visites, Liens, Campagnes.
- Accueil à trois cartes et un graphique, largeur plafonnée à 1450 px dans
  l'administration existante ; menu latéral et thèmes conservés.
- Donut SVG avec masque circulaire de 760 ms ; valeurs exactes dès le départ,
  transition d'opacité du total et de la légende ; aucune animation requise en
  mode mouvement réduit. Pourcentages entiers répartis pour totaliser 100 %.
- Sélection exclusive avec `aria-pressed`, sans déplier la ligne ; nouveau clic
  = retour au global. Filtres/date/type/onglet invalident la sélection.
- Palette commune par plateforme. Légende chiffrée, état vide sans secteur fictif.
- Liste virtualisée à lignes de 64 px, défilement interne, recherche sur nom/ID,
  filtres par plateforme ou source capturée. Navigation clavier Haut/Bas/Début/Fin.
- Chargement/erreur explicites et Réessayer ; aucune réponse tardive ne remplace
  un contexte plus récent. Les onglets restent disponibles pendant la requête.
- Rapports de provenance complémentaires corrigés : une mesure sélectionnée à
  la fois, unités adaptées ; aucun cumul de visites avec des ouvertures.

Les adaptations visuelles par rapport à la maquette sont le maintien de la barre
latérale, des couleurs de thème de l'instance, des actions rapides et du volet de
rapports historiques. Les graphiques utilisent les événements effectivement
enregistrés, jamais la courbe illustrative du kit.

## Validation réalisée

Tests Python : 111 réussis dans les suites `analytics_test.py` (44),
`campaign_selection_test.py` (11), `campaign_lifecycle_test.py` (16),
`conservation_test.py` (11), `platform_sources_test.py` (3),
`tracked_backup_compatibility_test.py` (9), `instance_test.py` (11),
`statistics_workspace_test.py` (6).

Tests JavaScript : 31 réussis avec `node --test` sur `statistics-workspace`,
`metrics`, `dates`, `calendar`, `collection`, `statistics-charts`,
`partner-report`, `source-platforms` et `daily-report`.

Cinq suites navigateur réussies : `statistics-workspace-browser-test.cjs`,
`statistics-browser-test.cjs`, `ergonomics-browser-test.cjs`,
`admin-ui-browser-test.cjs`, `admin-browser-test.cjs`.

Préparation de V1.4.15 : trois suites supplémentaires réussies (`conservation`,
`public`, `optimization`) et trois tests des notes de version. Les attentes
initiales des autres parcours généraux ciblent désormais la nouvelle vue
d'ensemble ; leurs vérifications métier restent conservées dans la CI complète.

Contrôles nouveaux : accueil 1920×1080 à 100 %, dimensions de document exactement
1920×1080 ; pas de débordement horizontal à 1440×900, 1366×768, 390×844 et 320×700 ;
thèmes clair/sombre ; sélection/désélection sans changement de hauteur ; trois
origines ; homonymes ; source inconnue ; zéro ; dates anciennes ; 0–4 campagnes
actives ; mois civil ; unités séparées ; erreur/reprise ; chargement retardé ;
navigation clavier ; mouvement réduit ; API privée ; absence de mutation des
compteurs ; collecte aux frontières UTC/locales des deux changements d'heure.

Sur 10 003 liens, moins de 30 boutons de ligne sont présents dans le DOM. Le
parcours clavier jusqu'au dernier élément et la recherche mesurés dans cette
session prennent 23 ms (mesure locale indicative, hors requête serveur).
Aucune erreur JavaScript ni requête marchande dans la nouvelle recette.

`node scripts/build-links.mjs` réussit. Vérifications syntaxiques Node/Python et
`git diff --check` réussies. Aucun outil de lint dédié n'est configuré dans
`package.json`. Les tests nouveaux sont ajoutés au workflow existant.

Les tests utilisent exclusivement des bases SQLite temporaires. Les captures
livrées illustrent ces jeux de validation et ne sont pas des mesures de production.
Les tests de gestion ont émis des traces Windows de connexions HTTP annulées lors
des changements rapides de page ; leurs assertions et contrôles JavaScript passent.

## Déploiement et retour arrière

1. Intégrer le patch sur la base indiquée ou reprendre les modifications préparées
   sur `feat/statistics-workspace-v1-2`. Sur une base plus récente, résoudre les écarts
   puis relancer les tests. Ne pas remplacer la configuration d'instance.
2. Exécuter la CI existante et construire une image de préproduction avec le
   Dockerfile fourni. Il copie le nouveau module Python dans l'image. La version
   `VERSION` n'est volontairement pas modifiée ; suivre la procédure de release.
3. Vérifier les quatre compteurs sur une copie isolée de la base réelle, avec le
   fuseau de cette instance, et contrôler les campagnes actives.
4. Lors d'un déploiement autorisé, sauvegarder le volume et remplacer uniquement
   l'image selon la procédure habituelle. Conserver `/data`, les sessions,
   paramètres, secrets et redirections. Aucun nouveau paramètre ni migration
   n'est requis par cette refonte.
5. Retour arrière : rétablir l'image précédente compatible avec la base de départ.
   Cette refonte n'ayant pas modifié le schéma ni les données, elle ne nécessite
   aucune restauration de base. Les éventuelles migrations d'autres releases
   restent soumises à leur propre procédure.

Limites de la validation locale : Docker n'est pas installé dans cet environnement.
La construction des images et la validation globale, y compris les modules
marchands, sont assurées par le workflow officiel avant publication de V1.4.15.
La production n'a pas été interrogée. La publication GitHub/GHCR ne met pas à jour
l'instance hébergée ; la comparaison avec ses données réelles reste une opération
de recette après mise à jour.
