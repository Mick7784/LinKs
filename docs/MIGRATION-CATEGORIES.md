# Suppression des catégories de liens suivis

Ce document décrit le changement préparé et sa validation, sans autoriser sa publication ou un déploiement. Le nom du lien reste obligatoire. Les catégories des fichiers, des fonds et les regroupements de statistiques sont des concepts distincts et restent inchangés.

## Comportement attendu

Les formulaires, la bibliothèque, l'API et la passerelle PulSe ne classent plus les liens suivis par catégorie. La recherche utilise le nom, les destinations et les notes. Un ancien champ `category` reçu à la création ou à la modification est ignoré. Les réponses et les nouveaux exports JSON n'en contiennent plus.

La suppression ne change ni les identifiants de liens, ni les URL d'origine et de destination, ni les partenaires et règles d'affiliation, ni les sources et plateformes. Les doublons restent détectés et réutilisables. Jetons, URL courtes, redirections, suspensions, archives, campagnes, promotions, compteurs et historiques restent conservés. Les destinations affiliées existantes ne sont pas recalculées.

Le lien vidéo PulSe est identifié par l'ID YouTube, avec un nom obligatoire et une destination fixe. Il réutilise ses anciennes identités et URL publiées sans dépendance à une catégorie. Voir [le contrat PulSe](PULSE-BRIDGE.md).

## Avant une mise à jour d'une instance existante

1. Obtenir une autorisation distincte pour la publication et le déploiement. Conserver les variables, protections d'accès, réseau, Compose et volumes actuels.
2. Sauvegarder hors du volume actif l'ensemble des données persistantes, y compris SQLite de façon cohérente avec son éventuel WAL, les médias, les fichiers d'instance et la configuration. Utiliser l'API de sauvegarde SQLite ou une copie du volume lorsque le service n'écrit plus ; ne pas copier uniquement un fichier `.db` actif.
3. Conserver l'image précédente avec sa référence immuable, les sources correspondantes et la sauvegarde complète du volume.
4. Tester l'image candidate sur une copie isolée et privée du volume réel, sans réseau ou accès de production. Vérifier SQLite 3.35.0 minimum dans cette image, l'espace libre et le temps de démarrage nécessaire à la sauvegarde et aux comparaisons complètes.
5. Comparer avant/après toutes les données conservées, en excluant uniquement `tracked_links.category`. Vérifier les liens courts et longs existants, les liens archivés/suspendus, les affiliations, les sources, les campagnes et les statistiques. Tester aussi la restauration de la sauvegarde sur une autre copie isolée.
6. Ne déclarer le déploiement prêt que lorsque la recette locale, la CI, les images AMD64/ARM64 applicables et l'essai sur copie réelle ont été validés. Ce document n'affirme pas que ces validations externes ont déjà eu lieu.

## Migration SQLite au démarrage

`scripts/analytics.py:init` appelle `scripts/tracked_links.py:remove_legacy_category` avant les autres initialisations et avant l'ouverture des serveurs.

- Sans ancienne colonne : aucune migration ni nouvelle copie de sécurité. Une installation neuve crée directement le schéma sans catégorie.
- Avec ancienne colonne : transaction `BEGIN IMMEDIATE`, clés étrangères actives, contrôle de version, schéma historique reconnu, intégrité et références vérifiées, noms non vides.
- Une dépendance inattendue telle qu'un index sur la catégorie, une vue ou un déclencheur lié à `tracked_links` bloque la migration ; aucun objet personnalisé n'est supprimé automatiquement.
- Une copie SQLite complète est créée dans un dossier unique, voisin de la base : `pre-category-removal/<identifiant>/analytics.db.partial`. L'API SQLite inclut les écritures WAL validées. La copie est réouverte, vérifiée et comparée à la base verrouillée ; elle devient `analytics.db` seulement après validation.
- La commande native `ALTER TABLE tracked_links DROP COLUMN category` retire la colonne. Aucune reconstruction manuelle de table ni désactivation des clés étrangères.
- Avant validation de la transaction, l'intégrité et la conservation sont contrôlées sur toutes les tables : colonnes, références, schémas conservés, valeurs et types SQLite, y compris les doublons. Seul l'ancien champ est exclu.
- Une erreur annule la suppression et empêche le démarrage. Une copie déjà validée reste disponible ; une tentative suivante ne l'écrase pas. Une copie `.partial` n'est pas une sauvegarde validée et n'est jamais utilisée automatiquement.

Après succès, le chemin de la sauvegarde vérifiée est affiché dans le journal. Les démarrages suivants ne recréent ni la colonne ni une nouvelle copie. Les dossiers de sauvegarde ne sont pas purgés automatiquement. Ils contiennent volontairement l'ancien champ et les données complètes pour permettre un retour arrière : les conserver avec les mêmes précautions que le volume. Il ne s'agit pas d'un effacement forensique des anciens fichiers.

La copie SQLite automatique ne remplace pas la sauvegarde externe complète du volume. Une suppression manuelle de dossiers ou une réparation improvisée ne fait pas partie de cette procédure.

## Imports et exports

Le format d'export reste `links-backup` v3. Les nouveaux exports omettent uniquement la clé `category` des liens suivis. Les noms, notes ou URL contenant littéralement le mot `category` sont conservés.

Le nouvel importeur accepte les formats v1/v2/v3 avec ou sans ancien champ et l'ignore, sans recréer la colonne. Les validations strictes des autres champs et les protections des identités publiées restent actives. Une restauration répétée ne doit pas dupliquer les jetons ou gonfler les compteurs. L'aperçu et son annulation n'écrivent aucune donnée.

Cette compatibilité concerne le nouvel importeur : une ancienne image peut refuser un nouvel export sans catégorie. L'export JSON n'inclut pas les comptes administrateur ni l'intégralité du volume ; conserver aussi les sauvegardes historiques.

## Retour arrière

En cas d'échec avant validation, la transaction conserve l'ancien schéma. Ne pas contourner l'erreur ni supprimer ses preuves ; analyser la cause avant une nouvelle tentative.

Après succès, ne pas relancer simplement une ancienne image sur la base migrée : elle peut encore attendre la colonne. Tester d'abord un couple image/volume antérieur cohérent sur une copie isolée. La copie `pre-category-removal/.../analytics.db` permet de retrouver l'ancien schéma SQLite, mais n'est pas à elle seule une sauvegarde du volume.

Avant tout retour arrière autorisé, arrêter les écritures et sauvegarder aussi l'état courant de façon cohérente. Restaurer un ancien instantané après de nouveaux clics ou modifications ferait perdre ces écritures sans réconciliation ; les préserver et définir leur reprise avant tout remplacement. Ne pas improviser de fusion de compteurs.

## Recette reproductible

Uniquement sur des bases temporaires synthétiques, avec Python, Pillow et les données de fuseaux horaires disponibles :

```sh
python3 -B -m unittest discover -s scripts -p '*_test.py' -v
node --test scripts/metrics.test.cjs scripts/dates.test.cjs scripts/video-api.test.mjs scripts/calendar.test.cjs scripts/collection.test.cjs scripts/statistics-charts.test.cjs scripts/partner-report.test.cjs scripts/source-platforms.test.cjs scripts/daily-report.test.cjs
```

Suites ciblées :

```sh
python3 -B -m unittest discover -s scripts -p tracked_categories_migration_test.py -v
python3 -B -m unittest discover -s scripts -p tracked_backup_compatibility_test.py -v
python3 -B -m unittest discover -s scripts -p tracked_category_schema_test.py -v
node scripts/tracked-library-browser-test.cjs
node scripts/tracked-backup-browser-test.cjs
```

Les parcours navigateur requièrent Playwright/Chromium et les ports locaux libres. `PYTHON_PATH`, `CHROMIUM_PATH` et `NODE_PATH` permettent de sélectionner les runtimes. Les fenêtres ordinateur/mobile et thèmes clair/sombre sont contrôlés ; les captures sont facultatives via `UI_SCREENSHOTS`.

La fixture `scripts/fixtures/tracked-categories-v1326.sql` est historique, figée et exclusivement synthétique : ne jamais la charger dans une instance existante. Les tests vérifient notamment conservation exacte, relances, sauvegardes anciennes, noms obligatoires, références invalides, pannes de copie/validation et arrêt brutal avant validation, en journaux DELETE et WAL.

Le workflow `.github/workflows/publish.yml` inclut les trois suites et le parcours de sauvegarde avant ses étapes de build/publication. `scripts/check-images.sh` vérifie aussi le moteur SQLite et l'absence de colonne sur les installations neuves des images jetables. Ces contrôles ne publient rien par eux-mêmes ; aucune modification des déclencheurs ou conditions de release n'est nécessaire.
