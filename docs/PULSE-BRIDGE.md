# PulSe — passerelle privée LinKs

Cette passerelle est développée sur une branche séparée. Elle ne change ni la page publique LinKs, ni l'administration, ni les anciennes URL suivies.

## Contrat HTTP

La ressource PulSe reste une application Docker distincte. Elle contacte `http://domotik-links:8080` via le réseau Docker interne `pangolin`.

Trois endpoints serveur-à-serveur sont ajoutés :

- `GET /api/pulse/links` retourne seulement les **liens suivis indépendants** actifs, et jamais les liens classiques ni les campagnes ;
- `GET /api/pulse/stats` conserve par défaut les statistiques sur sept jours ; `?days=7` et `?days=30` choisissent la période (jours à zéro inclus). `period` indique la période, `total` le nombre de clics sur cette période, `today` les clics du jour, `last7` toujours les clics des sept derniers jours, `stories` les clics issus des Stories sur la période, et `days` les points datés du graphique. Une période différente, vide ou répétée renvoie HTTP 400 ;
- `POST /api/pulse/story-link` avec `{"type":"campaign","id":"..."}`, `{"type":"independent","id":"..."}` ou `{"type":"youtube","id":"<ID vidéo YouTube>"}` prépare une URL courte suivie attribuée à Instagram Story. Seules les promotions actives, les liens suivis disponibles et la vidéo courante de la source YouTube LinKs sont autorisés. Le client ne choisit jamais la destination vidéo.

Les campagnes et les liens indépendants conservent leur historique existant : PulSe appelle les méthodes `story_link` et `tracked_links.token_link` déjà utilisées par LinKs. Aucune réattribution ou purge des jetons historiques.

## Sécurité

Toutes les requêtes exigent `Authorization: Bearer <secret>` ; le secret est lu via `PULSE_BRIDGE_TOKEN` dans **l'environnement du conteneur LinKs**. Il doit contenir au moins 32 caractères aléatoires (64 caractères hexadécimaux recommandés).

- Variable absente ou trop courte : routes PulSe désactivées (HTTP 404).
- Jeton incorrect : HTTP 401.
- Le navigateur n'envoie jamais le jeton ; **seul le backend PulSe** le possède.
- Cette API ne peut pas consulter les utilisateurs, sessions, sauvegardes ni modifier les campagnes.
- La source Instagram Story est déterminée côté LinKs et n'est pas choisie par le client.
- Le chemin `/api/pulse/` est routé par Nginx vers le serveur applicatif interne, sans exposer d'accès administrateur générique.

## Procédure de recette (après CI et revue)

1. Sauvegarder le volume `/data` de LinKs et conserver une possibilité de retour arrière.
2. Générer le secret : `openssl rand -hex 32`. Ne pas le copier dans Git ni l'envoyer en conversation.
3. Vérifier la CI de la branche et publier **volontairement** une image LinKs incluant le changement ; ne pas déployer une branche Git comme `latest` sans validation.
4. Ajouter `PULSE_BRIDGE_TOKEN` à la stack LinKs dans Dockhand, puis mettre à jour **son image seulement**, en conservant intégralement les variables, le volume et le réseau.
5. Ajouter **le même secret** à la stack PulSe, avec `LINKS_PUBLIC_URL=http://domotik-links:8080` et éventuellement `LINKS_BRIDGE_URL=http://domotik-links:8080`.
6. Redéployer PulSe avec reconstruction de son image. Ne pas modifier la ressource Pangolin `pulse-test.domotik-studio.fr`, cible `http://pulse-story-spike-test:4173`, vérification `/healthz`.
7. Vérifier les offres actives, les liens suivis, les statistiques réelles et les liens courts distincts. Tester une publication Instagram sur Samsung.
8. Vérifier que les liens classiques n'apparaissent pas, que les compteurs ne changent pas lors de la simple copie et que les URLs publiées continuent à fonctionner après un redémarrage.

## Vérifications

```bash
python3 -m unittest discover -s scripts -p 'pulse_bridge_test.py'
python3 -m unittest discover -s scripts -p 'analytics_test.py'
```

`stories` compte des ouvertures de liens attribuées aux Stories, pas des publications. Il s'agit d'un sous-ensemble des clics de `total`, à ne pas additionner à ce total. La carte locale « Stories déclarées » doit être retirée de l'interface PulSe V1.1.

## Extension préparatoire pour PulSe V1.1

Le choix 7/30 jours est additif : aucune migration, création de jeton, modification de redirection ou écriture des compteurs lors de la consultation. Le fuseau est celui configuré par LinKs. Les anciennes réponses à sept jours conservent leurs champs et valeurs.

Les liens existants sont réutilisés par campagne ou couple lien/source ; ils ne prouvent pas l'attribution à une publication Instagram précise. Aucun classement « top publications » n'est fourni. La source vidéo existante est `/latest-video.json`. À la préparation explicite d'une vidéo, la passerelle vérifie son ID contre cette source, crée ou réutilise un lien privé déterministe dans `tracked_links` (catégorie YouTube), puis utilise `tracked_links.token_link` et les redirections existantes. Sa destination est fixée à `https://www.youtube.com/watch?v=<ID>` : une nouvelle dernière vidéo ne modifie pas les anciennes Stories. Aucun changement de schéma ni réattribution des jetons existants. Une vidéo devenue ancienne au moment de la préparation exige une actualisation PulSe. Un lien désactivé/archivé n'est pas réactivé ; une destination modifiée dans l'admin est refusée à la préparation.

L'application PulSe V1.1 est développée dans le dépôt séparé `Mick7784/PulSe`, à partir des sources V1 récupérées dans le Compose Dockhand du propriétaire. Cette PR LinKs est une dépendance distincte, à valider et publier avant d'utiliser les fonctions YouTube/30 jours. Elle ne publie et ne déploie pas PulSe.
