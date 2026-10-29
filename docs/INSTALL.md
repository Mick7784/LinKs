# Installation et mise à jour

Cette documentation décrit une installation générique, sans configuration de production.

## Nouvelle installation

Le fichier `compose.yaml` est un exemple pour une nouvelle installation. Il conserve `/data` dans un volume nommé et lie les accès à la machine locale. Adapter l’exposition à votre hébergement et utiliser HTTPS pour une administration accessible à distance.

```sh
docker compose up -d
docker compose logs links
```

Dans cet exemple local, la page et l’administration sont accessibles sur `http://localhost:8080` et `http://localhost:8081`. Le code de setup est affiché dans les logs au premier démarrage et conservé dans `/data/setup-code`, avec accès restreint. Ne jamais le publier.

Ouvrir l’administration, saisir le code et suivre l’assistant. Confirmer l’adresse publique : elle peut être différente de l’adresse administrative.

`ADMIN_ORIGIN` déclare l’origine HTTPS administrative pour les cookies sécurisés. Links ne fait pas confiance à des en-têtes de proxy fournis arbitrairement par un client.

## Mise à jour d’une instance antérieure à V1.1

**Conserver votre compose, votre volume et votre protection d’accès actuels. Ne pas remplacer une stack existante par l’exemple destiné aux nouvelles installations.**

1. Sauvegarder le volume complet de façon cohérente, y compris SQLite et ses éventuels fichiers WAL, les uploads et tout fichier d’instance. Utiliser la sauvegarde SQLite ou copier lorsque le service n’écrit plus.
2. Avant de changer d’image, exécuter `scripts/preserve-instance.py` avec Python **dans l’ancienne image**. Le script ne contacte aucun service et ne collecte aucun secret.
3. Vérifier `/data/legacy-instance.json` et les images dans `/data/assets`. Le script conserve aussi un instantané SQLite et une copie des uploads/assets dans `/data/pre-v11-volume`.
4. Inclure ces fichiers dans la sauvegarde externe du volume.
5. Mettre à jour uniquement l’image lorsque la release est publiée et validée.

Exemple générique :

```sh
docker cp scripts/preserve-instance.py NOM_DU_CONTENEUR:/tmp/preserve-instance.py
docker exec NOM_DU_CONTENEUR python3 /tmp/preserve-instance.py
```

Les options `--root` et `--data` permettent d’adapter les chemins. Le script refuse d’écraser un transfert existant ou un asset différent. SQLite reste prioritaire. Les URL historiques `/assets/...` continuent de fonctionner via les fichiers persistants.

Une instance historique est marquée configurée et reste en accès externe. Aucun compte local n’est imposé. Si un asset requis ou l’adresse publique manque, la migration s’arrête ; ne pas contourner cette vérification.

## Sauvegarde applicative

Le format version 3 comprend contenus, boutons, paramètres, statistiques, liens Story, citations, uploads référencés et assets persistants. Les formats 1 et 2 restent acceptés. Les tables ou réglages qu’un ancien format ne connaît pas sont conservés ; les anciennes sources et snapshots ne sont pas renommés.

Les comptes et sessions administrateur ne sont pas exportés. Une restauration conserve le mode d’accès et les identifiants du système qui reçoit la sauvegarde, puis invalide les sessions locales. Garder les sauvegardes privées.

Pour restaurer sur une nouvelle installation, terminer d’abord son assistant et créer son administrateur, puis importer la sauvegarde depuis ce compte.

L’export applicatif ne remplace pas une sauvegarde du volume. La restauration remplace les données incluses après validation ; les uploads reçoivent de nouveaux noms pour éviter d’écraser les fichiers courants.

Les exports récents omettent la catégorie des liens suivis. Le nouvel importeur accepte les fichiers v1/v2/v3 avec ou sans cet ancien champ et l'ignore. Cette compatibilité va vers la nouvelle application : une ancienne image peut refuser un nouvel export sans catégorie.

## Suppression des catégories de liens suivis

Cette évolution comprend une migration de retrait de colonne, contrairement aux migrations additives historiques. Lire [la procédure dédiée](MIGRATION-CATEGORIES.md) et la tester sur une copie isolée avant une mise à jour autorisée. SQLite 3.35.0 minimum est requis. Le premier démarrage sauvegarde la base complète dans `pre-category-removal/<identifiant>/analytics.db`, vérifie sa conservation, puis retire uniquement `tracked_links.category`. Toute erreur bloque le démarrage et annule la suppression. Les installations neuves créent directement la table sans cette colonne.

## Vidéo facultative

Activer la section dans les paramètres et configurer la source côté installation. YouTube Data API v3 se configure dans Paramètres → YouTube (chaîne, clé, test). Le fournisseur Creator Studio historique reste compatible : `CREATOR_STUDIO_URL` et `CREATOR_STUDIO_API_KEY` restent dans la configuration sécurisée ; ne jamais committer la clé.

Seuls titre, URL, miniature et date quittent le relais. Sans source disponible, la carte est masquée.

## Accès externe

Installer et vérifier votre protection externe avant de choisir ce mode dans Paramètres > Accès. Le mode externe ne constitue pas lui-même une authentification. Les nouvelles installations démarrent en mode local.

## Retour arrière

Conserver l’image précédente, le code sauvegardé et le volume pré-migration. Sauvegarder également l’état courant avant un retour arrière : ne pas écraser les données créées depuis la mise à jour. Un retour d’image ne restaure pas automatiquement le volume. Après retrait de `tracked_links.category`, l'ancienne image peut nécessiter l'ancien schéma : utiliser un couple image/volume cohérent et suivre [les précautions de retour arrière](MIGRATION-CATEGORIES.md#retour-arrière).

## Validation et releases

`VERSION` est la référence du dépôt pour la version officielle. Les patches intermédiaires ne la changent pas. Le workflow existant valide les tests et une image temporaire ; la branche de préparation ne publie aucune image. Numérotation, README et date sont finalisés uniquement lors d’une release validée.
