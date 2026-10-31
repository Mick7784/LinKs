# Changelog

## V1.4.4

# V1.4.4 — Connexion automatique Domadoo

- Variables serveur facultatives `DOMADOO_LOGIN` et `DOMADOO_PASSWORD` pour le
  Compte Domadoo intégré. Une session valide est réutilisée ; en son absence ou
  après expiration, LinKs soumet le formulaire ordinaire une seule fois par tentative.
- Attente du lien affilié et du résumé avant collecte, puis retour aux restrictions
  de lecture. Les protections Cloudflare et les vérifications supplémentaires
  interrompent l'automatisation et laissent disponible la connexion humaine.
- Diagnostics distincts pour refus du formulaire, contrôle du portail et navigation
  bloquée par LinKs. Aucun identifiant n'est envoyé à l'interface ou journalisé.
- Historique financier, pagination, synchronisation quotidienne, session chiffrée
  et conservation du dernier relevé valide inchangés.

### Configuration

```yaml
environment:
  DOMADOO_LOGIN: ${DOMADOO_LOGIN:-}
  DOMADOO_PASSWORD: ${DOMADOO_PASSWORD:-}
```

Renseigner les valeurs dans la configuration privée du déploiement, puis cliquer
**Synchroniser**. Sans ces variables, la connexion humaine reste disponible.
Les variables ne sont pas appliquées aux comptes de reporting supplémentaires.
Conserver `init: true`, `/tmp` de 512 Mo et le volume `/data` existants.

### Validation réelle restante

Tests automatisés avec formulaires, identifiants et données synthétiques seulement.
L'acceptation du compte réel par Domadoo/Cloudflare depuis le VPS n'est pas validée.
Aucune furtivité, résolution de CAPTCHA ou modification d'empreinte du navigateur
n'est ajoutée. Aucun déploiement sur le VPS n'est effectué par cette publication.

## V1.4.3

### Corrections de la connexion Domadoo

- Firefox devient le navigateur par défaut, sans furtivité. Lors d’un essai public
  local sans identifiants, il a atteint le formulaire Domadoo (HTTP 200), tandis
  que Chromium recevait un HTTP 403. L’authentification complète sur le VPS reste
  à valider après déploiement : cette release ne garantit pas l’acceptation Cloudflare.
- Reprise des sessions chiffrées et d’une connexion interrompue, avec séparation
  entre état provisoire et session validée. Le dernier relevé financier est conservé.
- Commandes de la fenêtre sérialisées ; vérification sans recharger un formulaire
  ou un challenge ; conservation de la fenêtre après un timeout initial.
- Diagnostic de connexion copiable, sans identifiant, cookie ni jeton : navigateur,
  étape, HTTP, reprise, redirections classées et éventuel Ray ID.

### Déploiement et validation

- Aucune modification Compose ni nouvelle variable obligatoire. Conserver
  `init: true`, le tmpfs `/tmp` de 512 Mo et le volume `/data`.
- Ouvrir **Affiliation → Domadoo → Connexion et synchronisation**, puis réaliser
  personnellement la première connexion Firefox. Une ancienne session Chromium
  n’est pas transférée automatiquement entre moteurs.
- Tester la collecte et la reprise après redémarrage. Si la vérification boucle,
  copier le diagnostic de la fenêtre ; ne pas transmettre d’identifiants ou de HAR.
- L’image inclut les navigateurs AMD64/ARM64 ; les tests du navigateur et de la
  persistance sont exécutés sur chaque architecture native. Aucun VPS n’a été modifié.

La [comparaison technique ciblée](../domadoo-connexion.md) détaille les preuves,
les corrections de code et les limites de validation.

## V1.4.2

### 🔧 Améliorations

- Release V1.4.2 — titres améliorés et connexion Domadoo à valider
- preserve title specifications and highlight review proposals

### 🐛 Corrections

- allow human verification exchange and explain Domadoo challenge blocks

## V1.4.1

### 🐛 Corrections

- Récupération des titres sur les pages volumineuses, y compris compressées,
  sans dépasser les limites de lecture et de décompression. Les protections
  SSRF, DNS/IP, TLS, redirections et délais sont conservées.
- Diagnostic plus précis des échecs réseau et d'extraction, sans exposer les URL,
  paramètres, adresses IP ou contenus distants.

### 🔧 Améliorations

- Corrections rédactionnelles locales et ciblées des titres existants : accents,
  marques reconnues, hyphénation et ponctuation. Les références et valeurs
  techniques sont préservées ; ce moteur n'est pas un correcteur général.
- Comparaison avant/après, édition et sélection explicite des titres à appliquer.
  Aucune modification automatique des URL, liens affiliés ou statistiques.
- Intégration avec l'ensemble du module Affiliation et du connecteur Domadoo V1.4,
  y compris le correctif de test indépendant du mois courant.

### ⚙️ Technique

- Validation commune des titres, de l'affiliation et des images AMD64/ARM64 dans
  le workflow existant, avec contrôle Chromium sur ARM64 natif.
- Prise en charge du numéro V1.4.1, avec compatibilité des versions historiques,
  réservation persistante et reprise de publication sans réutiliser le tag V1.4.

### ⚠️ Mise à jour et validation

- Aucune modification Compose ou variable supplémentaire par rapport à V1.4.
  Conserver `init: true`, le tmpfs `/tmp` de 512 Mo et le volume `/data`.
- Après déploiement, vérifier l'affichage V1.4.1, la prévisualisation des titres et
  l'application des seuls noms sélectionnés. Les URL et statistiques restent inchangées.
- La connexion Domadoo depuis le VPS, les protections du portail et l'exactitude
  des données réelles restent à valider par l'administrateur, sans contournement.
- Guides : [Titres](https://github.com/Mick7784/LinKs/blob/V1.4.1/docs/title-generation.md)
  et [Affiliation](https://github.com/Mick7784/LinKs/blob/V1.4.1/docs/affiliation.md).

## V1.4

### ✨ Nouveautés

- Module Affiliation dans l’analyse : synthèse financière, graphiques, comptes et
  partenaires, transactions recherchables et paginées, corrections et bons de paiement.
- Premier connecteur Domadoo avec connexion humaine depuis l’administration,
  session chiffrée, synchronisation manuelle ou quotidienne et conservation du
  dernier relevé complet en cas d’échec.
- Séparation des plateformes, partenaires commerciaux et comptes. Préparation
  des comptes Amazon, Affiliatly, GoAffPro, Awin et Impact ; leurs collecteurs ne
  sont pas inclus dans cette version.

### 🎨 Interface

- Navigation interne par onglets, cartes compactes, thèmes clair et sombre et
  adaptation mobile selon la maquette Affiliation.
- Valeurs absentes clairement signalées ; « non approuvée » n’est assimilé ni à
  une commission refusée ni à une commission en attente.

### ⚙️ Technique

- Historique SQLite additif, montants signés en centimes et sauvegarde avant migration.
- Lecture intégrale des pages, contrôle des doublons, relecture de cohérence et
  ingestion atomique. Sessions exclues des sauvegardes JSON.
- Chromium intégré pour AMD64 et ARM64, sans nouveau port exposé. APIs financières
  exclusivement administrateur ; liens existants et pont PulSe conservés.

### ⚠️ Mise à jour et validation

- Conserver `/data`, ajouter `init: true`, porter le tmpfs `/tmp` à **512 Mo**.
  Aucun nouveau volume ni variable d’environnement obligatoire.
- Ouvrir Affiliation → Domadoo → Connexion et synchronisation, effectuer la
  connexion humaine, lancer une synchronisation et comparer au portail réel.
  La collecte quotidienne est désactivée initialement.
- Les tests n’utilisent aucun compte réel. Connexion depuis le VPS, protections du
  portail et exactitude des chiffres du compte restent à valider par l’administrateur.
- Les bons de paiement ne constituent pas un historique de virements. Fuseau des
  ventes, attente/refus et autorisation d’automatisation restent à confirmer avec Domadoo.
- Guide complet : [Affiliation](https://github.com/Mick7784/LinKs/blob/main/docs/affiliation.md).

## V1.331

### 🔧 Titres automatiques plus pertinents

- Le moteur existant compare les données produit structurées, les titres principaux, Open Graph, le titre HTML et les segments descriptifs des URL. Le titre HTML n'est pas privilégié automatiquement.
- Les marques et références attestées sont conservées. Les marques seules, catégories de boutiques et formulations commerciales génériques sont écartées ; le nettoyage ne coupe plus systématiquement au premier séparateur.
- Les liens Domadoo et Amazon, les redirections et liens courts, les pages Ko-fi, les invitations Discord et les profils Instagram bénéficient d'une identification plus prudente.
- Le titre actuel reste inchangé lorsque le gain n'est pas démontré, que les sources se contredisent ou que la destination ne peut pas être identifiée. Aucune référence produit n'est inventée et aucune API d'IA payante n'est utilisée.

### 🎨 Fenêtre « Générer des titres »

- Les améliorations, titres déjà pertinents, titres conservés faute de gain certain et destinations non identifiées sont distingués.
- Un niveau de fiabilité discret accompagne les résultats. Les titres inchangés ne sont pas comptabilisés comme des améliorations.
- Les propositions restent modifiables manuellement ; aucun changement n'est présélectionné et seule la sélection explicite est validée.

### 🛡️ Récupération et compatibilité

- Les protections SSRF et la validation de chaque redirection sont conservées et renforcées : attente DNS bornée, budget global de récupération, rejet des pages trop volumineuses et interruption des réponses bloquées.
- Le service commun reste utilisé par la création individuelle, la création en lot et la révision des titres. Aucun changement de schéma ni migration de données.
- Les URL finales, liens courts, données d'affiliation et statistiques ne sont pas modifiés par l'analyse ; la validation ne met à jour que les noms sélectionnés.
- Les pages bloquées, trop lourdes, dynamiques ou insuffisamment documentées peuvent conserver leur titre actuel : la pertinence est privilégiée au nombre de propositions.

### ✅ Validation

- Corpus de 25 fixtures HTML reproductibles couvrant Domadoo, Amazon accessible et inaccessible, Ko-fi, Discord, Instagram, titres corrects et métadonnées génériques ou contradictoires.
- 67 tests Python ciblés et trois parcours navigateur validés localement, avec contrôle de la sélection, de l'édition, des états, des compteurs et de la conservation des données.
- Vérifications de la fenêtre aux largeurs 320, 390 et 1440 px, en thèmes clair et sombre. La chaîne complète de tests et de validation Docker AMD64/ARM64 s'exécute avant publication.

La publication met à disposition la release et les images Docker ; elle ne déploie pas l'application sur une instance ou un VPS.

## V1.330

### ✨ Back-office organisé par usage

- Navigation regroupée en Analyser, Gérer les liens, Composer la page et Administrer, avec les destinations existantes toujours visibles.
- Accès mobile directs aux statistiques, liens suivis et campagnes ; page courante identifiée et navigation disponible pendant le défilement.
- Création d’un lien suivi ou d’une campagne depuis l’accueil. Les campagnes en cours ouvrent directement leur fiche ou leurs résultats.

### 📊 Statistiques orientées vers les actions

- Parcours vue d’ensemble → tendance → jour sélectionné → liens et campagnes → fiche, avec détail quotidien sur toute la largeur.
- Recherche et tri visibles, contexte de période/source lisible, raccourcis depuis les indicateurs et vers les sections.
- Les catégories d’événements suivent le contexte choisi ; toutes restent consultables. Sources, partenaires, histogramme et historiques sont conservés.
- Chargement explicite et bouton de reprise après erreur, avec conservation des derniers résultats et indication de leur contexte.

### 🔧 Gestion quotidienne

- Formulaire de lien suivi commençant par l’URL pour proposer le titre existant, toujours modifiable. Après création, choix de source et copie directement accessibles.
- Destinations lisibles dans la bibliothèque, boutons Copier explicites et source choisie conservée pendant la session de navigation.
- Liste des campagnes avant le planning, accès directs entre liste et planning ; partenaires et outils de composition reliés par des raccourcis.
- Densité, libellés, espacements et actions harmonisés sur ordinateur et mobile. Thèmes clair/sombre/système conservés.

### Compatibilité et validation

Back-office uniquement. Aucun changement aux fichiers publics `site/`, aux API, à l’authentification, aux données, aux migrations, aux calculs, à la collecte ou aux URLs publiées. L’intégration PulSe reste inchangée.

La recette automatisée couvre les dix écrans aux largeurs 320, 360, 390, 768, 1024 et 1440 px dans les deux thèmes, les parcours directs, le clavier, la reprise après erreur et la conservation de la configuration publique. Les tests statistiques de référence, métier, navigateur et Docker AMD64/ARM64 doivent tous réussir avant cette publication unique.

La publication ne déploie rien sur une instance ou un VPS. Aucun changement de stockage ne nécessite de migration pour cette refonte.

## V1.329

### ✨ Statistiques du jour pour PulSe

- Nouveau `GET /api/pulse/today`, privé Bearer sur le serveur admin, sans paramètre et en lecture seule.
- Clics d’aujourd’hui et d’hier en Europe/Paris sur les compteurs journaliers existants : clics de la page, campagnes/Stories et liens suivis. Les vues de page sont exclues.
- Comparaison explicitement avec hier, journée complète. Les données ne permettent pas une comparaison à heure égale.
- Classements du jour limités aux liens suivis : cinq liens et cinq sources au maximum, sans URLs ni tokens. Leur total est inclus dans le total général et ne doit jamais lui être ajouté.
- Snapshot cohérent dans une transaction de lecture. Aucun changement de schéma, identifiant, destination, affiliation, source, token, lien court ou historique.

### Compatibilité et validation

Les routes historiques PulSe 7/30 jours restent disponibles et inchangées. PulSe v1.1.3 reste compatible ; PulSe v1.1.4 utilise ce nouvel endpoint. Un fuseau de collecte autre que Europe/Paris produit un état indisponible explicite, sans conversion fictive ni modification de configuration. La collecte désactivée est signalée comme données partielles.

Tests minuit, changements d’heure, zéro clic, classement quotidien distinct des totaux historiques, absence d’écriture, accès privé/public et refus des paramètres. Les suites métier, navigateur et Docker AMD64/ARM64 complètes doivent être vertes avant publication.

### Exploitation

Aucun déploiement ni changement de production. HTTP Basic et les secrets sont conservés. Pour revenir à V1.328, revenir d’abord à PulSe v1.1.3 ; conserver tous les volumes et données LinKs. L’API est additive, aucune migration de données n’est nécessaire.

## V1.328

### 🔧 Améliorations

- Release V1.328 — Intégration LinKs et passerelle PulSe

## V1.327

### Liens suivis sans catégories

- Suppression définitive des catégories des liens suivis dans la base SQLite, les API, les formulaires et les filtres de la bibliothèque. Le nom du lien reste obligatoire ; la recherche utilise le nom, les destinations et les notes.
- Conservation des identifiants, destinations et URL d’origine, liens courts, redirections, partenaires et règles d’affiliation, sources, plateformes, campagnes, promotions, compteurs et historiques. Les destinations affiliées existantes ne sont pas recalculées.
- Compatibilité PulSe maintenue sans modification de son interface. Les liens associés aux vidéos YouTube conservent une destination fixe par vidéo et réutilisent leurs identités et URL déjà publiées, sans catégorie.

### Mise à niveau automatique

- Au premier démarrage sur une ancienne base, création et vérification d’une sauvegarde SQLite complète dans `pre-category-removal/<identifiant>/analytics.db`, puis retrait transactionnel de la seule colonne `tracked_links.category`.
- Contrôles d’intégrité, des références et de conservation des données avant validation. Une erreur annule la suppression et bloque le démarrage ; la sauvegarde validée reste disponible. Les démarrages suivants ne relancent pas la migration.
- SQLite 3.35.0 minimum requis et vérifié dans les images de test. Les nouvelles installations créent directement le schéma sans catégorie. Aucun nouveau paramètre Compose ou `.env`.
- La sauvegarde intégrée concerne SQLite. Pour un retour à une ancienne image, utiliser un état antérieur compatible ; un simple changement d’image ne rétablit pas la colonne supprimée. Cette version ne redémarre pas automatiquement l’instance.

### Compatibilité et validation

- Les anciens champs de catégorie reçus par l’API ou les sauvegardes v1/v2/v3 sont ignorés. Les nouveaux exports ne contiennent plus ce champ, sans changer les autres informations exportées. Un ancien importeur peut refuser ce nouvel export.
- Les catégories des fichiers et les regroupements statistiques restent inchangés : ils sont distincts des anciennes catégories de liens suivis.
- Tests de conservation, restauration de la sauvegarde intégrée, idempotence, pannes et interruptions sur bases fictives ; parcours ordinateur/mobile en clair/sombre et vérifications des images AMD64/ARM64.

## V1.326

### 🔧 Améliorations

- Release V1.326 — Back-office séparé et éditeur visuel de la page publique (#51)

## V1.325

### Campagnes : planification et gestion automatiques

- Création et programmation sans plafond ; trois campagnes visibles, avec priorité aux ponctuelles, ordre manuel persistant et relève automatique. Aperçu du planning à une date et une heure choisies.
- Archivage automatique des ponctuelles terminées avec activité ou références à préserver. Seules les campagnes sans aucune statistique ni référence nécessaire sont supprimées ; les permanentes ne sont pas concernées.
- Formulaire simplifié : titre public, nom interne généré, campagne permanente ou programmation avec dates et heures, classement souris et tactile, états explicites et chevauchements signalés.
- Visuel par défaut configurable dans Apparence, conservé dans `/data`, avec secours intégré et priorité aux images propres aux campagnes.
- Affiliation centralisée avec les Liens suivis : détection du partenaire, choix manuel ou Aucun, aperçu cliquable de la destination finale, prévention de la double affiliation et réutilisation des doublons.

### Mise à jour depuis V1.324

- Image `ghcr.io/mick7784/links:V1.325`, pour `linux/amd64` et `linux/arm64`, également publiée sous `latest`. Pour une installation épinglée, sélectionner `IMAGE_TAG=V1.325`.
- Aucun nouveau paramètre Docker Compose ou `.env`. Conserver le même volume `/data`, son nom, les configurations et les secrets ; sauvegarder ce volume avant la mise à jour manuelle.
- Mise à niveau additive automatique de la base pour la provenance d’affiliation, sans conversion des types historiques ni recalcul des destinations existantes. Statistiques, historiques, images référencées, liens courts et redirections conservés.
- Au démarrage, les anciennes ponctuelles déjà expirées suivent les règles d’archivage ou de suppression ci-dessus. Les archives restent consultables avec leurs statistiques et leurs redirections.
- Compatibilité API PulSe maintenue : toutes les campagnes éligibles restent disponibles pour publication, indépendamment des trois places publiques. Aucune modification de PulSe ni intervention sur le VPS ; la publication ne redémarre pas l’installation.

## V1.324

### Refonte finale du dashboard Statistiques

- Composition reconstruite selon la maquette : six indicateurs compacts, évolution dominante à gauche et provenance à droite, puis détail quotidien, top liens et campagnes sur une même rangée desktop.
- Suppression des quatre boutons de navigation interne. Période et Source conservés ; recherche et tri accessibles dans un volet repliable, utilisable au clavier.
- Classements publics et suivis réunis dans un panneau avec choix explicite de la mesure. Détail quotidien par catégorie avec volumes exacts, calendrier, navigation, provenances et accès aux fiches.
- Analyses partenaires, histogramme, sources détaillées et historiques conservés dans les sections complémentaires. Les campagnes inactives restent consultables.
- Icônes visibles, aplats sobres, couleurs cyan/bleu/violet/rose cohérentes entre indicateurs et graphiques, anneau agrandi. Logo officiel conservé à l’identique. Aucun comparatif temporel inventé.

### Validation

- Comparaisons avant/après en clair et sombre à 1672 px, largeur de la maquette, avec le même jeu de données isolé.
- Contrôles responsive à 320, 390, 768, 1024, 1440 et 1920 px dans les deux thèmes : aucun débordement horizontal de la page ou du rapport.
- Tests des valeurs, sources, périodes, historiques de 400 jours, partenaires, fiches, recherche, pagination, navigation clavier et tactile, contrastes et réduction des animations.
- [Captures et vérification visuelle](../statistics/V1.324/README.md).

### Mise à jour depuis V1.323

- Image `ghcr.io/mick7784/links:V1.324`, pour AMD64 et ARM64, également publiée sous `latest`.
- Aucune migration ni modification de Compose ou de `.env`. Si votre installation utilise un tag fixe, sélectionner `V1.324`.
- Conserver le volume `/data`, les paramètres et les historiques. Aucune intervention sur le VPS ; calculs, API, redirections et compatibilité PulSe préservés.

## V1.323

### Fidélité graphique des statistiques

- Icônes des six indicateurs agrandies sur des fonds légèrement teintés ; chiffres et libellés mieux hiérarchisés, avec adaptation aux écrans étroits.
- Accents cyan pour la page publique, bleus pour les clics et les sources, violets pour les liens suivis et roses pour les campagnes. Séries, légendes, anneau et barres restent distincts et lisibles dans les deux thèmes.
- Relief discret des cartes, bordures plus douces et pictogrammes de panneaux cohérents avec la maquette validée. Le logo officiel existant est conservé.
- Mise en page, filtres et fonctionnalités statistiques préservés. Aucune modification des données, API, historiques, redirections ou de PulSe.

### Mise à jour depuis V1.322

- Image `ghcr.io/mick7784/links:V1.323`, également publiée sous `latest`, pour AMD64 et ARM64.
- Aucune migration ni modification des paramètres Compose ou `.env`. Pour une installation épinglée, sélectionner le tag `V1.323`.
- Conserver le volume `/data`, les configurations et les historiques. Aucun déploiement sur le VPS n’est effectué par cette publication.

## V1.322

### Statistiques plus compactes et lisibles

- Six indicateurs compacts, avec des icônes colorées et des libellés complets. Aucun delta de croissance inventé.
- Courbe initiale présentant séparément les visites, clics publics, ouvertures de liens suivis et ouvertures de campagnes. Bascule de chaque série, valeurs exactes et sélection du jour conservées.
- Détail quotidien central, avec calendrier, navigation entre jours, filtre de catégorie, provenance et accès aux fiches. Cinq liens par page ; tous les résultats restent accessibles.
- Classements publics, suivis et campagnes rapprochés sur grand écran, avec cinq résultats par page. Ouvertures partagées en premier pour les campagnes ; clics publics, impressions, copies et archives restent consultables.
- Histogramme public et provenance des campagnes accessibles dans des volets repliables pour réduire les répétitions à l’ouverture.
- Logo officiel fourni affiché intégralement dans le back-office, avec son fond d’origine, en clair et sombre. Favicon et identité de la page publique préservées.
- Mise en page vérifiée à 320, 390, 768, 1024, 1440 et 1920 px, dans les deux thèmes, au clavier et au toucher.

### Conservation et mise à jour depuis V1.321

- Réutilisation des composants, filtres et rapports existants. Aucune modification du schéma, des calculs du serveur, des événements, des identifiants ou des associations historiques.
- Historiques, liens courts, redirections, sauvegardes, paramètres et compatibilité PulSe préservés. Le serveur ajoute uniquement la ressource du logo officiel.
- Image `ghcr.io/mick7784/links:V1.322`, également publiée sous `latest`, pour AMD64 et ARM64.
- Aucune migration ni nouveau paramètre Compose ou `.env`. Pour une installation épinglée, sélectionner le tag `V1.322`.
- Conserver le volume `/data`, son nom, les configurations et les secrets lors de la mise à jour manuelle. Aucun déploiement sur le VPS n’est effectué par cette publication.

## V1.321

### 📅 Détail des clics du jour

- Sélection d’une date directement sur les courbes et histogrammes, au clic, au toucher ou au clavier. Le survol consulte les valeurs sans remplacer le jour choisi.
- Nouveau panneau intégré aux statistiques avec choix de date et navigation jour précédent/suivant, dans les limites de la période sélectionnée.
- Trois classements distincts : clics des liens publics, ouvertures des liens suivis indépendants et ouvertures des campagnes partagées. Les visites, impressions et copies de codes ne sont pas présentées comme des clics.
- Titres, volumes, provenances, plateformes et sources historiques consultables sur place ; accès aux fiches disponibles, y compris les raccourcis publics et les campagnes archivées.
- Filtres de période/source conservés, messages explicites pour les journées sans activité et pagination des grandes listes de liens et de provenances.
- Calcul de lecture exclusivement à partir des événements quotidiens du rapport existant. Les clics de campagne déjà présents parmi les liens publics ne sont jamais ajoutés une seconde fois. Aucun suivi individuel ni attribution historique supposée.

### 📊 Graphiques et classements plus sobres

- Anneaux et barres de répartition en couleurs unies, sans hachures, pois ni textures. Couleurs stables, séparations nettes, légendes numérotées, valeurs et pourcentages conservés.
- Classement compact des campagnes par barres horizontales, avec les ouvertures partagées comme métrique initiale. Clics publics et ouvertures restent distincts ; impressions et copies restent sélectionnables.
- Campagnes sans activité accessibles dans une section repliable, sans suppression des campagnes actives, archivées ou historiques.
- Espacement resserré des classements publics et suivis ; titres lisibles, chiffres alignés, provenance et fiches accessibles sans quitter les statistiques.
- Synchronisation de la date entre les graphiques et le détail quotidien, y compris sur les longues périodes. Navigation clavier fondée sur le jour ayant le focus.
- Palette générale du back-office conservée ; vérifications à 320, 390, 768 et 1920 px dans les thèmes clair et sombre, au clavier et au toucher.

### 🔒 Conservation et mise à jour depuis V1.320

- Aucun changement d’API, de schéma, d’identifiant, d’association partenaire ou des calculs statistiques existants. Le serveur sert uniquement un nouveau composant JavaScript du back-office.
- Historiques, liens courts, redirections, sauvegardes, paramètres et intégration PulSe préservés. Page publique inchangée.
- Image `ghcr.io/mick7784/links:V1.321`, également publiée sous `latest`, pour AMD64 et ARM64.
- Aucune migration et aucun nouveau paramètre Compose ou `.env`. Si le tag est épinglé sur V1.320, sélectionner `V1.321`.
- Sauvegarder puis conserver impérativement le volume `/data` existant, son nom, les paramètres et les secrets lors de la mise à jour manuelle. Aucun déploiement sur le VPS n’est effectué par cette publication.

## V1.320

### ✨ Provenances regroupées par plateforme

- Vue par plateforme pour les sources clairement identifiées : YouTube Post et Description, Instagram Story et Bio, Discord, Facebook, TikTok et autres plateformes reconnues.
- Associations explicites prioritaires et libellés historiques strictement reconnus ; les provenances ambiguës restent dans « Autres » ou « Source inconnue ». L’ancienne clé incertaine `instagram-story` n’est pas attribuée à Instagram par son seul nom.
- Sources individuelles toujours consultables et filtrables sur place, avec conservation de leurs clés, de leurs distinctions et des filtres de période/source.
- Détails chargés à l’ouverture et paginés pour les grandes listes. Les contributions de chaque source sont conservées une seule fois ; le total d’une plateforme correspond à la somme de ses sources.

### 📊 Lisibilité et visualisations

- Textes, chiffres, dates, légendes et commandes agrandis ; classements de liens alignés en lignes comparatives et détails secondaires repliables.
- Comparaisons des campagnes par points sur une même échelle, avec valeurs visibles, formes distinctes et séries activables.
- Anneaux interactifs pour quelques catégories et barres pour les listes nombreuses ou les libellés longs ; valeurs absolues et pourcentages affichés.
- Couleurs stables, variantes adaptées aux thèmes clair/sombre et repères supplémentaires : tracés, formes, textures et numéros associés aux légendes.
- Lecture quotidienne des courbes et histogrammes plus compacte ; survol, toucher, clavier et navigation entre jours conservés.
- Indicateurs sur une colonne sur les petits écrans ; dispositions et détails vérifiés à 320, 390, 768 et 1920 px sans débordement horizontal.

### 🤝 Attribution des ouvertures aux partenaires

- Classement fondé sur les associations explicites actuelles des liens et les événements de la période/source sélectionnées, sans utiliser les compteurs cumulés ni déduire un partenaire du domaine.
- Répartition entre ouvertures attribuées, liens sans partenaire déclaré et attributions non identifiables ; liens concernés consultables directement.
- Les URL affiliées directes sans partenaire restent un cas légitime. L’interface indique que les événements historiques ne conservent pas le partenaire au jour du clic ni l’intention d’une absence d’association.
- Une indisponibilité des métadonnées affiche un classement temporairement indisponible, sans être présentée comme zéro ouverture ou une absence de partenaire.

### 🔒 Conservation et compatibilité

- Aucun changement du schéma de données, des événements enregistrés, des calculs de métriques ou des API existantes.
- Aucune fusion de sources, modification d’identifiant, réécriture d’historique ou attribution artificielle.
- Liens courts, redirections, paramètres, archives, configuration et compatibilité PulSe préservés ; page publique inchangée.

### ⬆️ Mise à jour depuis V1.319

- Image `ghcr.io/mick7784/links:V1.320`, également publiée sous `latest`, pour AMD64 et ARM64.
- Aucun nouveau paramètre Compose ou `.env` et aucune migration de données requise.
- Conserver le fichier Compose, les variables, les secrets et le volume `/data` existants, sans changer le nom du volume. Effectuer une sauvegarde avant la mise à jour.
- Si `IMAGE_TAG` ou le tag de l’image est épinglé sur V1.319, sélectionner `V1.320`. Avec `latest`, récupérer la nouvelle image puis recréer manuellement le service LinKs.
- Aucun déploiement automatique ni intervention sur le VPS.

## V1.319

### ✨ Statistiques sur une seule page

- Vue globale, liens suivis, page publique et campagnes accessibles directement, avec six indicateurs distincts et une mise en page qui utilise la largeur disponible.
- Courbes quotidiennes, histogramme avec axe fixe, classements de liens et partenaires, comparaisons de campagnes et répartitions des sources adaptées au nombre de sources.
- Valeurs exactes au survol, au toucher et au clavier ; séries activables, inspecteur de date et navigation quotidienne jusqu’à 400 jours.
- Couleurs stables : cyan pour l’activité publique, violet pour les liens suivis, bleu pour les sources et rose pour les campagnes.

### 🎨 Back-office et ergonomie

- Palette claire et sombre harmonisée sur les pages et les modales ; contraste renforcé des textes secondaires, champs, boutons, bordures et états de focus.
- Une seule barre de filtres et de navigation, avec conservation de la période et de la source, y compris lorsqu’une source n’a aucune activité sur la période.
- Fiches existantes des liens, partenaires et campagnes accessibles depuis les classements, sans quitter Statistiques ; retour du focus après fermeture.
- Détails visibles immédiatement, libellés longs lisibles, recherche sans résultat explicitée et disposition adaptée aux ordinateurs, tablettes et mobiles.

### 🐛 Sources historiques et fidélité des données

- Résolution des libellés depuis les identités, règles, alias non ambigus et associations historiques enregistrées ; les identifiants techniques restent internes.
- Les sources renommées ou archivées gardent leurs associations. Les provenances inconnues ou incertaines restent signalées, sans attribution arbitraire.
- Les événements de l’ancien graphique sont détachés lors du passage du tableau de bord aux statistiques : les infobulles et le clavier utilisent toujours les séries et la période courantes.
- Visites, clics publics, ouvertures des liens suivis, ouvertures des campagnes et copies de codes restent distincts. Une mesure indisponible n’est pas remplacée par un zéro.
- Les classements partenaires utilisent les événements de la période filtrée et les associations actuelles explicites des liens ; les ouvertures sans association sont indiquées et exclues du classement.

### 🔒 Conservation et compatibilité

- Aucun changement des calculs statistiques existants, du schéma de données, des redirections, des liens courts ni des compteurs historiques.
- Paramètres, contenus, liens, sources, archives et historiques conservés ; aucune réécriture des données à la consultation.
- API et parcours PulSe conservés. La page publique reste inchangée.

### ⬆️ Mise à jour

- Image `ghcr.io/mick7784/links:V1.319`, également publiée sous `latest`, pour AMD64 et ARM64.
- Aucun nouveau paramètre Compose ou `.env` et aucune migration de données requise depuis V1.318.
- Conserver intégralement le volume `/data`, le fichier Compose, les variables et les secrets existants, notamment la configuration PulSe. Effectuer une sauvegarde avant la mise à jour.
- Si `IMAGE_TAG` ou le tag de l’image est épinglé sur une ancienne version, sélectionner `V1.319`. Avec `latest`, seule la récupération de l’image et la recréation manuelle du service sont nécessaires.
- Aucun déploiement automatique ni intervention sur le VPS.

## V1.318

### ✨ Gestionnaire de liens suivis

- Navigation distincte pour Page publique, Liens suivis et Statistiques ; bibliothèque avec recherche, filtres, pagination et actions rapides.
- Partenaires facultatifs : domaines, codes et modèles libres, détection des sous-domaines, aperçu cliquable et choix manuel ou Aucun.
- Conservation de l’URL d’origine et de la destination publiée ; tout remplacement demande confirmation, sans réécriture lors d’un changement de code partenaire.
- Détection des destinations équivalentes après tracking, réutilisation des liens courts et ajout de sources ; exception confirmée et protection contre les créations simultanées.

### 🔧 Sources et compatibilité

- Instagram, YouTube, Facebook, TikTok et Discord proposés en priorité ; recherche et filtres pour gérer les sources courantes, historiques et archivées.
- Anciennes sources, identifiants, URL courtes et compteurs conservés, sans fusion destructive. PulSe réutilise ses liens Stories existants et utilise les plateformes pour les nouveaux partages.
- Correction des configurations Sanyipace initialisées vers sanyipacetoilet.com, en préservant les personnalisations.
- Migrations additives et sauvegardes/restaurations compatibles. Aucune modification de la page Statistiques dans cette version.

### ⬆️ Mise à jour

- Image ghcr.io/mick7784/links:V1.318 et latest pour AMD64 et ARM64.
- Aucun nouveau paramètre Compose ou .env ; conserver le volume /data existant. Utiliser IMAGE_TAG=V1.318 pour épingler la version si souhaité.
- La mise à jour de l’instance reste manuelle ; aucun déploiement automatique sur le VPS.

## V1.317

### 🔧 Améliorations

- Release V1.317 - correction affichage liens suivis privés

## V1.316

### ✨ Nouveautés

- PulSe peut préparer une URL courte suivie propre à la dernière vidéo YouTube de la source LinKs existante. La destination est fixée à cette vidéo et reste identique quand une nouvelle vidéo devient la dernière publiée.
- La passerelle privée accepte les statistiques sur 7 ou 30 jours, avec les clics quotidiens réels, les jours sans clic et le total de la période. Le comportement à 7 jours reste compatible.

### 🔒 Sécurité et conservation

- Le serveur vérifie l’identifiant vidéo contre la source YouTube LinKs ; PulSe ne peut pas imposer une destination arbitraire.
- Le lien vidéo est créé ou réutilisé comme lien suivi privé, catégorie YouTube, source Instagram Story. Un lien désactivé ou archivé n’est pas réactivé.
- Aucun changement de schéma, aucune réattribution des anciens jetons et aucune remise à zéro des historiques. La génération ou la copie du lien ne compte pas comme clic ; les redirections conservent le tracking existant.
- La passerelle reste protégée par le secret serveur PULSE_BRIDGE_TOKEN, jamais transmis au navigateur.

### 🧪 Validation

- Tests passerelle : stabilité de la destination, génération sans clic, HEAD sans clic, GET compté, refus des destinations arbitraires et des liens indisponibles, fenêtres 7/30 jours et compatibilité last7.
- Suite de non-régression LinKs, parcours Stories mobile/bureau, contrôles Docker et images AMD64/ARM64 dans la CI.

### 🔧 Mise en service

- Mettre à jour l’image LinKs vers V1.316 en conservant le volume /data, les variables existantes et le même PULSE_BRIDGE_TOKEN que PulSe. Ne pas remplacer la stack par une configuration vide.
- Avec PulSe V1.1.1 : actualiser, sélectionner la dernière vidéo, puis préparer/copier le lien. Ajouter le sticker Lien et publier reste une action manuelle dans Instagram.
- La publication de cette release ne redéploie aucun conteneur du VPS. La mise à jour de l’instance en production reste une opération distincte à valider.

## V1.315

### ✨ Nouveautés

- Ajout d'une passerelle privée pour l'application PulSe : récupération des liens suivis indépendants, des statistiques quotidiennes et génération de liens Story courts.
- Les promotions et les mises en avant actives peuvent être publiées via PulSe ; les liens classiques sont exclus.

### ⚙️ Technique

- API `/api/pulse/links`, `/api/pulse/stats` et `/api/pulse/story-link` protégée par un jeton serveur dédié `PULSE_BRIDGE_TOKEN`.
- Attribution Instagram Story fondée sur les jetons et redirections historiques de LinKs, sans réinitialisation des statistiques.
- Ajout de tests automatiques dédiés et d'un guide de configuration Dockhand dans `docs/PULSE-BRIDGE.md`.

### 🔧 Déploiement

- La passerelle est désactivée sans jeton serveur configuré ; les données persistantes restent dans le volume LinKs existant.
- Sauvegarder `/data` avant toute mise à jour du conteneur en production. Configurer le même secret aléatoire côté LinKs et côté PulSe.

## V1.314

### ✨ Nouveautés

- add blurred background image behind contained offer artwork

### 🔧 Améliorations

- Release V1.314 - publish validated LinKs carousel and default manual runs to release
- test: replace obsolete pause-button interaction with autoplay-resume check
- test: verify legacy overlay is hidden rather than its unused computed height
- test: target foreground artwork when offer also has blurred background
- test: allow non-square visual viewport inside fixed-height promo card
- test: inspect sharp foreground image instead of blurred background
- style: blur and darken backdrop while keeping original promotion uncropped
- test: require fixed promotional card height with contained image
- test: update legacy promo height assertions for uncropped responsive artwork
- test: normalize redesigned offer geometry in theme baseline comparison
- test: validate uncropped square offers and footer instead of cover
- Fix mobile promo artwork and remove Pause control (#39)

### 🐛 Corrections

- keep blurred artwork layer visible behind foreground image
- preserve fixed offer card dimensions and contain artwork within image area

## V1.313

### 🎨 Détails des sources plus lisibles

- Les ouvertures partagées et les clics publics présentent leur répartition dans un accordéon « Détails » : une ligne par source, un compteur visible et sa part du total.
- Les libellés « Ancien lien partagé » et « Source inconnue » remplacent les anciens textes longs dans ces détails, sans modifier les clés d’attribution.
- Affichage adapté aux petits écrans, aux thèmes clair et sombre et à la navigation au clavier. Le contenu est chargé à la première ouverture et ne se duplique pas à la réouverture.

### 🛡️ Conservation et vérifications

- Aucun changement des campagnes, des historiques, du stockage, des API de tracking ou des règles d’attribution. Aucune migration nécessaire. Le graphique des clics par jour reste inchangé.
- Tests des compteurs et pourcentages, des filtres, des archives, de la pagination, des états vides, des libellés longs et du total nul ; détails dépliés à 320, 390, 768 et 1440 px dans les deux thèmes.
- La chaîne de publication vérifie les tests Python, JavaScript et navigateur, le démarrage Docker, les images AMD64/ARM64 et l’identité des manifests de la version publiée et de latest.
- La publication GitHub/GHCR ne redémarre pas le serveur et ne touche pas à ses données. Conserver le volume existant lors de la mise à jour de l’instance.

## V1.312

### 🎨 Statistiques plus lisibles

- Vue globale compacte : classements limités à cinq entrées, cellules sans activité masquées et accès direct aux analyses complètes.
- Grille responsive en colonnes indépendantes, avec recherche, filtres, tri et pagination dans les vues détaillées. Les commandes de pagination disparaissent lorsqu’une seule page suffit.
- Barres proportionnelles communes aux liens publics et partagés. Comparaison distincte des clics publics et des ouvertures partagées des campagnes, avec classement par métrique choisie.
- Sources présentées dans un diagramme et une légende unique, complète et paginée. Les valeurs représentent des événements, jamais des visiteurs uniques.
- Dashboard consacré à la synthèse. Les chronologies détaillées apparaissent lorsque plusieurs jours d’activité apportent une information utile. Les copies de codes restent compactes.

### ⚡ Composants communs et performances

- Collections mises à jour en une seule passe, détails chargés à l’ouverture et chronologies inchangées réutilisées.
- Réutilisation temporaire des rapports et requêtes en cours, invalidée après modification. Aucun stockage persistant ajouté.
- Composants autonomes de classement, répartition, chronologie et pagination documentés pour les autres back-offices DomotiK Studio.
- Retrait de la seconde liste des sources et des styles et interactions devenus inutiles.

### 🛡️ Conservation et validation

- API, schéma SQLite, historiques, archives, sources, campagnes, images, jetons, URL courtes et authentification conservés. Aucune migration nécessaire.
- Page publique identique à V1.311. Aucun accès au VPS ni à son volume de données.
- Tests Python, JavaScript et navigateur : vues globales/détaillées, plus de cinq cents liens, métriques séparées, périodes historiques, états vides, clair/sombre et mobile. Validation Docker AMD64/ARM64 et manifests avant publication.

## V1.311

### ✨ Statistiques et administration

- Nouvelle page Statistiques : liens publics et partagés, campagnes, sources et copies de codes promo, avec recherche, tri, détails et pagination commune.
- Dashboard limité aux cinq KPI, au graphique synthétique et aux campagnes actives. Accès contextuels aux analyses ; planning déplacé dans Liens & campagnes.
- Synthèse partagée sans duplication, périodes personnalisées pour les historiques, composants autonomes de navigation, collection paginée et graphique de répartition.
- Analyses des liens suivis centralisées ; retrait de leurs anciens contrôles et styles analytiques redondants. Correction des libellés liés à `/go/`.

### 🐛 Campagnes programmées

- Les campagnes apparaissent et expirent sur une page publique déjà ouverte. Le carrousel précédent est nettoyé avant reconstruction.
- Une seule collecte de visite et une impression par campagne visible et par chargement de page, sans doublon lors des actualisations.

### 🛡️ Conservation et validation

- Réutilisation des API, calculs, migrations et protections V1.310. Aucune modification du schéma SQLite ni des identités, sources, jetons ou URL courtes.
- Tests Python, JavaScript et navigateur, dont 504 liens, archives, périodes historiques, sources séparées, texte hostile et transitions programmées sans rechargement.
- Pipeline existant de validation Docker et publication AMD64/ARM64 conservé. Aucun accès au VPS ni à son volume de données.

## V1.310

### 🛡️ Conservation des données et des liens

- Retirer un contenu ou un raccourci conserve son identité, ses statistiques et ses médias. Les éléments restent restaurables depuis les archives ; les campagnes publiées continuent de rediriger.
- Une restauration préserve les compteurs actuels, les contenus ajoutés depuis la sauvegarde, les jetons et codes courts ainsi que les destinations publiées. Les agrégats communs sont conservés au maximum, sans double addition à chaque import.
- Prévisualisation des effets avant confirmation et copie de sécurité SQLite avec les fichiers référencés avant restauration.
- Migration additive : sauvegarde pré-migration, indicateurs de retrait et correspondances stables des anciennes sources, sans recréer les identifiants ni réécrire l’historique.
- La collecte ne purge plus automatiquement les anciens compteurs. Les rapports restent bornés par période.

### 🐛 Fiabilité et confidentialité

- Renommer une source prédéfinie ne change plus son identité de comptage. Une source déjà publiée est archivée même sans clic.
- DNT et Global Privacy Control sont respectés côté serveur sur les liens longs, courts et les métriques.
- Les sauvegardes prennent en charge les SVG historiques passifs, sans autoriser l’upload de SVG ni le contenu exécutable.
- Le secours public inclut les campagnes programmées non privées et est actualisé après l’assistant initial.
- Correction des miniatures de bibliothèque du dashboard, des styles et scripts bloqués par CSP, et de la reprise du carrousel pendant le focus ou le survol. Une commande pause/reprise est disponible.

### 🎨 Administration

- En-tête de barre latérale limité au logo LinKs by DomotiK Studio.
- Cartes KPI uniformes au repos avec un accent discret au survol.
- Sélecteur clair/sombre/système aligné, avec icônes soleil/lune/écran.
- Périodes des liens privés raccordées, raccourcis retirés restaurables, export CSS Expert partagé et contrôles hérités sans effet signalés.

### ✅ Validation et déploiement

- Tests de conservation, migration répétée sur copie d’un volume synthétique, restauration, attribution, confidentialité, médias, CSP et interactions.
- Validation CI des images AMD64 et ARM64 sur données temporaires ; vérification des manifests version/latest.
- Aucun accès au VPS ni utilisation des données de production. La validation sur une copie du volume réel reste à effectuer avant un déploiement en production. Publier l’image ne redémarre pas l’instance.

## V1.309

### Administration : identité DomotiK Studio désormais visible

La V1.308 harmonisait surtout les fonds du back-office ; la différence était difficile à distinguer de la version précédente. Cette mise à jour apporte des repères de marque clairement visibles **sans refonte des fonctionnalités ou de la grille**.

- **Barre latérale** : signature « ÉCOSYSTÈME DOMOTIK STUDIO », zone de logo légèrement mise en valeur et trait supérieur cyan/bleu/violet.
- **Navigation** : sélection plus nette grâce à un filet cyan et un fond très subtil, sans éclairage néon envahissant.
- **Barre supérieure** : marque discrète près du fil d'Ariane et très fin trait tricolore.
- **Tableau de bord** : rappel coloré de 2 px en haut des indicateurs clés ; les cartes restent neutres et très lisibles.
- **Boutons principaux** : bleu vif conforme à la charte, avec texte contrasté.
- **Connexion** : fond bleu nuit et signature tricolore cohérents avec l'administration.

### Compatibilité et ergonomie

- Sidebar mobile compacte conservée ; la micro-signature est masquée sur les petits écrans.
- Thèmes clair et sombre conservés, contrastes et hiérarchie inchangés.
- Pas de changement des sections, des formulaires, des données, des URL courtes ou du front-end public.
- **Aucune migration de base de données.** Conserver les volumes existants lors du déploiement.

### Vérification après mise à jour

La version installée apparaît en bas du menu d'administration. Si ce menu affiche encore une version précédente, le VPS ou la fenêtre du navigateur n'a pas encore chargé la nouvelle image. Une actualisation forcée (Ctrl+F5) peut aider si les styles restent en cache.

### Tests

Les tests navigateur vérifient la signature de la barre latérale, la sélection du menu, le fil d'Ariane et les indicateurs, en plus de la suite existante (statistiques, campagnes, éditeur, mobile et Docker).

### Publication

Image Docker : `ghcr.io/mick7784/links:V1.309` — AMD64 et ARM64. La publication ne met pas à jour le VPS automatiquement ; conserver les volumes de données et les réglages existants.

## V1.308

### 🎨 Identité visuelle DomotiK Studio

LinKs rejoint la nouvelle charte de l’écosystème DomotiK Studio, en conservant sa personnalité de produit indépendant et le monogramme K officiel.

### Page publique : mêmes composants, palette harmonisée
- **Bleu nuit** `#060E24`, **cyan** `#00E5FF`, **bleu vif** `#0066FF`, **violet** `#A855F7`, blanc doux `#EAF2FF`.
- Ajustement limité à la palette par défaut et aux nuances de fond, bordures, liens et icônes. Les tailles, cartes, animations, contenus et comportements du carrousel **ne changent pas**.
- Les thèmes personnels et les réglages de l’éditeur « Apparence » restent disponibles : aucune modification en base de données et aucun thème enregistré n’est écrasé.

### Footer LinKs by DomotiK Studio
- Ajout de la signature visuelle LinKs avec son K officiel et le libellé « by DomotiK Studio ».
- Conservation du logo de profil, du copyright personnalisable, de la citation aléatoire et du numéro de version dynamique.
- Mise en valeur discrète du pied de page, sans ajout de section ni surcharge sur mobile.

### Administration
- La barre latérale utilise le mot-symbole LinKs actualisé.
- Harmonisation de la palette claire/sombre avec l’écosystème DomotiK, mais **surfaces sobres, professionnelles et lisibles**, sans effet néon envahissant.
- Pas de modification de l’organisation, des formulaires, des outils ou des statistiques.

### 🔒 Compatibilité
- Aucun changement de schéma SQLite, sauvegardes, URL courtes, jetons de redirection ni comptages.
- Aucun changement des contenus publics ou des réglages des thèmes personnels.
- Mise à jour de l’image Docker en conservant exactement les volumes existants.

### ✅ Contrôles
- Tests de rendu desktop/mobile, contraste, présence du logo de footer et version dynamique.
- Tests de non-régression « Apparence » : comparaison de la géométrie du profil et des cartes, plutôt qu’identité stricte des anciennes couleurs.
- CI fonctionnelle et Docker requis avant publication.

### 🚀 Publication

Image Docker : `ghcr.io/mick7784/links:V1.308` — AMD64 et ARM64. Conserver les volumes et la configuration de l'installation existante ; la publication GitHub ne redémarre pas automatiquement le VPS.

## V1.307

### 🔗 Liens courts discrets

- Les nouveaux liens de partage utilisent un **code opaque de 9 caractères directement à la racine du domaine**, par exemple `https://links.domotik-studio.fr/X7mQ9p2Ka` (exemple fictif). Aucun `/go/`, `st_`, `tk_` ni `utm_source` n'apparaît dans l'URL copiée.
- Chaque source de publication possède sa propre URL courte et **stable** pour chaque campagne ou lien privé. La source est enregistrée côté serveur et ne dépend plus d'un paramètre susceptible d'être supprimé lors du partage.
- Changer l'URL de destination conserve le même code court. Recopier le lien d'une même source redonne exactement le même code.
- Le suivi des clics reste actif côté serveur (agrégé, sans identification des visiteurs). Le canal enregistré correspond à l'emplacement choisi au moment de copier, pas nécessairement au site sur lequel une tierce personne repartage ensuite l'URL.

### 🔒 Compatibilité préservée

- **Tous les anciens liens `/go/st_...` et `/go/tk_...`, y compris ceux avec `?utm_source=...`, restent fonctionnels** et conservent leurs compteurs existants.
- Les nouveaux codes sont des alias vers ces mêmes jetons historiques : pas de remise à zéro, de transfert de statistiques ni de double comptage.
- Nouvelle table SQLite **additive** `short_aliases` incluse dans l'export des sauvegardes ; les restaurations d'anciennes sauvegardes conservent les alias déjà publiés sur l'instance.
- Lorsqu'une source à zéro clic est supprimée définitivement, ses codes courts sont révoqués mais **réservés** : ils ne seront jamais réattribués.
- La page publique, les campagnes et les destinations existantes ne changent pas.

### ✅ Tests

- Tests d'URL opaque, sources Instagram/YouTube distinctes, comptabilisation, redirections GET/HEAD, filtrage des robots, changement de destination, archivage, suppression d'une source et compatibilité des sauvegardes.
- Tests navigateurs et construction Docker avec configuration Nginx de routage des codes courts.

**Avant de mettre à jour le VPS :** sauvegardez les volumes Docker/SQLite existants et conservez leur montage pour la nouvelle image.

### 🚀 Mise à jour

Image prévue : `ghcr.io/mick7784/links:V1.307` (Docker AMD64 et ARM64). La release n'effectue aucun redémarrage du VPS : conserver le volume existant pour retrouver toutes les anciennes URL et les statistiques.

## V1.306

### ✨ Liens suivis indépendants des campagnes

- Nouvelle zone **Liens suivis · privés** dans **Liens & campagnes** : créez des liens vers des produits ou des pages externes sans créer de promotion ni afficher de nouveau bloc sur la page publique.
- Chaque lien conserve un identifiant permanent par source de publication : changer le nom ou l'URL de destination ne modifie pas les URL de partage déjà publiées.
- Un lien archivé continue de rediriger et de compter les clics. La suspension de la redirection reste possible sans effacer les statistiques.

### 🔗 Sources de publication personnalisables

- Gestionnaire central permettant d'ajouter, renommer, archiver et restaurer des sources (Instagram Story, YouTube Post, newsletter, réseaux supplémentaires, etc.).
- La source se choisit au moment de copier le lien. Chaque combinaison lien + source possède une URL permanente.
- Source à **zéro clic historique** : suppression définitive, après confirmation de l'utilisateur, avec révocation des URL non utilisées.
- Source ayant reçu au moins un clic : archivage uniquement, avec maintien des anciens liens et des statistiques.
- Sources personnalisées également proposées lors de la copie des liens des campagnes, sans modifier les liens historiques.

### 📊 Statistiques plus lisibles

- Chaque lien suivi possède une fiche repliable affichant un graphique en anneau (donut) et la répartition des clics par source.
- Filtres 7, 14, 30 jours ou total historique. Les compteurs cumulés sont conservés indépendamment de la rétention des agrégats journaliers.
- Les ouvertures des nouveaux liens suivis sont incluses dans les statistiques de liens partagés du tableau de bord, sans fausser le CTR de la page publique.

### 🔒 Données et compatibilité

- Migration SQLite **additive** : nouvelles tables pour les liens suivis, sources et jetons. Aucun effacement ni modification des identifiants des campagnes et liens `/go/st_...` existants.
- Sauvegardes et restaurations étendues aux nouvelles tables. Les liens permanents préexistants sont protégés même lors d'une restauration d'ancienne sauvegarde.
- Les anciennes attributions incertaines ne sont pas réécrites. Les URL externes utilisent le canal choisi lors de leur publication, non une identification du visiteur.
- Préserver les volumes Docker et effectuer une sauvegarde avant la mise à jour de l'installation.

### ✅ Validation

- Tests des liens permanents, changement de destination, redirections, sources à zéro clic, archivage, statistiques, sauvegarde/restauration, interface desktop/mobile et image Docker.

### 🧭 Utilisation dans le back-office

- Ouvrez **Liens & campagnes → Créer un lien suivi** pour enregistrer un produit sans l'afficher publiquement.
- Sélectionnez la source de publication puis copiez l'URL permanente depuis la ligne correspondante.
- Cliquez sur le nom du lien pour déplier son camembert de statistiques et choisir la période de consultation.
- **Gérer les sources** permet de créer, renommer ou retirer des sources avec protection de leur historique.

## V1.305

### ✨ Version installée visible dans le back-office

- La barre latérale de l’administration affiche discrètement la version réelle de LinKs, sous « DomotiK Studio · Administration ».
- Le libellé provient du champ serveur `app_version` déjà utilisé dans les paramètres techniques : il se met à jour automatiquement à chaque nouvelle release et ne peut pas être faussé par la restauration d’une sauvegarde ancienne.
- La présentation respecte les thèmes clair et sombre et les règles existantes de la navigation mobile (pied de la barre latérale masqué sur petits écrans).

### 🔒 Compatibilité et données

- Aucun changement à la base SQLite, à la page publique, aux statistiques, aux campagnes, aux liens `/go/...`, aux destinations ou au volume de données Docker.
- Mise à jour sans migration : conserver le volume `/data` et toutes les autres configurations du conteneur.
- Les liens suivis indépendants des campagnes, les sources personnalisables et les camemberts dépliables restent prévus pour une prochaine version ; ils ne font pas partie de cette release.

### ✅ Vérifications

- Tests automatisés du back-office, y compris l’affichage de la version réelle sur ordinateur et la compatibilité mobile.
- Tests de non-régression de l’application, vérification de la page publique et construction Docker validés en CI.

## V1.304

### ✨ Statistiques et suivi des liens partagés

- Le tableau de bord distingue les **clics effectués sur la page LinKs** des **ouvertures directes de liens partagés**. Chaque campagne affiche désormais ses impressions, clics sur la page, ouvertures externes, clics totaux et CTR de la page sur la période sélectionnée.
- Les liens de campagne copiés depuis l'administration peuvent être attribués à Instagram Story, YouTube Post, Facebook ou TikTok. Le sélecteur ajoute un paramètre `utm_source` sans modifier le jeton de redirection existant.
- Les liens `/go/st_...` sans indication de provenance continuent de fonctionner : leurs nouvelles ouvertures sont comptées comme source non identifiée. Les événements historiques conservent leurs données et leur ancienne classification, clairement signalée comme incertaine.

### 🎨 Tableau de bord plus lisible

- Présentation renforcée des indicateurs : trafic de la page, liens partagés, copies de codes promo et performances des campagnes.
- Sur le graphique quotidien, les barres cyan (visites) et violettes (clics sur la page) apparaissent côte à côte pour éviter tout recouvrement.
- Les campagnes actives mettent en évidence les ouvertures de liens partagés, les clics totaux et le CTR de la page, sans confondre impressions et redirections.
- Mise en forme responsive, vérifiée sur ordinateur et sur mobile, sans modification du design public.

### 🔒 Données et compatibilité

- **Aucune réinitialisation ni réécriture des statistiques historiques**. Les 117 ouvertures précédemment suivies restent conservées dans les compteurs existants ; elles sont reliées à leurs campagnes lors de la lecture des rapports, sans double comptage.
- **Tous les jetons, liens de partage, URL de destination, campagnes et contenus existants sont conservés**. Les liens déjà publiés sur Instagram, YouTube ou ailleurs restent valides.
- Les sauvegardes et restaurations prennent en charge les nouvelles provenances tout en acceptant les anciens événements `instagram-story`.
- Le volume de données Docker existant doit être conservé au déploiement. Effectuer une sauvegarde avant mise à jour ; la release publie l'image sans redémarrer l'installation de production.
- Mise à jour recommandée : sauvegarder le volume actuel, puis remplacer uniquement l'image de l'application par `ghcr.io/mick7784/links:V1.304` et vérifier la page publique et le dashboard après redémarrage.

### ✅ Validation

- Tests Python, JavaScript et scénarios navigateur desktop/mobile validés dans la CI.
- Parcours vérifiés : copie de lien, redirection, conservation des jetons, filtres de sources, statistiques par campagne, restauration et fonctionnement du calendrier.
- Construction Docker et contrôles de santé passés.

## V1.303

### ✨ Paramètres repensés

- Une seule section principale est affichée à la fois : vue d’ensemble, Général, Intégrations, Statistiques, Accès & sécurité, Citations, Partage, Stockage et Sauvegarde & maintenance.
- Navigation latérale persistante sur desktop, sélecteur compact sur mobile. Identité, logo, avatar, description, copyright, URL, fuseau, collecte et règles de sources, configuration YouTube, accès, partage, sauvegarde/restauration et version restent disponibles.
- La vue d’ensemble présente l’identité, YouTube, les statistiques, l’espace occupé, la corbeille, les citations et la version installée. Les cartes ouvrent directement la section correspondante.
- Les listes de fichiers et de citations, ainsi que l’état détaillé de YouTube, sont demandés uniquement lorsque leur section est ouverte.
- Les citations conservent leur contenu, leur ordre, leur activation, leurs imports et leurs actions. Recherche, filtre actif/inactif, compteur et pages de vingt citations évitent une liste de plusieurs centaines de lignes.

### 🗂️ Stockage global des fichiers personnels

- Un inventaire commun couvre les uploads et les anciens fichiers personnels de `/data/assets` : liens, campagnes, profil, raccourcis, icônes, fonds de thèmes et imports. Les références de fichiers présentes dans des réglages supplémentaires sont également protégées.
- Le gestionnaire affiche le total, la répartition par catégorie, la place occupée par la corbeille, les miniatures, tailles, formats, dates et toutes les utilisations connues. Des filtres permettent de consulter une catégorie, les fichiers utilisés ou la corbeille.
- Les fichiers partagés comptent une seule fois dans le total. Toutes leurs catégories et références restent visibles. La dernière catégorie connue est conservée lorsqu’un fichier devient orphelin.
- Un remplacement ou un détachement rend l’ancien fichier éligible à la corbeille uniquement après la disparition de sa dernière référence. Une nouvelle utilisation annule la suppression. Les contenus inactifs, liens archivés et thèmes non actifs restent pris en compte.
- Les fichiers sans référence bénéficient de sept jours avant le nettoyage automatique. La commande Vider la corbeille demande confirmation et vérifie les références sous le verrou des données avant la suppression physique.
- Les assets livrés avec LinKs sont exclus. Les copies exactes d’assets système conservées par une ancienne migration sont aussi protégées ; les fichiers personnels qui remplacent un asset de même nom restent gérés.
- Les anciens fichiers découverts au premier démarrage bénéficient d’un délai complet de sept jours, quelle que soit leur date historique. Les liens symboliques ne sont pas supprimés par le gestionnaire.

### ⚡ Optimisations et refactor ciblé

- L’aperçu des liens et campagnes conserve son iframe et son document. Les saisies rapides sont regroupées avant une mise à jour du contenu, sans recharger ses feuilles de style à chaque frappe.
- Les images de la bibliothèque de contenus sont créées à son ouverture ; les miniatures sont chargées progressivement. La grille d’icônes des raccourcis s’ouvre à la demande et n’est plus reconstruite à chaque modification du libellé ou de la destination.
- L’éditeur de raccourcis présente d’abord l’icône actuelle, le libellé et la destination. La liste déroulante d’icônes redondante est masquée ; la bibliothèque assure le choix. Sur mobile, un bouton donne accès à l’aperçu.
- L’actualisation du snapshot public passe par une liste centrale de mutations pertinentes. Son contenu est comparé avant toute écriture atomique ; les opérations privées, les tests et les analyses ne le régénèrent pas. Le choix de citation du secours statique est stable, tandis que l’API publique conserve son choix aléatoire.
- Les écritures de fichiers des uploads, de la configuration initiale, des migrations historiques, des imports de thèmes et des restaurations utilisent le même utilitaire atomique.
- L’inventaire réutilise les métadonnées existantes et limite les accès disque. Le nettoyage évite de relire toutes les références pour chaque fichier : le verrou des données couvre la vérification et l’ensemble de la suppression.
- Les anciennes règles de présentation des Paramètres devenues inutiles sont retirées. Aucun changement de framework ni refonte générale du rendu public.

### 🔄 Compatibilité et migrations

- Migration additive : table interne `user_files`, avec date et dernière catégorie connue. La table et les échéances de corbeille V1.302 sont conservées. Aucun format de contenu ni format de sauvegarde n’est remplacé.
- Identifiants, liens, campagnes, statistiques, thèmes, uploads, sauvegardes, migrations historiques, Story et Creator Studio restent compatibles.
- Déploiement avec le volume existant : sauvegarder le volume, récupérer la version V1.303 puis redémarrer selon la procédure habituelle. Le démarrage effectue l’inventaire et la migration sans supprimer de fichier utilisateur nouvellement découvert.

### ✅ Validation et publication

- 79 tests Python, 10 tests JavaScript et 12 suites navigateur, avec parcours desktop/mobile réels.
- Régressions ciblées : références partagées, remplacement, anciens assets, protection système, réutilisation de corbeille, migration additive, snapshot sans réécriture, navigation des neuf sections, chargements à la demande, citations et aperçu persistant.
- Validation Docker et smoke tests avant publication ; images `linux/amd64` et `linux/arm64` publiées sous `ghcr.io/mick7784/links:V1.303` et `latest`, avec égalité des digests contrôlée par la publication.
- Le déploiement sur le serveur est réalisé par le propriétaire après publication, conformément au fonctionnement convenu.

## V1.302

### 🐛 Corrections

- Les uploads des liens, campagnes, profils, thèmes et raccourcis restent liés à leur éditeur. Les réponses tardives sont ignorées, l’état d’import est affiché et l’enregistrement est protégé pendant l’opération.
- Les anciennes dates des liens classiques sont à nouveau visibles, modifiables et supprimables, permettant leur réactivation.
- Les images sont réellement décodées et contrôlées : PNG, JPEG, WebP et GIF, fichiers corrompus ou tronqués rejetés, limites de taille et de dimensions. La même validation couvre uploads, configuration initiale, thèmes et restaurations.
- Les adresses d’images non supportées sont refusées sans élargir la CSP. Les pastilles des statistiques affichent leurs couleurs. HEX, sélecteur de couleur et opacité restent synchronisés.
- Une ancienne sauvegarde ne change plus la version du logiciel affichée. La modification manuelle de version a été retirée. L’ordre des sections est explicitement celui de l’administration.

### ✨ Nouveautés

- Paramètres > Stockage affiche l’espace utilisé, les fichiers personnels, leurs miniatures, leur taille et leurs utilisations, ainsi que la corbeille.
- Les fichiers inutilisés sont suivis dans une corbeille et supprimés automatiquement après sept jours. Une réutilisation annule leur suppression. Les actions Nettoyer et Vider la corbeille vérifient toutes les références avant suppression ; les assets système sont exclus.
- L’archivage des campagnes détache leur image tout en conservant noms, dates, URL, codes promo, statistiques et liens Story. Un fichier partagé reste protégé par ses autres utilisations.

### 🎨 Interface

- Les cartes « Offre du moment » gagnent environ 12 % de hauteur sur desktop et 6 % sur mobile. Le dégradé reste limité à la zone texte pour montrer davantage l’image, notamment carrée, sans déplacer le texte du bas de la carte.

### ⚙️ Technique

- Le healthcheck Docker vérifie le backend et SQLite ; `/nginx-healthz` conserve un contrôle séparé de Nginx.
- Validation d’images avec Pillow et ajout d’une table SQLite additive `upload_trash`. Le suivi automatique tourne au démarrage puis chaque heure, et après les modifications de contenus.
- Tests de régression sur les réponses tardives, images invalides, anciennes sauvegardes, références partagées, délais de corbeille, campagnes archivées et rendu desktop/mobile. Le smoke Docker provoque puis répare une indisponibilité SQLite pour vérifier le healthcheck réel.

### ⬆️ Mise à jour

- Les identifiants, contenus, statuts et statistiques existants sont conservés. Les campagnes déjà archivées libèrent leur image à la mise à jour ; les fichiers nouvellement identifiés comme inutilisés bénéficient du délai complet de sept jours.
- Les fichiers historiques valides restent utilisables. Une sauvegarde contenant une image réellement corrompue est refusée sans remplacer les données actuelles.
- Les sauvegardes restent au format 3 et ajoutent une métadonnée `software_version`, indépendante du numéro de format. Elles contiennent les images référencées, pas la corbeille ; sauvegardez le volume serveur si vous souhaitez conserver aussi les fichiers inutilisés.
- Comme convenu, la mise en production sur votre serveur se fait après votre pull de la release ou de l’image Docker publiée.

## V1.301

### ✨ Nouveautés

- Six fonds photo panoramiques : communauté, création, maison connectée, boutique, contact professionnel et lifestyle. Les filtres Tous, Photos, Dégradés et LinKs se combinent avec les catégories métier.
- Réseaux & raccourcis affiche désormais les vraies icônes. L’éditeur partage la bibliothèque d’icônes existante et permet de rechercher, importer, remplacer ou supprimer une icône personnelle.
- Aperçu public Desktop/Mobile avec le thème actif et réglages dédiés aux couleurs, bordures, dimensions, opacité, effets et survol des raccourcis.

### 🐛 Corrections

- Les raccourcis vers une ancre sont correctement rendus. Les anciennes icônes e-mail restent compatibles.
- Les sauvegardes conservent les icônes personnelles et restent compatibles avec les sauvegardes précédentes.

### Mise à jour

- Migration automatique additive : identifiants, liens, ordre, statuts et statistiques sont conservés. Les douze fonds déjà disponibles et le rendu LinKs Original restent inchangés.
- Les icônes personnelles acceptent PNG, JPEG, WebP ou GIF jusqu’à 1 Mo. Préférez une image carrée avec fond transparent.

## V1.3

### ✨ Nouveautés

- Bibliothèque de douze fonds panoramiques, dont les six images historiques inchangées ; catégories et sélection instantanée dans l’éditeur des liens.
- Bibliothèque d’icônes complétée : Home Assistant, téléphone, vidéo, podcast, blog, téléchargement, calendrier et localisation. Les pictogrammes historiques sont conservés.

### 🎨 Thèmes / Apparence

- Nouveau menu Apparence : Mes thèmes, Éditeur, Bibliothèque et Import / Export.
- LinKs Original permanent et restaurable, plus trois thèmes personnalisés : création, édition, renommage, duplication, activation et suppression.
- Éditeur de 91 variables visuelles : couleurs, typographie, profil, cartes, icônes, médias, effets, dimensions et éléments secondaires.
- Aperçu de la page publique avec les données réelles, modes Desktop/Mobile, états actif/édition et modifications non enregistrées.
- Color pickers, HEX avec opacité, nuanciers, couleurs récentes, variantes et avertissements de contraste.
- Format portable `.links-theme` v1 et CSS Expert : valeurs contrôlées, images personnelles embarquées, fonds système référencés par ID, aucun code arbitraire.

### 🐛 Corrections

- Fermeture explicite des connexions SQLite utilisées au démarrage et pour la sauvegarde de migration.
- Préservation des réponses HTTP lors des rejets anticipés sous Windows.
- Champs des paramètres protégés pendant leur chargement pour éviter qu’une réponse tardive écrase une saisie.

### ⚙️ Technique

- Thèmes persistants dans SQLite, migration additive avec LinKs Original actif ; contenu, campagnes, icônes, images et préférences du back-office conservés.
- Sauvegarde/restauration des thèmes et de leurs images personnelles dans le format applicatif v3.
- Publication explicite après tests et build : réservation persistante et idempotente, tags Git/Docker et Release GitHub portant la même version, notes structurées et CHANGELOG communs.
- Un commit, une PR ou une validation seule ne publie plus de version de production.

### ⬆️ Mise à jour

- Conserver le volume `/data`, la configuration et le fichier Compose. Aucun changement d’apparence n’est appliqué à une instance existante sans action de son administrateur.
- Les fichiers de thème utilisent le moteur version 1. Ils n’exécutent ni CSS arbitraire ni JavaScript.

Les entrées de production sont ajoutées après validation, à partir du même fichier que les notes GitHub Release.

## V1.203

### Améliorations

- Version persistante réservée sur `main`, selon l’état historique du dépôt.

## V1.201

### Interface

- Fond Amazon et aperçu public corrigés, formulaires lien/campagne séparés, images de profil remplaçables et thèmes du back-office conservés.
- Dashboard, statistiques des Stories et codes promo harmonisés.

## V1.2

### Interface

- Refonte du back-office et fiabilisation de la copie des codes promo.
