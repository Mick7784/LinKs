# DomotiK Studio — Liens

Une page de liens légère et responsive pour rassembler les réseaux sociaux, les ressources et la dernière vidéo YouTube de DomotiK Studio.

Réalisée en HTML, CSS et JavaScript natif, sans framework ni dépendance JavaScript côté navigateur.

## Fonctionnalités

- Profil personnalisable : nom, description, portrait et logo.
- Liens et réseaux sociaux configurables depuis un fichier JSON.
- Dernière vidéo YouTube avec miniature 16:9, titre et date de publication.
- Cartes mises en avant et indication des liens affiliés.
- Liens temporaires avec date d’expiration.
- Thème sombre, navigation au clavier et prise en compte des préférences de réduction des animations.
- Image Docker pour servir le site avec Nginx.

## Structure du projet

```text
links.json              Contenu de la page
links.schema.json       Schéma de configuration
scripts/build-links.mjs  Validation et génération de la configuration
site/                   Page, styles, scripts et images
Dockerfile              Construction de l’image
nginx.conf              Configuration du serveur web
.github/workflows/      Vérifications et publication automatisées
```

## Personnalisation

Modifier `links.json` pour changer le profil, les réseaux sociaux et les liens. Les cartes s’affichent dans l’ordre du tableau `links`.

Exemple de carte :

```json
{
  "title": "Une ressource à découvrir",
  "description": "Une courte présentation du contenu.",
  "url": "https://example.com",
  "icon": "website",
  "featured": true
}
```

Les propriétés disponibles sont décrites dans `links.schema.json`. Le script de génération vérifie notamment les champs, les URL et l’existence des images locales.

### Images et apparence

Placer les images dans `site/assets/` et les référencer avec un chemin tel que `/assets/mon-image.webp`.

Les styles se trouvent dans `site/style.css` et `site/icons.css`. La politique de sécurité du serveur autorise les images locales et les miniatures YouTube ; toute autre source externe nécessite une adaptation de cette politique.

### Dernière vidéo YouTube

Renseigner l’identifiant de la chaîne dans `latestVideo.channelId`. L’identifiant commence par `UC` : il ne s’agit pas du nom de chaîne précédé de `@`.

Lors de la construction, le script consulte le flux public YouTube et génère les informations de la dernière vidéo. Aucun accès à un compte YouTube ni clé API n’est nécessaire. La miniature est chargée depuis YouTube lors de la consultation de la page ; un clic ouvre la vidéo dans un nouvel onglet.

Supprimer le bloc `latestVideo` pour désactiver cette fonctionnalité.

> La vidéo est actualisée à la construction de l’image. La publication d’une nouvelle image ne met pas automatiquement à jour un site déjà déployé.

### Liens temporaires

Ajouter `expiresAt` pour masquer une carte à une date donnée :

```json
{
  "title": "Une offre temporaire",
  "url": "https://example.com",
  "expiresAt": "2026-12-31"
}
```

Une date seule inclut toute la journée, en heure de Paris. Une valeur comme `2026-12-31T18:00` indique une heure précise. Sans ce champ, le lien reste visible.

## Développement local

Prérequis : Node.js 24 et Python 3 pour le serveur de prévisualisation. Un accès réseau à YouTube est nécessaire si le bloc `latestVideo` est activé.

Depuis la racine du dépôt :

```sh
node scripts/build-links.mjs
python3 -m http.server 8080 --directory site
```

Ouvrir ensuite [localhost:8080](http://localhost:8080).

Après une modification de `links.json`, relancer le script de génération et actualiser la page. Le fichier `site/config.js` est généré : ne pas le modifier directement.

## Docker

Construire et lancer une instance locale :

```sh
docker build -t links .
docker run --rm -p 127.0.0.1:8080:8080 links
```

Le site est accessible sur [localhost:8080](http://localhost:8080). Le point de contrôle `/healthz` permet de vérifier que le serveur répond.

Pour un hébergement public, adapter le réseau, le domaine et HTTPS à l’environnement de déploiement. Le fichier `compose.yaml` du dépôt est prévu pour un environnement existant et doit être adapté avant réutilisation.

## Publication et mises à jour

GitHub Actions construit et vérifie le conteneur à chaque proposition de modification. Les mises à jour de `main` publient ensuite une image AMD64/ARM64 sur GitHub Container Registry.

Le workflow peut aussi être lancé manuellement et est programmé toutes les trois heures pour actualiser les données YouTube.

Les images utilisent deux formats de tags :

- `latest` pour la dernière publication.
- `sha-<commit>` pour une version associée à un commit.

Attendre la réussite de la publication avant de récupérer l’image et de redéployer le site. Pour revenir à une version précédente, sélectionner le tag du commit souhaité.
