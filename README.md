# Links

Links est une page de liens auto-hébergée, personnalisable et accompagnée d’un back office. Elle réunit les liens, réseaux sociaux et offres d’un créateur, d’un projet ou d’une communauté sur une page adaptée aux ordinateurs et aux mobiles.

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
- Filtres par période et par source.

### Back office

Gestion des contenus, campagnes, boutons, paramètres, citations et statistiques. Les citations peuvent être ajoutées individuellement, en masse ou importées depuis un fichier texte, dans une limite de 300.

## Installation et premier démarrage

La version en préparation inclut un assistant pour les nouvelles installations :

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

Dernière version publiée : **V1.046 — 2 octobre 2026**.

**V1.1 est en préparation.** Elle n’est pas encore publiée ; la date et le résumé définitifs seront renseignés lors de sa validation.

## Nouveautés V1.1 en préparation

- Configuration générique persistante et assistant initial.
- Connexion locale et maintien de la protection externe.
- Migration des instances historiques et conservation des assets.
- Sauvegardes incluant citations, images et nouveaux paramètres.
- Cartes d’offres cliquables et suivi des copies de codes promo.
- Dashboard enrichi, éditeur promo / mise en avant corrigé.
- Citations compactes, limite de 300 et suppression globale.
- Pictogramme Amazon dédié.

## Historique des versions

### V1.046 — 2 octobre 2026

Cartes d’offres immersives, titre public et code promo dans l’éditeur, aperçu de campagne, gestion des citations et version persistante affichée dans le footer.

## Licence

Links est distribué sous [licence MIT](LICENSE). Utilisation, modification et redistribution sont autorisées selon les termes de cette licence.

## Origine

Links a été créé initialement pour DomotiK Studio. Cette origine ne conditionne pas la configuration d’une nouvelle installation.
