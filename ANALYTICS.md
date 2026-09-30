# Statistiques Links

La même image sert la page publique sur 8080 et le backoffice sur 8081. Le port 8080 expose uniquement la collecte `POST /metrics`, jamais la consultation des statistiques.

Le même service SQLite stocke désormais les blocs de contenu, les boutons du haut et les réglages du profil. Les tables existantes de compteurs ne sont ni supprimées ni recréées. Au premier démarrage, les liens et boutons de `links.json` sont importés si les tables de contenu sont vides.

Les images ajoutées dans le back-office sont limitées à 4 Mo (JPEG, PNG, WebP ou GIF) et enregistrées dans `/data/uploads`. Le volume `links-stats` existant suffit donc pour conserver statistiques, contenus et visuels.

## Activation

- Définir `ANALYTICS_ENABLED=true` dans l'environnement du conteneur. Aucun mot de passe applicatif n'est demandé.
- Monter un volume persistant sur `/data`. Conserver ce volume pendant les mises à jour et le sauvegarder.
- Le volume doit être accessible en écriture par l'utilisateur `nginx` de l'image. Un nouveau volume nommé Docker reprend les permissions du répertoire `/data` de l'image.
- Sans activation, la collecte et le backoffice restent désactivés. Pour la migration, la présence de l'ancienne variable `STATS_PASSWORD` active encore le service mais sa valeur n'est plus utilisée pour l'authentification. `ANALYTICS_ENABLED=false` désactive explicitement le service.
- `ANALYTICS_ORIGIN` désigne l'origine publique exacte (par défaut `https://links.domotik-studio.fr`).

Le backoffice est réservé au réseau privé : créer une ressource privée VPN Pangolin TCP vers le port **8081** du conteneur. L'accès est contrôlé par le VPN ; il n'y a plus d'authentification dans l'application. Supprimer toute ancienne ressource publique pointant vers 8081 et ne pas publier ce port sur Internet. Conserver la ressource publique Links sur **8080**.

## Mesures

Pages vues à l'affichage de la page, clics (dont clic milieu), source UTM prioritaire sur le domaine référent. Les liens fonctionnent même si la collecte échoue. Aucun cookie, stockage navigateur, identifiant visiteur ou IP dans la base de statistiques. Do Not Track et Global Privacy Control désactivent la collecte côté navigateur.

Sources reconnues : YouTube, Instagram, Facebook, TikTok, Discord, Google, newsletter et DomotiK Studio. Les autres référents sont regroupés sous « Autre site », les autres valeurs UTM sous « Autre campagne ». Les URLs complètes de provenance ne sont pas enregistrées.

Exemples : `?utm_source=youtube`, `?utm_source=instagram`, `?utm_source=domotik-studio`.

Compteurs agrégés par jour (Europe/Paris), source et identifiant stable du lien. Conservation glissante de 400 jours avec purge à la collecte. Les anciens compteurs basés sur les intitulés restent lisibles. La carte « Dernière vidéo » regroupe les vidéos successives.

Les vues ne sont pas des visiteurs uniques et les clics pour 100 vues ne sont pas un taux de conversion. La collecte côté navigateur peut être bloquée, omise ou falsifiée ; ce ne sont pas des chiffres de facturation. Aucune reconstitution de l'historique avant activation.

La base ne contient pas les IP ; les journaux techniques du reverse proxy peuvent en contenir indépendamment. L'accès `/metrics` n'est pas journalisé par Nginx dans cette image.

## Vérification

`python3 scripts/analytics_test.py` vérifie l'accès privé sans mot de passe, l'isolation des ports, les entrées invalides, l'attribution, la persistance et les mises à jour concurrentes. Le workflow teste aussi le conteneur avec un système de fichiers en lecture seule et un répertoire de données accessible en écriture.


