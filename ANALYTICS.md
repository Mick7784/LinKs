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

Pour les promos du carousel, une impression est ajoutée uniquement lorsque la diapositive devient effectivement visible. Les impressions ne sont pas incluses dans les totaux globaux de clics du dashboard ; elles servent au calcul du CTR propre à chaque promo.

Les vues ne sont pas des visiteurs uniques et les clics pour 100 vues ne sont pas un taux de conversion. La collecte côté navigateur peut être bloquée, omise ou falsifiée ; ce ne sont pas des chiffres de facturation. Aucune reconstitution de l'historique avant activation.

La base ne contient pas les IP ; les journaux techniques du reverse proxy peuvent en contenir indépendamment. L'accès `/metrics` n'est pas journalisé par Nginx dans cette image.

## Vérification

`python3 scripts/analytics_test.py` vérifie l'accès privé sans mot de passe, l'isolation des ports, les entrées invalides, l'attribution, la persistance et les mises à jour concurrentes. Le workflow teste aussi le conteneur avec un système de fichiers en lecture seule et un répertoire de données accessible en écriture.



## Partage et sauvegarde

Dans Réglages, « Partager Links » génère une adresse avec `utm_source` pour chaque plateforme reconnue. Le bouton de copie fonctionne aussi avec un accès HTTP privé lorsque le navigateur autorise la copie ; sinon le champ est sélectionné pour une copie manuelle.

« Télécharger une sauvegarde » exporte un fichier JSON versionné contenant les blocs (archives comprises), les boutons, les réglages, les compteurs et les images importées utilisées par ces contenus. Les anciennes images inutilisées et les journaux serveur ne sont pas inclus. Les fichiers statiques fournis par l'image Docker ne sont pas dupliqués.

La restauration remplace les données actuelles après confirmation dans l'interface. Elle valide la structure, les compteurs, les images et la capacité des promotions, puis réalise la modification dans une transaction. Les images restaurées utilisent de nouveaux noms : une erreur d'écriture ne remplace pas les fichiers existants. Télécharger une sauvegarde actuelle avant de restaurer permet de revenir en arrière.

Limites : 64 Mo pour le JSON complet, 40 Mo d'images avant encodage et 4 Mo par image. Au-delà, sauvegarder le volume `/data` avec les outils du serveur. Le téléchargement et la restauration ne sont accessibles que sur le port privé 8081.

L'import initial depuis `links.json` est désormais marqué en base : vider les listes ne provoque plus leur réapparition au redémarrage. La restauration des archives respecte la limite des trois promotions et le remplacement d'une promotion est atomique. Le dashboard conserve les identifiants stables en base et affiche leurs noms publics ; le ratio global est libellé « Clics pour 100 vues ».


## Liens Stories Instagram

Dans les mises en avant et promos, le bouton 🔗 génère puis copie un lien stable `/go/st_…`. Les 16 caractères aléatoires identifient la promotion, pas un visiteur. Une duplication reçoit un lien différent. L’URL doit être HTTP(S), sans identifiants, et ne peut pas pointer vers Links lui-même.

La route publique répond en HTTP 302 avec `Cache-Control: no-store`, vers l’URL partenaire actuelle. Elle conserve les paramètres d’affiliation. Modifier la destination ou le nom ne change pas le lien. Une promotion archivée, désactivée, programmée ou expirée peut encore être atteinte via sa Story : l’accès direct est indépendant de sa visibilité sur la page. Une promotion supprimée ou dont l’URL devient invalide répond 410 ; un identifiant inconnu répond 404. Aucun de ces cas n’enregistre de clic. HEAD et les robots de prévisualisation connus ne sont pas comptés.

`story_links` conserve seulement l’association permanente token/promotion, son nom de secours et sa date de création. Les métriques réutilisent `counts` avec `kind=story`, `source=instagram-story` et `link=story:TOKEN:HH`. Les clics sont agrégés par date et heure de Paris, sans cookies, IP, empreinte ou identifiant visiteur. L’heure est donc une tranche agrégée, pas un journal d’événements individuels. La conservation des compteurs reste de 400 jours. Les codes réservés ne sont jamais réattribués.

Le dashboard présente séparément l’activité de la page Links et les redirections Story. Les clics Story ne créent pas de page vue, ne gonflent pas les clics de la page, son graphique, son Top 5 ni son taux de clic. La carte Story suit la période et le filtre source : Instagram inclut les Stories ; Instagram Story permet de les isoler. Sources principales regroupe les visites de la page et les clics directs Story, une fois chacun, avec une note qui explique cette mesure.

Les statistiques utilisent le nom interne actuel de la promotion, y compris après archivage. Lors d’une suppression définitive, ce dernier nom est conservé comme libellé historique et tous les clics Story restent accessibles. Les sauvegardes version 2 incluent les associations Story et les compteurs. Les anciennes sauvegardes version 1 restent acceptées et préservent l’historique Story existant. Une restauration ne peut jamais attribuer un code réservé à une autre promotion.

Validation : `python3 scripts/analytics_test.py`. Le parcours navigateur `scripts/story-browser-test.cjs` vérifie copie, redirection, statistiques, filtres, URL dynamique, archivage et suppression aux tailles desktop/mobile ; il est exécuté par GitHub Actions avec Playwright.
