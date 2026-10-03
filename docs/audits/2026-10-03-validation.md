# Validation du chantier LinKs — 3 octobre 2026

Branche : `work/backoffice-2026-10-03`. Baseline : `fda9ea20c0a3f126a26ab8afa9bb57231f907875` (V1.1). [PR de revue et CI](https://github.com/Mick7784/links/pull/21). Le SHA final et le nombre de fichiers sont disponibles dans la PR. La version reste V1.1.

## Résultat et périmètre

L’audit initial est conservé dans [2026-10-03.md](2026-10-03.md). Navigation mobile, métriques séparées, archives, planning, mécanismes de migration et restauration existants étaient déjà fonctionnels. Les principaux problèmes concernaient le formulaire dense, l’aperçu classique simulé, les erreurs derrière une modale et une identité produit confondue avec celle de l’utilisateur.

- Administration sombre par défaut, cyan/violet subtils, thème clair et préférence système conservés.
- Identité produit SVG autonome avec K stylisé : navigation, favicon, setup, login et README. Le visuel de référence reste intact. Aucune identité produit ajoutée à la page utilisateur.
- Dashboard : hiérarchie KPI, Stories et codes rapprochés, toutes les métriques et filtres conservés. Graphique superposé et interaction clavier conservés.
- Réglages : accès rapides aux sections, titres explicites, version regroupée dans une zone technique. Sources vidéo inchangées.
- Formulaire : titre/destination/description/icône/image/état, nom interne repris du titre si vide, options avancées, dates accessibles selon le type, image retirable, formats et limite réellement imposés indiqués.
- Aperçus : même renderer et CSS que le public, actions neutralisées dans une iframe sans scripts. Le chargement des images réajuste la hauteur.
- Erreurs : feedback dans la modale active ; déplacement des dates sans perte de focus lors de la saisie.

## Bugs corrigés

1. Amazon : l’icône calculée n’était pas utilisée sans image. SVG vectoriel sans police externe, détection par domaines explicites et choix Amazon pris en charge par le backend, la configuration et son schéma. Les domaines trompeurs ne sont pas reconnus.
2. Copie : aucune solution après refus/absence de Clipboard API. Fallback `execCommand` uniquement compté si son résultat confirme le succès ; aucun clic partenaire ni navigation. Identifiant stable récupérable depuis l’id du bloc.
3. Origin : l’adresse publique pouvait être validée avec `/` final puis conservée sans normalisation. La comparaison stricte refusait alors un Origin navigateur légitime. Normalisation lors de la sauvegarde et du démarrage ; origines étrangères toujours refusées.
4. Aperçu classique : icône remplacée par deux lettres et CTA artificiel. Renderer public partagé, retrait d’image vérifié.
5. Messages d’erreur : notification extérieure à la modale non visible ou inaccessible. Feedback interne ajouté.

Ces causes sont reproduites sur des données temporaires. L’incident exact de l’instance de production n’a pas été inspecté : aucun accès ni écriture en production.

## Vérifications

- Python : 29 tests backend, 11 tests instance/auth/migration/backup.
- JavaScript : 6 tests métriques, dates/fuseaux/DST et API vidéo.
- Quatre scripts navigateur : public, administration, Stories et instance/setup/login.
- Administration et public : 320, 390, 768, 1024/1440 selon les scénarios, thèmes, noms longs, tableaux, modales, menus, clavier, contrastes et absence de débordement horizontal.
- Setup/login : 320, 768 et 1440 ; code bootstrap, refus, interruption, connexion et branding chargé sans connexion préalable.
- Copie : vrai presse-papier, refus Clipboard API avec copie fallback réelle, échec total sans événement, réponse 204, SQLite, dashboard, source, historique, absence de popup et de clic partenaire ; Origin étranger 403.
- Contenus : classique minimal, e-mail, création/édition, image ajoutée/retirée, valeurs historiques conservées, campagne, brouillon, duplication et archivage.
- Non-régression : auth local/external, sauvegardes v1/v2/v3, restauration, migration V1.1, images/assets, statistiques historiques, citations, Stories, rotation des offres, vidéo, fallback public et analytics off.
- CI PR : build Docker temporaire et smoke tests, sans publication. La première CI a réussi ; vérifier également le statut du dernier SHA de la PR avant déploiement.
- Revue visuelle des captures desktop/mobile et vérification syntaxe/diff.

## Limites et travaux reportés

Pas de designer, cropper, bibliothèque d’images/logos, refonte vidéo ou ajout marketing. Aucune dimension minimale/ratio obligatoire n’est imposé pour les uploads ; les images externes restent soumises à la politique CSP existante. Clipboard peut encore échouer si le navigateur refuse les deux méthodes : le message d’échec est alors affiché et aucune copie n’est comptée. DNT/GPC et analytics off empêchent volontairement la collecte.

Le test Docker CI est AMD64 ; aucun build multiarchitecture publié. Les scénarios navigateur utilisent Chromium ; Firefox/Safari n’ont pas été exécutés. La fidélité des aperçus est assurée par le composant partagé à leur largeur disponible ; leur aperçu Desktop n’est pas une reproduction de toute la page à 1440 px.

## Déploiement recommandé après décision explicite

Aucun déploiement n’a été effectué. Ne pas fusionner la PR mécaniquement : le workflow existant de `main` peut publier `latest`.

1. Vérifier le succès de la CI sur le SHA final et conserver l’identifiant exact de l’image V1.1 actuellement utilisée.
2. Télécharger une sauvegarde applicative et sauvegarder le volume existant. Conserver le fichier Compose, ses variables et le nom du projet de l’instance actuelle.
3. Sur une machine de build autorisée, récupérer la branche et construire une image locale dédiée au SHA, sans tag `latest` :

```bash
git checkout work/backoffice-2026-10-03
LINKS_SHA=$(git rev-parse HEAD)
docker build -t "links-candidate:$LINKS_SHA" .
docker save "links-candidate:$LINKS_SHA" -o links-candidate.tar
```

4. Transférer puis charger l’image sur le serveur prévu : `docker load -i links-candidate.tar`.
5. Dans le projet Compose existant, créer `compose.candidate.yaml` en remplaçant `SHA_FINAL` par le SHA validé :

```yaml
services:
  links:
    image: links-candidate:SHA_FINAL
```

6. En conservant le même répertoire/projet et le fichier Compose réel de l’instance, exécuter :

```bash
docker compose -f compose.yaml -f compose.candidate.yaml up -d --no-deps --pull never links
```

Ne jamais supprimer/recréer le volume et ne pas remplacer la configuration de l’instance par le Compose générique du dépôt. Si le fichier Compose ou le service portent un autre nom dans l’installation, reprendre leurs noms existants.

7. Contrôler la santé, login/external, liens/images, dernière vidéo, copie promo et compteur dashboard, Stories, citations et téléchargement de sauvegarde. Vérifier que l’adresse publique et l’Origin navigateur correspondent.
8. Retour arrière : remettre l’image V1.1 exacte dans l’override et relancer la même commande, avec le même volume. Aucune migration de schéma n’a été ajoutée par ce chantier. Ne restaurer la sauvegarde de données que si cela est nécessaire et après conservation des éventuelles actions effectuées depuis.
