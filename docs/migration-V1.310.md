# V1.310 — conservation et migration

La migration ajoute `retired` à `content_blocks` et `top_buttons`, une table `tracking_source_keys` et une identité d’instance dans les réglages. Elle ne renumérote ni les contenus, ni les sources, ni les jetons, ni les codes courts, et ne réécrit pas les événements.

Une ancienne base est sauvegardée dans `/data/pre-v1310-database.db` avant l’ajout des colonnes. Archiver ou retirer une campagne conserve désormais son image ; les fichiers déjà supprimés par une version antérieure ne peuvent pas être reconstruits.

## Restauration conservatrice

Les contenus manquants dans une ancienne sauvegarde sont conservés comme archives. Les boutons absents sont retirés et restaurables. Les destinations déjà publiées restent celles de l’instance courante ; une restauration ne remplace pas un code ou un jeton par celui d’un autre objet. Les suspensions des liens privés et les révocations existantes restent respectées.

Pour chaque clé `(jour, source, type, lien)`, la restauration garde le plus grand agrégat connu. Elle ne somme pas des snapshots qui se recouvrent. Les correspondances statistiques et règles de sources déjà présentes sont préservées ; une origine historique incertaine n’est pas réattribuée par supposition.

La prévisualisation utilise les mêmes contrôles que la restauration sans écrire de fichiers ni remplacer de tables. Après confirmation, `/data/restore-safety/<identifiant>/` reçoit une sauvegarde cohérente SQLite et les fichiers locaux actuellement référencés. Conserver aussi une sauvegarde externe complète du volume. Ces copies de sécurité ne sont pas exposées par les routes publiques et ne sont pas nettoyées automatiquement.

Les sauvegardes v1/v2/v3 restent importables. Les nouvelles sauvegardes identifient leur instance : la fusion d’une autre instance avec un historique déjà présent est refusée, car un maximum par clé ne reconstitue pas deux flux indépendants. Transférer vers une installation vide. Les anciens formats ne portent pas toujours cette identité : leur origine doit être vérifiée avant import.

Le JSON n’exporte pas les comptes administrateur, la clé YouTube privée ni toute la corbeille. Une récupération complète et un retour d’image nécessitent donc une sauvegarde cohérente du volume, de la configuration et de l’image précédente. Ne pas lancer une ancienne image sur la base modifiée comme procédure de rollback improvisée.

## Politique d’historique

La collecte ne supprime plus les anciens compteurs. Une requête de rapport est limitée à 400 jours, indépendamment de la conservation. Les cumuls des liens privés et les sources de publication restent distincts des visites et clics de la page. Les anciennes sources génériques sont liées une fois à l’identité connue lors de la migration ; si le libellé avait déjà disparu, la migration ne devine pas une association.

Les nouveaux partages utilisent l’identifiant stable de la source. Une source ayant un jeton, un code publié ou une correspondance historique est archivée lors de son retrait, même sans clic mesuré.

## Validation et production

Les tests utilisent des installations temporaires et des copies de volumes synthétiques représentant l’ancien schéma. Ils comparent les identifiants, événements, destinations et intégrités SQLite après deux démarrages. Les images des deux architectures sont exécutées dans des conteneurs jetables de CI.

**Aucune copie du volume réel n’étant disponible, la validation de migration sur cette copie reste à effectuer avant déploiement. Aucun accès au VPS n’est prévu dans ce chantier.** La publication GitHub/GHCR n’effectue pas de redémarrage de production.
