# DomotiK Studio — Liens

Page statique responsive, sans dépendance JavaScript externe, sans traceur ni cookie ajouté. Portrait et logo fournis par Mickaël. Les assets sont servis localement.

## Personnaliser

Modifier uniquement `links.json` : profil, réseaux, ordre et contenu des cartes. Le fichier est validé à chaque build : une URL ou une date incorrecte bloque la publication plutôt que de mettre un site incomplet en ligne.

### Dernière vidéo YouTube

Le bloc `latestVideo` récupère automatiquement le titre, la miniature et le lien direct vers la dernière vidéo publiée sur la chaîne :

```json
"latestVideo": {
  "channelId": "UC-bkgpkh9sGcnX8oqFea3Uw"
}
```

La carte affiche une miniature 16:9, un bouton de lecture, le titre et la date de publication. Un clic ouvre YouTube dans un nouvel onglet. Si la miniature échoue, la carte reste utilisable. Les miniatures sont chargées depuis `i.ytimg.com`, autorisé explicitement par la politique de sécurité du serveur.

Le workflow GitHub est aussi relancé toutes les trois heures afin de reconstruire l’image avec la vidéo la plus récente.

Exemple de lien temporaire :

```json
{
  "title": "Promo du moment",
  "url": "https://exemple.fr",
  "expiresAt": "2026-10-31"
}
```

`"2026-10-31"` laisse le lien visible jusqu'à la fin du 31 octobre, heure de Paris. Pour une heure précise : `"2026-10-31T18:00"`. Le lien disparaît à l'heure prévue, y compris pour une page déjà ouverte. Les propriétés admises sont documentées dans `links.schema.json`, ce qui donne aussi l'autocomplétion dans VS Code.

Les images locales se placent dans `site/`, puis se référencent par leur chemin web, par exemple `"image": "/assets/mon-image.webp"`. Sans image, une icône graphique peut être choisie avec `"icon"`.

Le style est dans `site/style.css`. Le portrait et le logo se trouvent dans `site/assets/`. L'e-mail de contact est public sur le site.

## Prévisualiser

Depuis le dépôt : `node scripts/build-links.mjs && python3 -m http.server 8080 --directory site`, puis ouvrir http://localhost:8080.

## Publication GitHub Packages

À chaque push sur `main`, GitHub Actions construit et teste le conteneur, puis publie une image multiarchitecture AMD64/ARM64 :

- `ghcr.io/mick7784/links:latest`
- `ghcr.io/mick7784/links:sha-<SHA complet du commit>`

Les pull requests construisent et testent sans publier. Un lancement manuel est également disponible dans Actions. L'authentification utilise le `GITHUB_TOKEN` fourni par GitHub, avec `contents: read` et `packages: write`. Aucun secret personnel n'est nécessaire pour construire. Autoriser Actions dans les paramètres du dépôt si nécessaire. Les éventuels quotas de minutes/stockage GitHub s'appliquent.

La visibilité du dépôt n'est pas modifiée. Le package peut être privé : vérifier sa visibilité dans GitHub Packages. Ne pas le rendre public sans décision explicite.

## Dockhand

1. Attendre la réussite du workflow dans GitHub → Actions.
2. Pour un package privé, ajouter un registre dans Dockhand → Settings → Registries : URL `ghcr.io`, utilisateur `Mick7784`, mot de passe = jeton GitHub personnel **classic** avec `read:packages`. Ne jamais committer ce jeton. La clé SSH du dépôt ne remplace pas cet accès registre.
3. Créer la stack depuis le dépôt Git déjà connecté, branche `main`, fichier `compose.yaml`. Ne pas activer la construction : l'image est déjà fabriquée sur GitHub.
4. Déployer sur le même VPS que Pangolin. Le réseau Docker externe `pangolin` doit exister.
5. Dans Pangolin, utiliser un site local/sans tunnel donnant accès au réseau du serveur, puis une ressource HTTP avec cible `domotik-links`, port `8080`. Ne pas utiliser `localhost` ni l'IP publique du VPS comme cible. Le nom Docker est accessible depuis Traefik/Gerbil via le réseau partagé.
6. Choisir le domaine de la ressource, par exemple `links.domotik-studio.fr`. Le wildcard DNS existant couvre ce sous-domaine. Pour le domaine racine, il faut une entrée DNS explicite vers le VPS.
7. Désactiver l'authentification de la ressource **du site public uniquement**, sans modifier celle des interfaces d'administration.

Aucun port supplémentaire n'est publié sur Internet par cette stack.

## Mises à jour et retour arrière

La publication GHCR ne redéploie PAS automatiquement Dockhand. Après un workflow réussi, relancer le déploiement avec **Re-pull images** pour récupérer la nouvelle image. Éviter une synchronisation Git immédiate qui pourrait partir avant la fin du build. Une automatisation de mise à jour d'image pourra être ajoutée dans Dockhand après validation du premier déploiement.

Pour revenir à une version connue, définir dans la stack `IMAGE_TAG=sha-<SHA complet>` puis redéployer. Sans cette variable, le Compose utilise `latest`.
