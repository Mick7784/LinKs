# LinKs · by DomotiK

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/links-logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/links-logo-light.png">
  <img src="docs/assets/links-logo-light.png" alt="LinKs by DomotiK" width="320">
</picture>

LinKs est une page de liens auto-hébergée, personnalisable et accompagnée d’un back office. Elle réunit les liens, réseaux sociaux et offres d’un créateur, d’un projet ou d’une communauté sur une page adaptée aux ordinateurs et aux mobiles.

## Fonctionnalités

### Page publique

- Liens et boutons de réseaux sociaux organisables.
- Dernière vidéo facultative lorsqu’une source est configurée.
- Cartes de campagnes illustrées, carrousel et copie de codes promo.
- Citation facultative dans le footer.
- Identité, images et copyright personnalisables.

### Campagnes

- Programmation avec dates et heures dans le fuseau choisi.
- Activation, brouillons, priorités et ordre manuel.
- Jusqu’à trois offres simultanées, contrôle des chevauchements et proposition de créneau.
- Duplication, archives et liens directs pour les Stories.

### Statistiques

- Visites, clics, sources, impressions et CTR.
- Activité des Stories présentée séparément.
- Copies de codes promo et taux de copie, avec historique du code réellement copié.
- Histogramme quotidien : visites en cyan et clics en violet, superposés sur le même axe.
- Vue de 14 jours par défaut ; périodes de 7, 30 ou 90 jours disponibles, avec conservation des jours sans activité.
- Valeurs lisibles, repères intermédiaires et détail au survol, au toucher ou au clavier.
- Répartition des sources en donut, avec total, valeurs et pourcentages.
- Filtres par période et par source, sans modification des compteurs historiques.

### Back office

L’administration possède sa propre identité LinKs ; votre page publique conserve votre identité.

- Navigation latérale sur ordinateur et menu compact sur mobile.
- Thèmes clair, sombre et système, avec préférence conservée.
- Dashboard avec visites, clics, CTR, Stories, copies promo et campagnes en cours.
- Cartes Stories et copies promo harmonisées : totaux en en-tête, métriques alignées et détails secondaires.
- Formulaire de lien classique centré sur le titre, la description, l’URL, l’icône et l’image ; réglages de campagne présentés séparément.
- Aperçu utilisant le rendu public, avec image de fond et overlay.
- Logo et avatar gérés par aperçu, remplacement et retrait.
- Animations discrètes respectant la préférence de réduction des animations.

Gestion des contenus, campagnes, boutons, paramètres, citations et statistiques. Les citations peuvent être ajoutées individuellement, en masse ou importées depuis un fichier texte, dans une limite de 300.

## Installation et premier démarrage

Les nouvelles installations disposent d’un assistant de configuration :

1. Démarrer Links avec un stockage persistant.
2. Récupérer le code initial dans la console de l’installation.
3. Ouvrir l’administration et créer le premier compte.
4. Renseigner le nom affiché et, si souhaité, un logo et une description.
5. Ajouter un premier lien.
6. Confirmer l’adresse publique et le fuseau horaire.
7. Choisir d’activer ou non les statistiques.
8. Vérifier le résumé et terminer la configuration.

La page publique reste neutre tant que la configuration n’est pas terminée. Le code initial devient inutilisable après validation. YouTube et les réseaux supplémentaires ne sont pas obligatoires.

Les instructions générales se trouvent dans [la documentation d’installation](docs/INSTALL.md).

## Authentification

**Mode local :** connexion administrateur intégrée, utilisée par défaut sur une nouvelle installation.

**Mode externe :** protection par un outil externe, un reverse proxy sécurisé ou un VPN. Links n’impose aucun fournisseur. Cette protection doit être en place avant d’activer ce mode.

Les installations historiques conservent leur mode externe lors de la migration.

## Personnalisation

Les informations de l’assistant restent modifiables depuis le back office : identité, logo, avatar, copyright, adresse publique, fuseau et statistiques. Liens, réseaux, campagnes et citations utilisent leurs éditeurs existants.

La vidéo est facultative. Désactiver les statistiques laisse la page et son administration fonctionnelles.

## Confidentialité

Les statistiques sont facultatives et agrégées. Elles comptabilisent des actions, pas des personnes uniques. La collecte ne crée ni cookie analytics ni identifiant visiteur ; aucune adresse IP n’est stockée dans la base de statistiques. Do Not Track et Global Privacy Control sont respectés.

Une copie de code est une action, sans indication d’achat. Les compteurs sont conservés pendant 400 jours. Les sessions administrateur utilisent un cookie distinct, réservé à la connexion.

## Version actuelle

Version du code : **V1.202**.

L’image `ghcr.io/mick7784/links:latest` inclut les correctifs et améliorations du dashboard intégrés sur `main`. Elle est publiée pour **AMD64 et ARM64** ; une image `sha-<commit>` permet de sélectionner un build précis. Chaque publication validée réserve une version persistante et publie également un tag Docker numéroté.

Les corrections suivent V1.201, V1.202… ; la prochaine version fonctionnelle est V1.3, suivie de V1.301… Chaque merge validé sur `main` incrémente automatiquement `VERSION`. Une réservation associée au commit source garantit qu’une relance ne double pas l’incrément ; son commit `[skip ci]` évite les boucles. Le champ `version` du workflow permet un jalon explicite (V1.3, V2.1…). À V1.299, un jalon explicite est requis. La création d’une page GitHub Release reste facultative.

## Dernières mises à jour

Les mises à jour intégrées à V1.201 comprennent :

- Back office sobre dans l’esprit d’un dashboard SaaS, avec le K officiel et des logos adaptés aux thèmes clair/sombre.
- Dashboard analytics : barres quotidiennes rapprochées et animées, lecture des valeurs, tooltips et donut des sources.
- Présentation uniforme des Stories et codes copiés, avec conservation des données et calculs existants.
- Logo de l’administration ouvrant le dépôt GitHub du projet.
- Fond de carte Amazon rétabli et traitement de son icône dédié.
- Aperçu des liens corrigé, images de profil visibles et séparation des formulaires lien/campagne.

Ces changements concernent principalement l’administration. Ils n’imposent pas l’identité LinKs à la page publique de l’utilisateur.

## Mise à jour et sauvegarde

Effectuer une sauvegarde avant de mettre à jour. Conserver le fichier Compose, le volume `/data`, les images persistantes et la configuration existante ; mettre à jour uniquement le service LinKs. La publication d’une image ne redémarre pas automatiquement votre instance.

Les sauvegardes applicatives v1, v2 et v3 restent compatibles. Le format v3 comprend les contenus, paramètres, statistiques, citations et images référencées. Les comptes administrateur ne sont pas exportés. Voir [installation, migration et sauvegarde](docs/INSTALL.md) pour les précautions et la procédure complète.

## Historique des versions

### V1.201 — correctifs et améliorations de présentation

Fond Amazon, aperçu fidèle, remplacement/retrait des images de profil, formulaires lien/campagne distincts, thèmes et dashboard analytics améliorés. Image disponible via `latest`, sans nouvelle release numérotée pour les mises à jour de présentation.

### V1.2 — refonte du back office

Navigation et formulaires simplifiés, identité LinKs by DomotiK et fiabilisation de la copie des codes promo.

### V1.1 — 2 octobre 2026

Installation générique avec assistant sécurisé, authentification locale facultative pour les instances historiques, configuration persistante et migration conservant le mode externe. Sauvegarde/restauration compatible incluant citations, assets et historique des codes copiés. Cartes d’offres, dashboard, éditeur de campagnes, citations et pictogramme Amazon conservés. Licence MIT.

### V1.046 — 2 octobre 2026

Cartes d’offres immersives, titre public et code promo dans l’éditeur, aperçu de campagne, gestion des citations et version persistante affichée dans le footer.

## Licence

Links est distribué sous [licence MIT](LICENSE). Utilisation, modification et redistribution sont autorisées selon les termes de cette licence.

## Origine

LinKs a été créé initialement pour DomotiK Studio. Cette origine ne conditionne pas la configuration d’une nouvelle installation.

### Configuration YouTube

Dans Paramètres → YouTube, renseignez une chaîne (identifiant UC…, @nom ou URL) et une clé YouTube Data API v3, puis testez la connexion. LinKs lit les vidéos publiques depuis la playlist d’uploads, ignore les publications privées et futures, et met les résultats en cache pendant cinq minutes. La clé reste côté serveur ; `YOUTUBE_API_KEY` permet aussi une configuration serveur prioritaire. La clé saisie est conservée dans le volume persistant, hors sauvegarde JSON : renseignez-la de nouveau lors d’un transfert vers une autre installation.
