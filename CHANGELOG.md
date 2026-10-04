# Changelog

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
