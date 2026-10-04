# Changelog

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
