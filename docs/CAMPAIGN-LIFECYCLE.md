# Cycle de vie automatique — étape 2

Cette étape prolonge le [moteur de sélection](CAMPAIGN-SELECTION.md) sur la base V1.324. Elle réutilise `content_blocks`, `counts`, `story_links`, `short_aliases`, les réglages et le stockage existants. Aucun changement de schéma, de contrat PulSe, de formulaire ou de version de production.

## Campagnes concernées

Les campagnes `promo` et `featured` non archivées, non retirées et non brouillons sont traitées dès que leur fin est atteinte (`end_at <= instant courant`). Une campagne désactivée avec une fin passée reste concernée. Les brouillons sont conservés comme travaux non publiés ; les archives et les contenus retirés restent inchangés.

Les permanentes, sans `end_at`, ne sont jamais expirées. Les liens classiques ne sont pas concernés, même s’ils possèdent des dates historiques. Une fin historique seule reste une campagne ponctuelle, conformément à l’étape 1.

## Décision et conservation

- Avec une impression, un clic public, une ouverture de lien partagé ou une copie de code : archivage.
- Sans activité mais avec une référence à préserver : archivage.
- Sans aucune statistique ni référence à préserver : suppression de la ligne de campagne et retrait de son éventuelle préférence d’affichage horaire du calendrier.

La recherche porte sur **tout l’historique de `counts`**, sans filtre de période ni de source et même si la collecte est aujourd’hui désactivée. Elle utilise les identifiants `block:…`, les correspondances statistiques historiques et l’identifiant enregistré dans chaque copie de code. Une ligne statistique historique est conservée même si son compteur vaut zéro.

Tout `story_links.promotion_id` conserve la campagne : cette ligne porte la destination du lien long et des liens courts qui pointent vers son jeton. Le zéro clic, le marquage de suppression du lien ou la révocation d’un alias ne permettent pas de supprimer cette identité. Les correspondances `analytics.metric_aliases` et les références entrantes déclarées par des clés étrangères protègent également la campagne, y compris lorsque la clé prévoit une suppression en cascade.

L’étape 4 ajoute une exception pour la provenance interne `campaign_partners`, qui appartient à la campagne : elle est supprimée avec une campagne réellement inutilisée. Cette exception ne concerne aucun compteur ni lien publié. Voir le [contrat d’affiliation](CAMPAIGN-AFFILIATION.md).

L’archivage ne modifie que `archived` et `updated_at`. Aucun compteur, identifiant, destination, jeton ou association de publication n’est réécrit. La campagne quitte les listes actives et la sélection publique, mais reste dans Archives ; les rapports retrouvent ses clics, impressions, ouvertures et copies à partir des mêmes identifiants. Les redirections existantes gardent leur fonctionnement.

## Exécution et concurrence

Un traitement de fond démarre avec le processus serveur, sans requête publique ni ouverture du back-office. Il s’exécute immédiatement, puis attend la prochaine fin connue, avec une vérification au plus toutes les 30 secondes. Une création, modification, restauration ou modification des réglages réveille le traitement. Le moteur de sélection continue d’exclure les campagnes dès l’échéance, indépendamment de ce délai de maintenance.

Les dates avec décalage sont comparées en UTC ; les anciennes dates sans décalage utilisent le fuseau actuel de l’instance lu dans SQLite. Aucune comparaison lexicale de dates n’est utilisée. Une date de fin historique illisible est ignorée sans suppression.

La décision et les écritures partagent une transaction `BEGIN IMMEDIATE`, sous le verrou de données existant. SQLite sérialise aussi les écritures d’une autre connexion ou d’un autre processus. Les métriques publiques valident leur campagne et enregistrent l’événement dans une seule transaction : si l’événement est accepté avant le nettoyage, il protège l’historique ; si la campagne a déjà été supprimée, la requête est rejetée et ne crée pas de statistique orpheline. La génération des liens partagés utilise déjà ce même verrou transactionnel.

Une nouvelle passe ne touche plus les lignes archivées ou supprimées. Les erreurs de stockage ou de base sont journalisées puis retentées. Un historique de copie illisible suspend la passe et annule sa transaction, pour éviter une suppression fondée sur des données incomplètes. Le secours public est réécrit atomiquement après validation de la transaction ; sa réécriture est retentée même si les données n’ont pas changé depuis la passe précédente.

## Images et sauvegardes

Le nettoyage des campagnes **ne supprime aucun fichier**. Les archives continuent de référencer leurs images. Une image partagée avec une autre campagne, un lien, un profil ou un thème conserve son propriétaire et reste protégée par le stockage existant. Une image devenue orpheline suit la corbeille habituelle et son délai de grâce de sept jours.

Les sauvegardes continuent d’inclure les archives, leurs statistiques, liens et images. La restauration conserve ses garanties antérieures ; toute ponctuelle restaurée avec une fin passée sera à nouveau traitée. Pour réutiliser une ancienne campagne, il faut lui donner une nouvelle période.

## Tests

`python3 scripts/campaign_lifecycle_test.py` couvre les quatre catégories de statistiques sur toute leur durée de vie, l’absence d’activité, les liens longs/courts à zéro clic, les références révoquées et historiques, les clés étrangères, les permanentes et brouillons, les dates exactes et changements d’heure, les relances, les images partagées, les nettoyages concurrents, une écriture SQLite externe, les métriques tardives, les erreurs et la relève automatique sans requête HTTP.

La suite est intégrée au workflow GitHub existant. La PR ne déclenche aucune fusion, publication de release, publication d’image ni intervention sur le VPS.
