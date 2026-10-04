# Changelog

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
