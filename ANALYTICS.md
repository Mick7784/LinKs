# Statistiques Links

La même image sert la page publique sur 8080 et le backoffice sur 8081. Le port 8080 expose uniquement la collecte `POST /metrics`, jamais la consultation des statistiques.

## Activation

- Définir `STATS_PASSWORD` (au moins 16 caractères) dans l'environnement du conteneur.
- Monter un volume persistant sur `/data`. Conserver ce volume pendant les mises à jour et le sauvegarder.
- Le volume doit être accessible en écriture par l'utilisateur `nginx` de l'image. Un nouveau volume nommé Docker reprend les permissions du répertoire `/data` de l'image.
- Sans mot de passe, la collecte et le backoffice restent désactivés ; la page de liens fonctionne normalement.
- `ANALYTICS_ORIGIN` désigne l'origine publique exacte (par défaut `https://links.domotik-studio.fr`).

Créer une ressource HTTPS Pangolin pour le backoffice vers le port **8081** du conteneur, avec authentification Pangolin activée. Ne pas publier ce port directement sur Internet. La connexion supplémentaire utilise `admin` et `STATS_PASSWORD`. Conserver la ressource publique Links sur **8080**.

## Mesures

Pages vues à l'affichage de la page, clics (dont clic milieu), source UTM prioritaire sur le domaine référent. Les liens fonctionnent même si la collecte échoue. Aucun cookie, stockage navigateur, identifiant visiteur ou IP dans la base de statistiques. Do Not Track et Global Privacy Control désactivent la collecte côté navigateur.

Sources reconnues : YouTube, Instagram, Facebook, TikTok, Discord, Google, newsletter et DomotiK Studio. Les autres référents sont regroupés sous « Autre site », les autres valeurs UTM sous « Autre campagne ». Les URLs complètes de provenance ne sont pas enregistrées.

Exemples : `?utm_source=youtube`, `?utm_source=instagram`, `?utm_source=domotik-studio`.

Compteurs agrégés par jour (Europe/Paris), source et intitulé du lien. Conservation glissante de 400 jours avec purge à la collecte. Les intitulés différents sont comptabilisés séparément. La carte « Dernière vidéo » regroupe les vidéos successives.

Les vues ne sont pas des visiteurs uniques et les clics pour 100 vues ne sont pas un taux de conversion. La collecte côté navigateur peut être bloquée, omise ou falsifiée ; ce ne sont pas des chiffres de facturation. Aucune reconstitution de l'historique avant activation.

La base ne contient pas les IP ; les journaux techniques du reverse proxy peuvent en contenir indépendamment. L'accès `/metrics` n'est pas journalisé par Nginx dans cette image.

## Vérification

`python3 scripts/analytics_test.py` vérifie l'authentification, l'isolation des ports, les entrées invalides, l'attribution, la persistance et les mises à jour concurrentes. Le workflow teste aussi le conteneur avec un système de fichiers en lecture seule et un répertoire de données accessible en écriture.
