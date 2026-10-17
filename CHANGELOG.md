# Changelog

## V1.310

### 🛡️ Conservation des données et des liens

- Retirer un contenu ou un raccourci conserve son identité, ses statistiques et ses médias. Les éléments restent restaurables depuis les archives ; les campagnes publiées continuent de rediriger.
- Une restauration préserve les compteurs actuels, les contenus ajoutés depuis la sauvegarde, les jetons et codes courts ainsi que les destinations publiées. Les agrégats communs sont conservés au maximum, sans double addition à chaque import.
- Prévisualisation des effets avant confirmation et copie de sécurité SQLite avec les fichiers référencés avant restauration.
- Migration additive : sauvegarde pré-migration, indicateurs de retrait et correspondances stables des anciennes sources, sans recréer les identifiants ni réécrire l’historique.
- La collecte ne purge plus automatiquement les anciens compteurs. Les rapports restent bornés par période.

### 🐛 Fiabilité et confidentialité

- Renommer une source prédéfinie ne change plus son identité de comptage. Une source déjà publiée est archivée même sans clic.
- DNT et Global Privacy Control sont respectés côté serveur sur les liens longs, courts et les métriques.
- Les sauvegardes prennent en charge les SVG historiques passifs, sans autoriser l’upload de SVG ni le contenu exécutable.
- Le secours public inclut les campagnes programmées non privées et est actualisé après l’assistant initial.
- Correction des miniatures de bibliothèque du dashboard, des styles et scripts bloqués par CSP, et de la reprise du carrousel pendant le focus ou le survol. Une commande pause/reprise est disponible.

### 🎨 Administration

- En-tête de barre latérale limité au logo LinKs by DomotiK Studio.
- Cartes KPI uniformes au repos avec un accent discret au survol.
- Sélecteur clair/sombre/système aligné, avec icônes soleil/lune/écran.
- Périodes des liens privés raccordées, raccourcis retirés restaurables, export CSS Expert partagé et contrôles hérités sans effet signalés.

### ✅ Validation et déploiement

- Tests de conservation, migration répétée sur copie d’un volume synthétique, restauration, attribution, confidentialité, médias, CSP et interactions.
- Validation CI des images AMD64 et ARM64 sur données temporaires ; vérification des manifests version/latest.
- Aucun accès au VPS ni utilisation des données de production. La validation sur une copie du volume réel reste à effectuer avant un déploiement en production. Publier l’image ne redémarre pas l’instance.

## V1.309

### Administration : identité DomotiK Studio désormais visible

La V1.308 harmonisait surtout les fonds du back-office ; la différence était difficile à distinguer de la version précédente. Cette mise à jour apporte des repères de marque clairement visibles **sans refonte des fonctionnalités ou de la grille**.

- **Barre latérale** : signature « ÉCOSYSTÈME DOMOTIK STUDIO », zone de logo légèrement mise en valeur et trait supérieur cyan/bleu/violet.
- **Navigation** : sélection plus nette grâce à un filet cyan et un fond très subtil, sans éclairage néon envahissant.
- **Barre supérieure** : marque discrète près du fil d'Ariane et très fin trait tricolore.
- **Tableau de bord** : rappel coloré de 2 px en haut des indicateurs clés ; les cartes restent neutres et très lisibles.
- **Boutons principaux** : bleu vif conforme à la charte, avec texte contrasté.
- **Connexion** : fond bleu nuit et signature tricolore cohérents avec l'administration.

### Compatibilité et ergonomie

- Sidebar mobile compacte conservée ; la micro-signature est masquée sur les petits écrans.
- Thèmes clair et sombre conservés, contrastes et hiérarchie inchangés.
- Pas de changement des sections, des formulaires, des données, des URL courtes ou du front-end public.
- **Aucune migration de base de données.** Conserver les volumes existants lors du déploiement.

### Vérification après mise à jour

La version installée apparaît en bas du menu d'administration. Si ce menu affiche encore une version précédente, le VPS ou la fenêtre du navigateur n'a pas encore chargé la nouvelle image. Une actualisation forcée (Ctrl+F5) peut aider si les styles restent en cache.

### Tests

Les tests navigateur vérifient la signature de la barre latérale, la sélection du menu, le fil d'Ariane et les indicateurs, en plus de la suite existante (statistiques, campagnes, éditeur, mobile et Docker).

### Publication

Image Docker : `ghcr.io/mick7784/links:V1.309` — AMD64 et ARM64. La publication ne met pas à jour le VPS automatiquement ; conserver les volumes de données et les réglages existants.

## V1.308

### 🎨 Identité visuelle DomotiK Studio

LinKs rejoint la nouvelle charte de l’écosystème DomotiK Studio, en conservant sa personnalité de produit indépendant et le monogramme K officiel.

### Page publique : mêmes composants, palette harmonisée
- **Bleu nuit** `#060E24`, **cyan** `#00E5FF`, **bleu vif** `#0066FF`, **violet** `#A855F7`, blanc doux `#EAF2FF`.
- Ajustement limité à la palette par défaut et aux nuances de fond, bordures, liens et icônes. Les tailles, cartes, animations, contenus et comportements du carrousel **ne changent pas**.
- Les thèmes personnels et les réglages de l’éditeur « Apparence » restent disponibles : aucune modification en base de données et aucun thème enregistré n’est écrasé.

### Footer LinKs by DomotiK Studio
- Ajout de la signature visuelle LinKs avec son K officiel et le libellé « by DomotiK Studio ».
- Conservation du logo de profil, du copyright personnalisable, de la citation aléatoire et du numéro de version dynamique.
- Mise en valeur discrète du pied de page, sans ajout de section ni surcharge sur mobile.

### Administration
- La barre latérale utilise le mot-symbole LinKs actualisé.
- Harmonisation de la palette claire/sombre avec l’écosystème DomotiK, mais **surfaces sobres, professionnelles et lisibles**, sans effet néon envahissant.
- Pas de modification de l’organisation, des formulaires, des outils ou des statistiques.

### 🔒 Compatibilité
- Aucun changement de schéma SQLite, sauvegardes, URL courtes, jetons de redirection ni comptages.
- Aucun changement des contenus publics ou des réglages des thèmes personnels.
- Mise à jour de l’image Docker en conservant exactement les volumes existants.

### ✅ Contrôles
- Tests de rendu desktop/mobile, contraste, présence du logo de footer et version dynamique.
- Tests de non-régression « Apparence » : comparaison de la géométrie du profil et des cartes, plutôt qu’identité stricte des anciennes couleurs.
- CI fonctionnelle et Docker requis avant publication.

### 🚀 Publication

Image Docker : `ghcr.io/mick7784/links:V1.308` — AMD64 et ARM64. Conserver les volumes et la configuration de l'installation existante ; la publication GitHub ne redémarre pas automatiquement le VPS.

## V1.307

### 🔗 Liens courts discrets

- Les nouveaux liens de partage utilisent un **code opaque de 9 caractères directement à la racine du domaine**, par exemple `https://links.domotik-studio.fr/X7mQ9p2Ka` (exemple fictif). Aucun `/go/`, `st_`, `tk_` ni `utm_source` n'apparaît dans l'URL copiée.
- Chaque source de publication possède sa propre URL courte et **stable** pour chaque campagne ou lien privé. La source est enregistrée côté serveur et ne dépend plus d'un paramètre susceptible d'être supprimé lors du partage.
- Changer l'URL de destination conserve le même code court. Recopier le lien d'une même source redonne exactement le même code.
- Le suivi des clics reste actif côté serveur (agrégé, sans identification des visiteurs). Le canal enregistré correspond à l'emplacement choisi au moment de copier, pas nécessairement au site sur lequel une tierce personne repartage ensuite l'URL.

### 🔒 Compatibilité préservée

- **Tous les anciens liens `/go/st_...` et `/go/tk_...`, y compris ceux avec `?utm_source=...`, restent fonctionnels** et conservent leurs compteurs existants.
- Les nouveaux codes sont des alias vers ces mêmes jetons historiques : pas de remise à zéro, de transfert de statistiques ni de double comptage.
- Nouvelle table SQLite **additive** `short_aliases` incluse dans l'export des sauvegardes ; les restaurations d'anciennes sauvegardes conservent les alias déjà publiés sur l'instance.
- Lorsqu'une source à zéro clic est supprimée définitivement, ses codes courts sont révoqués mais **réservés** : ils ne seront jamais réattribués.
- La page publique, les campagnes et les destinations existantes ne changent pas.

### ✅ Tests

- Tests d'URL opaque, sources Instagram/YouTube distinctes, comptabilisation, redirections GET/HEAD, filtrage des robots, changement de destination, archivage, suppression d'une source et compatibilité des sauvegardes.
- Tests navigateurs et construction Docker avec configuration Nginx de routage des codes courts.

**Avant de mettre à jour le VPS :** sauvegardez les volumes Docker/SQLite existants et conservez leur montage pour la nouvelle image.

### 🚀 Mise à jour

Image prévue : `ghcr.io/mick7784/links:V1.307` (Docker AMD64 et ARM64). La release n'effectue aucun redémarrage du VPS : conserver le volume existant pour retrouver toutes les anciennes URL et les statistiques.

## V1.306

### ✨ Liens suivis indépendants des campagnes

- Nouvelle zone **Liens suivis · privés** dans **Liens & campagnes** : créez des liens vers des produits ou des pages externes sans créer de promotion ni afficher de nouveau bloc sur la page publique.
- Chaque lien conserve un identifiant permanent par source de publication : changer le nom ou l'URL de destination ne modifie pas les URL de partage déjà publiées.
- Un lien archivé continue de rediriger et de compter les clics. La suspension de la redirection reste possible sans effacer les statistiques.

### 🔗 Sources de publication personnalisables

- Gestionnaire central permettant d'ajouter, renommer, archiver et restaurer des sources (Instagram Story, YouTube Post, newsletter, réseaux supplémentaires, etc.).
- La source se choisit au moment de copier le lien. Chaque combinaison lien + source possède une URL permanente.
- Source à **zéro clic historique** : suppression définitive, après confirmation de l'utilisateur, avec révocation des URL non utilisées.
- Source ayant reçu au moins un clic : archivage uniquement, avec maintien des anciens liens et des statistiques.
- Sources personnalisées également proposées lors de la copie des liens des campagnes, sans modifier les liens historiques.

### 📊 Statistiques plus lisibles

- Chaque lien suivi possède une fiche repliable affichant un graphique en anneau (donut) et la répartition des clics par source.
- Filtres 7, 14, 30 jours ou total historique. Les compteurs cumulés sont conservés indépendamment de la rétention des agrégats journaliers.
- Les ouvertures des nouveaux liens suivis sont incluses dans les statistiques de liens partagés du tableau de bord, sans fausser le CTR de la page publique.

### 🔒 Données et compatibilité

- Migration SQLite **additive** : nouvelles tables pour les liens suivis, sources et jetons. Aucun effacement ni modification des identifiants des campagnes et liens `/go/st_...` existants.
- Sauvegardes et restaurations étendues aux nouvelles tables. Les liens permanents préexistants sont protégés même lors d'une restauration d'ancienne sauvegarde.
- Les anciennes attributions incertaines ne sont pas réécrites. Les URL externes utilisent le canal choisi lors de leur publication, non une identification du visiteur.
- Préserver les volumes Docker et effectuer une sauvegarde avant la mise à jour de l'installation.

### ✅ Validation

- Tests des liens permanents, changement de destination, redirections, sources à zéro clic, archivage, statistiques, sauvegarde/restauration, interface desktop/mobile et image Docker.

### 🧭 Utilisation dans le back-office

- Ouvrez **Liens & campagnes → Créer un lien suivi** pour enregistrer un produit sans l'afficher publiquement.
- Sélectionnez la source de publication puis copiez l'URL permanente depuis la ligne correspondante.
- Cliquez sur le nom du lien pour déplier son camembert de statistiques et choisir la période de consultation.
- **Gérer les sources** permet de créer, renommer ou retirer des sources avec protection de leur historique.

## V1.305

### ✨ Version installée visible dans le back-office

- La barre latérale de l’administration affiche discrètement la version réelle de LinKs, sous « DomotiK Studio · Administration ».
- Le libellé provient du champ serveur `app_version` déjà utilisé dans les paramètres techniques : il se met à jour automatiquement à chaque nouvelle release et ne peut pas être faussé par la restauration d’une sauvegarde ancienne.
- La présentation respecte les thèmes clair et sombre et les règles existantes de la navigation mobile (pied de la barre latérale masqué sur petits écrans).

### 🔒 Compatibilité et données

- Aucun changement à la base SQLite, à la page publique, aux statistiques, aux campagnes, aux liens `/go/...`, aux destinations ou au volume de données Docker.
- Mise à jour sans migration : conserver le volume `/data` et toutes les autres configurations du conteneur.
- Les liens suivis indépendants des campagnes, les sources personnalisables et les camemberts dépliables restent prévus pour une prochaine version ; ils ne font pas partie de cette release.

### ✅ Vérifications

- Tests automatisés du back-office, y compris l’affichage de la version réelle sur ordinateur et la compatibilité mobile.
- Tests de non-régression de l’application, vérification de la page publique et construction Docker validés en CI.

## V1.304

### ✨ Statistiques et suivi des liens partagés

- Le tableau de bord distingue les **clics effectués sur la page LinKs** des **ouvertures directes de liens partagés**. Chaque campagne affiche désormais ses impressions, clics sur la page, ouvertures externes, clics totaux et CTR de la page sur la période sélectionnée.
- Les liens de campagne copiés depuis l'administration peuvent être attribués à Instagram Story, YouTube Post, Facebook ou TikTok. Le sélecteur ajoute un paramètre `utm_source` sans modifier le jeton de redirection existant.
- Les liens `/go/st_...` sans indication de provenance continuent de fonctionner : leurs nouvelles ouvertures sont comptées comme source non identifiée. Les événements historiques conservent leurs données et leur ancienne classification, clairement signalée comme incertaine.

### 🎨 Tableau de bord plus lisible

- Présentation renforcée des indicateurs : trafic de la page, liens partagés, copies de codes promo et performances des campagnes.
- Sur le graphique quotidien, les barres cyan (visites) et violettes (clics sur la page) apparaissent côte à côte pour éviter tout recouvrement.
- Les campagnes actives mettent en évidence les ouvertures de liens partagés, les clics totaux et le CTR de la page, sans confondre impressions et redirections.
- Mise en forme responsive, vérifiée sur ordinateur et sur mobile, sans modification du design public.

### 🔒 Données et compatibilité

- **Aucune réinitialisation ni réécriture des statistiques historiques**. Les 117 ouvertures précédemment suivies restent conservées dans les compteurs existants ; elles sont reliées à leurs campagnes lors de la lecture des rapports, sans double comptage.
- **Tous les jetons, liens de partage, URL de destination, campagnes et contenus existants sont conservés**. Les liens déjà publiés sur Instagram, YouTube ou ailleurs restent valides.
- Les sauvegardes et restaurations prennent en charge les nouvelles provenances tout en acceptant les anciens événements `instagram-story`.
- Le volume de données Docker existant doit être conservé au déploiement. Effectuer une sauvegarde avant mise à jour ; la release publie l'image sans redémarrer l'installation de production.
- Mise à jour recommandée : sauvegarder le volume actuel, puis remplacer uniquement l'image de l'application par `ghcr.io/mick7784/links:V1.304` et vérifier la page publique et le dashboard après redémarrage.

### ✅ Validation

- Tests Python, JavaScript et scénarios navigateur desktop/mobile validés dans la CI.
- Parcours vérifiés : copie de lien, redirection, conservation des jetons, filtres de sources, statistiques par campagne, restauration et fonctionnement du calendrier.
- Construction Docker et contrôles de santé passés.

## V1.303

### ✨ Paramètres repensés

- Une seule section principale est affichée à la fois : vue d’ensemble, Général, Intégrations, Statistiques, Accès & sécurité, Citations, Partage, Stockage et Sauvegarde & maintenance.
- Navigation latérale persistante sur desktop, sélecteur compact sur mobile. Identité, logo, avatar, description, copyright, URL, fuseau, collecte et règles de sources, configuration YouTube, accès, partage, sauvegarde/restauration et version restent disponibles.
- La vue d’ensemble présente l’identité, YouTube, les statistiques, l’espace occupé, la corbeille, les citations et la version installée. Les cartes ouvrent directement la section correspondante.
- Les listes de fichiers et de citations, ainsi que l’état détaillé de YouTube, sont demandés uniquement lorsque leur section est ouverte.
- Les citations conservent leur contenu, leur ordre, leur activation, leurs imports et leurs actions. Recherche, filtre actif/inactif, compteur et pages de vingt citations évitent une liste de plusieurs centaines de lignes.

### 🗂️ Stockage global des fichiers personnels

- Un inventaire commun couvre les uploads et les anciens fichiers personnels de `/data/assets` : liens, campagnes, profil, raccourcis, icônes, fonds de thèmes et imports. Les références de fichiers présentes dans des réglages supplémentaires sont également protégées.
- Le gestionnaire affiche le total, la répartition par catégorie, la place occupée par la corbeille, les miniatures, tailles, formats, dates et toutes les utilisations connues. Des filtres permettent de consulter une catégorie, les fichiers utilisés ou la corbeille.
- Les fichiers partagés comptent une seule fois dans le total. Toutes leurs catégories et références restent visibles. La dernière catégorie connue est conservée lorsqu’un fichier devient orphelin.
- Un remplacement ou un détachement rend l’ancien fichier éligible à la corbeille uniquement après la disparition de sa dernière référence. Une nouvelle utilisation annule la suppression. Les contenus inactifs, liens archivés et thèmes non actifs restent pris en compte.
- Les fichiers sans référence bénéficient de sept jours avant le nettoyage automatique. La commande Vider la corbeille demande confirmation et vérifie les références sous le verrou des données avant la suppression physique.
- Les assets livrés avec LinKs sont exclus. Les copies exactes d’assets système conservées par une ancienne migration sont aussi protégées ; les fichiers personnels qui remplacent un asset de même nom restent gérés.
- Les anciens fichiers découverts au premier démarrage bénéficient d’un délai complet de sept jours, quelle que soit leur date historique. Les liens symboliques ne sont pas supprimés par le gestionnaire.

### ⚡ Optimisations et refactor ciblé

- L’aperçu des liens et campagnes conserve son iframe et son document. Les saisies rapides sont regroupées avant une mise à jour du contenu, sans recharger ses feuilles de style à chaque frappe.
- Les images de la bibliothèque de contenus sont créées à son ouverture ; les miniatures sont chargées progressivement. La grille d’icônes des raccourcis s’ouvre à la demande et n’est plus reconstruite à chaque modification du libellé ou de la destination.
- L’éditeur de raccourcis présente d’abord l’icône actuelle, le libellé et la destination. La liste déroulante d’icônes redondante est masquée ; la bibliothèque assure le choix. Sur mobile, un bouton donne accès à l’aperçu.
- L’actualisation du snapshot public passe par une liste centrale de mutations pertinentes. Son contenu est comparé avant toute écriture atomique ; les opérations privées, les tests et les analyses ne le régénèrent pas. Le choix de citation du secours statique est stable, tandis que l’API publique conserve son choix aléatoire.
- Les écritures de fichiers des uploads, de la configuration initiale, des migrations historiques, des imports de thèmes et des restaurations utilisent le même utilitaire atomique.
- L’inventaire réutilise les métadonnées existantes et limite les accès disque. Le nettoyage évite de relire toutes les références pour chaque fichier : le verrou des données couvre la vérification et l’ensemble de la suppression.
- Les anciennes règles de présentation des Paramètres devenues inutiles sont retirées. Aucun changement de framework ni refonte générale du rendu public.

### 🔄 Compatibilité et migrations

- Migration additive : table interne `user_files`, avec date et dernière catégorie connue. La table et les échéances de corbeille V1.302 sont conservées. Aucun format de contenu ni format de sauvegarde n’est remplacé.
- Identifiants, liens, campagnes, statistiques, thèmes, uploads, sauvegardes, migrations historiques, Story et Creator Studio restent compatibles.
- Déploiement avec le volume existant : sauvegarder le volume, récupérer la version V1.303 puis redémarrer selon la procédure habituelle. Le démarrage effectue l’inventaire et la migration sans supprimer de fichier utilisateur nouvellement découvert.

### ✅ Validation et publication

- 79 tests Python, 10 tests JavaScript et 12 suites navigateur, avec parcours desktop/mobile réels.
- Régressions ciblées : références partagées, remplacement, anciens assets, protection système, réutilisation de corbeille, migration additive, snapshot sans réécriture, navigation des neuf sections, chargements à la demande, citations et aperçu persistant.
- Validation Docker et smoke tests avant publication ; images `linux/amd64` et `linux/arm64` publiées sous `ghcr.io/mick7784/links:V1.303` et `latest`, avec égalité des digests contrôlée par la publication.
- Le déploiement sur le serveur est réalisé par le propriétaire après publication, conformément au fonctionnement convenu.

## V1.302

### 🐛 Corrections

- Les uploads des liens, campagnes, profils, thèmes et raccourcis restent liés à leur éditeur. Les réponses tardives sont ignorées, l’état d’import est affiché et l’enregistrement est protégé pendant l’opération.
- Les anciennes dates des liens classiques sont à nouveau visibles, modifiables et supprimables, permettant leur réactivation.
- Les images sont réellement décodées et contrôlées : PNG, JPEG, WebP et GIF, fichiers corrompus ou tronqués rejetés, limites de taille et de dimensions. La même validation couvre uploads, configuration initiale, thèmes et restaurations.
- Les adresses d’images non supportées sont refusées sans élargir la CSP. Les pastilles des statistiques affichent leurs couleurs. HEX, sélecteur de couleur et opacité restent synchronisés.
- Une ancienne sauvegarde ne change plus la version du logiciel affichée. La modification manuelle de version a été retirée. L’ordre des sections est explicitement celui de l’administration.

### ✨ Nouveautés

- Paramètres > Stockage affiche l’espace utilisé, les fichiers personnels, leurs miniatures, leur taille et leurs utilisations, ainsi que la corbeille.
- Les fichiers inutilisés sont suivis dans une corbeille et supprimés automatiquement après sept jours. Une réutilisation annule leur suppression. Les actions Nettoyer et Vider la corbeille vérifient toutes les références avant suppression ; les assets système sont exclus.
- L’archivage des campagnes détache leur image tout en conservant noms, dates, URL, codes promo, statistiques et liens Story. Un fichier partagé reste protégé par ses autres utilisations.

### 🎨 Interface

- Les cartes « Offre du moment » gagnent environ 12 % de hauteur sur desktop et 6 % sur mobile. Le dégradé reste limité à la zone texte pour montrer davantage l’image, notamment carrée, sans déplacer le texte du bas de la carte.

### ⚙️ Technique

- Le healthcheck Docker vérifie le backend et SQLite ; `/nginx-healthz` conserve un contrôle séparé de Nginx.
- Validation d’images avec Pillow et ajout d’une table SQLite additive `upload_trash`. Le suivi automatique tourne au démarrage puis chaque heure, et après les modifications de contenus.
- Tests de régression sur les réponses tardives, images invalides, anciennes sauvegardes, références partagées, délais de corbeille, campagnes archivées et rendu desktop/mobile. Le smoke Docker provoque puis répare une indisponibilité SQLite pour vérifier le healthcheck réel.

### ⬆️ Mise à jour

- Les identifiants, contenus, statuts et statistiques existants sont conservés. Les campagnes déjà archivées libèrent leur image à la mise à jour ; les fichiers nouvellement identifiés comme inutilisés bénéficient du délai complet de sept jours.
- Les fichiers historiques valides restent utilisables. Une sauvegarde contenant une image réellement corrompue est refusée sans remplacer les données actuelles.
- Les sauvegardes restent au format 3 et ajoutent une métadonnée `software_version`, indépendante du numéro de format. Elles contiennent les images référencées, pas la corbeille ; sauvegardez le volume serveur si vous souhaitez conserver aussi les fichiers inutilisés.
- Comme convenu, la mise en production sur votre serveur se fait après votre pull de la release ou de l’image Docker publiée.

## V1.301

### ✨ Nouveautés

- Six fonds photo panoramiques : communauté, création, maison connectée, boutique, contact professionnel et lifestyle. Les filtres Tous, Photos, Dégradés et LinKs se combinent avec les catégories métier.
- Réseaux & raccourcis affiche désormais les vraies icônes. L’éditeur partage la bibliothèque d’icônes existante et permet de rechercher, importer, remplacer ou supprimer une icône personnelle.
- Aperçu public Desktop/Mobile avec le thème actif et réglages dédiés aux couleurs, bordures, dimensions, opacité, effets et survol des raccourcis.

### 🐛 Corrections

- Les raccourcis vers une ancre sont correctement rendus. Les anciennes icônes e-mail restent compatibles.
- Les sauvegardes conservent les icônes personnelles et restent compatibles avec les sauvegardes précédentes.

### Mise à jour

- Migration automatique additive : identifiants, liens, ordre, statuts et statistiques sont conservés. Les douze fonds déjà disponibles et le rendu LinKs Original restent inchangés.
- Les icônes personnelles acceptent PNG, JPEG, WebP ou GIF jusqu’à 1 Mo. Préférez une image carrée avec fond transparent.

## V1.3

### ✨ Nouveautés

- Bibliothèque de douze fonds panoramiques, dont les six images historiques inchangées ; catégories et sélection instantanée dans l’éditeur des liens.
- Bibliothèque d’icônes complétée : Home Assistant, téléphone, vidéo, podcast, blog, téléchargement, calendrier et localisation. Les pictogrammes historiques sont conservés.

### 🎨 Thèmes / Apparence

- Nouveau menu Apparence : Mes thèmes, Éditeur, Bibliothèque et Import / Export.
- LinKs Original permanent et restaurable, plus trois thèmes personnalisés : création, édition, renommage, duplication, activation et suppression.
- Éditeur de 91 variables visuelles : couleurs, typographie, profil, cartes, icônes, médias, effets, dimensions et éléments secondaires.
- Aperçu de la page publique avec les données réelles, modes Desktop/Mobile, états actif/édition et modifications non enregistrées.
- Color pickers, HEX avec opacité, nuanciers, couleurs récentes, variantes et avertissements de contraste.
- Format portable `.links-theme` v1 et CSS Expert : valeurs contrôlées, images personnelles embarquées, fonds système référencés par ID, aucun code arbitraire.

### 🐛 Corrections

- Fermeture explicite des connexions SQLite utilisées au démarrage et pour la sauvegarde de migration.
- Préservation des réponses HTTP lors des rejets anticipés sous Windows.
- Champs des paramètres protégés pendant leur chargement pour éviter qu’une réponse tardive écrase une saisie.

### ⚙️ Technique

- Thèmes persistants dans SQLite, migration additive avec LinKs Original actif ; contenu, campagnes, icônes, images et préférences du back-office conservés.
- Sauvegarde/restauration des thèmes et de leurs images personnelles dans le format applicatif v3.
- Publication explicite après tests et build : réservation persistante et idempotente, tags Git/Docker et Release GitHub portant la même version, notes structurées et CHANGELOG communs.
- Un commit, une PR ou une validation seule ne publie plus de version de production.

### ⬆️ Mise à jour

- Conserver le volume `/data`, la configuration et le fichier Compose. Aucun changement d’apparence n’est appliqué à une instance existante sans action de son administrateur.
- Les fichiers de thème utilisent le moteur version 1. Ils n’exécutent ni CSS arbitraire ni JavaScript.

Les entrées de production sont ajoutées après validation, à partir du même fichier que les notes GitHub Release.

## V1.203

### Améliorations

- Version persistante réservée sur `main`, selon l’état historique du dépôt.

## V1.201

### Interface

- Fond Amazon et aperçu public corrigés, formulaires lien/campagne séparés, images de profil remplaçables et thèmes du back-office conservés.
- Dashboard, statistiques des Stories et codes promo harmonisés.

## V1.2

### Interface

- Refonte du back-office et fiabilisation de la copie des codes promo.
