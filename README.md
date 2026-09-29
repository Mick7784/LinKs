# DomotiK Studio — Liens

Une page responsive qui rassemble les réseaux sociaux, les liens utiles et la dernière vidéo YouTube. Réalisée en HTML, CSS et JavaScript, sans framework.

## Personnaliser

- **Contenu** : modifier `links.json` pour le profil, les réseaux et les liens.
- **YouTube** : les données viennent de Creator Studio à chaque ouverture de la page. `latestVideo` active la carte ; sa chaîne doit être celle sélectionnée dans l’export Creator Studio.
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

GitHub Actions construit et publie l’image après une modification de `main`. Aucune tâche programmée n’est nécessaire pour la vidéo.

Une fois la publication terminée, récupérer la nouvelle image et redéployer le site pour appliquer les changements.

## Connecter Creator Studio dans Dockhand

1. Dans Creator Studio → Paramètres → API, activer la publication YouTube et sélectionner uniquement DomotiK Studio dans les chaînes exportées. Créer une clé nommée Links.
2. Reprendre le service de `compose.yaml` : il utilise le réseau existant `pangolin` et l’adresse interne `http://creator-studio-api:3001/api/export/youtube`.
3. Dans les variables d’environnement de la stack Dockhand, définir `CREATOR_STUDIO_API_KEY` avec cette clé. Ne pas la committer dans Git.
4. Après publication de l’image, tirer la nouvelle image et recréer le conteneur Links une fois.

Le navigateur lit `/latest-video.json`. Un relais local transmet uniquement titre, URL, miniature et date ; ni clé ni revenus ne sont publiés. La fraîcheur dépend de la collecte existante de Creator Studio. Aucun appel YouTube n’a lieu pendant le build. Sans clé, si la source échoue ou si aucune vidéo n’existe, la carte reste masquée et les autres liens fonctionnent.

Vérification : ouvrir `/latest-video.json` sur le site ; la réponse doit être la vidéo seule. Une réponse 503 indique une configuration absente, 502 une source inaccessible, une clé refusée ou des données invalides.
