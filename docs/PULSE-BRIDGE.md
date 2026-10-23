# PulSe — passerelle privée LinKs

Cette passerelle est développée sur une branche séparée. Elle ne change ni la page publique LinKs, ni l'administration, ni les anciennes URL suivies.

## Contrat HTTP

La ressource PulSe reste une application Docker distincte. Elle contacte \`http://domotik-links:8080\` via le réseau Docker interne \`pangolin\`.

Trois endpoints serveur-à-serveur sont ajoutés :

- \`GET /api/pulse/links\` retourne seulement les **liens suivis indépendants** actifs, et jamais les liens classiques ni les campagnes ;
- \`GET /api/pulse/stats\` retourne les clics du jour, ceux des sept derniers jours (y compris les journées à 0), les clics issus des Stories, et les sept points du graphique ;
- \`POST /api/pulse/story-link\` avec \`{"type":"campaign","id":"..."}\` ou \`{"type":"independent","id":"..."}\` prépare une URL courte suivie attribuée à Instagram Story. Seules les promotions actives et les liens suivis disponibles sont autorisés.

Les campagnes et les liens indépendants conservent leur historique existant : PulSe appelle les méthodes \`story_link\` et \`tracked_links.token_link\` déjà utilisées par LinKs. Aucune réattribution ou purge des jetons historiques.

## Sécurité

Toutes les requêtes exigent \`Authorization: Bearer <secret>\` ; le secret est lu via \`PULSE_BRIDGE_TOKEN\` dans **l'environnement du conteneur LinKs**. Il doit contenir au moins 32 caractères aléatoires (64 caractères hexadécimaux recommandés).

- Variable absente ou trop courte : routes PulSe désactivées (HTTP 404).
- Jeton incorrect : HTTP 401.
- Le navigateur n'envoie jamais le jeton ; **seul le backend PulSe** le possède.
- Cette API ne peut pas consulter les utilisateurs, sessions, sauvegardes ni modifier les campagnes.
- La source Instagram Story est déterminée côté LinKs et n'est pas choisie par le client.
- Le chemin \`/api/pulse/\` est routé par Nginx vers le serveur applicatif interne, sans exposer d'accès administrateur générique.

## Procédure de recette (après CI et revue)

1. Sauvegarder le volume \`/data\` de LinKs et conserver une possibilité de retour arrière.
2. Générer le secret : \`openssl rand -hex 32\`. Ne pas le copier dans Git ni l'envoyer en conversation.
3. Vérifier la CI de la branche et publier **volontairement** une image LinKs incluant le changement ; ne pas déployer une branche Git comme \`latest\` sans validation.
4. Ajouter \`PULSE_BRIDGE_TOKEN\` à la stack LinKs dans Dockhand, puis mettre à jour **son image seulement**, en conservant intégralement les variables, le volume et le réseau.
5. Ajouter **le même secret** à la stack PulSe, avec \`LINKS_PUBLIC_URL=http://domotik-links:8080\` et éventuellement \`LINKS_BRIDGE_URL=http://domotik-links:8080\`.
6. Redéployer PulSe avec reconstruction de son image. Ne pas modifier la ressource Pangolin \`pulse-test.domotik-studio.fr\`, cible \`http://pulse-story-spike-test:4173\`, vérification \`/healthz\`.
7. Vérifier les offres actives, les liens suivis, les statistiques réelles et les liens courts distincts. Tester une publication Instagram sur Samsung.
8. Vérifier que les liens classiques n'apparaissent pas, que les compteurs ne changent pas lors de la simple copie et que les URLs publiées continuent à fonctionner après un redémarrage.

## Vérifications

\`\`\`bash
python3 -m unittest discover -s scripts -p 'pulse_bridge_test.py'
python3 -m unittest discover -s scripts -p 'analytics_test.py'
\`\`\`

La carte « Stories déclarées » de PulSe est un **compteur local au téléphone**, pas une preuve de publication Instagram. \`stories\` dans les statistiques de l'API compte des ouvertures de liens attribuées aux Stories, pas des publications.
