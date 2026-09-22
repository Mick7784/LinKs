# DomotiK Studio — Liens

Une page responsive qui rassemble les réseaux sociaux, les liens utiles et la dernière vidéo YouTube. Réalisée en HTML, CSS et JavaScript, sans framework.

## Personnaliser

- **Contenu** : modifier `links.json` pour le profil, les réseaux et les liens.
- **YouTube** : renseigner l’identifiant de la chaîne dans `latestVideo.channelId`.
- **Images** : placer les fichiers dans `site/assets/`.
- **Apparence** : modifier `site/style.css` et `site/icons.css`.

Les options sont décrites dans `links.schema.json`. Le fichier `site/config.js` est généré automatiquement.

## Lancer avec Docker

```sh
docker build -t links .
docker run --rm -p 127.0.0.1:8080:8080 links
```

Ouvrir [localhost:8080](http://localhost:8080).

## Mises à jour

GitHub Actions construit et publie l’image après une modification de `main`, ainsi que toutes les trois heures pour actualiser la vidéo YouTube.

Une fois la publication terminée, récupérer la nouvelle image et redéployer le site pour appliquer les changements.
