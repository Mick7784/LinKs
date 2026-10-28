# Gestion visuelle des campagnes — étape 3

Cette étape adapte les composants existants de la PR #50 aux moteurs de [sélection](CAMPAIGN-SELECTION.md) et de [cycle de vie](CAMPAIGN-LIFECYCLE.md). Elle ne refond pas le back-office et n’intègre aucune règle d’affiliation.

## Formulaire

Le bouton **Créer une campagne** ouvre directement le formulaire de campagne. Le choix du type de contenu et le nom interne sont masqués. Le titre public est obligatoire ; le nom interne est généré à la création à partir de ce titre. À l’édition, le nom interne enregistré reste inchangé, y compris lorsqu’il était identique au titre, afin de préserver les repères historiques. Les campagnes `featured` conservent leur type ; les valeurs historiques de priorité, badge, icône et texte d’action restent stockées.

La description, la destination, le code promo, le visuel, l’activation et le brouillon restent disponibles. La case **Campagne permanente** désactive les dates. En la décochant, les dates et heures deviennent éditables ; les nouvelles ponctuelles requièrent un début et une fin. Les anciens intervalles partiels sont préservés lorsqu’on ne les modifie pas. Les dates utilisent le fuseau de l’instance et le modèle de journée entière existant ; les heures acceptent la minute.

Les trois entrées du sélecteur d’image sont **Bibliothèque**, **Importer** et **URL**. Le choix « Aucune image » disparaît. Une campagne sans image spécifique hérite automatiquement du visuel par défaut ; une action secondaire permet de revenir à ce visuel. Une URL distante doit être en HTTPS, sans identifiants intégrés. Aucun téléchargement distant n’est effectué par le serveur. La politique CSP autorise le chargement de ces images HTTPS par le navigateur ; les autres directives restent inchangées. Les liens classiques gardent leur politique d’images locales. Une image distante historique déjà enregistrée reste conservée lors d’une modification de sa campagne.

## Apparence → Visuel par défaut

Le nouvel onglet **Visuel par défaut** propose un import PNG/JPEG/WebP de 4 Mo maximum, un aperçu, l’enregistrement, le remplacement et la réinitialisation. Il utilise les protections d’import existantes : sauvegarde désactivée pendant l’import, annulation des réponses tardives en quittant l’onglet, validation des pixels côté serveur.

L’ordre de rendu est :

1. Image spécifique de la campagne.
2. Visuel personnalisé commun.
3. Secours intégré `/assets/link-shopping.webp`, déjà présent dans LinKs.

Aucun nouveau logo ou visuel de marque n’est créé. Le visuel définitif pourra être importé plus tard.

Le réglage est enregistré sous `appearance.campaign_image` ; le fichier utilise le stockage existant `/data/uploads`. `GET /api/appearance/campaign-image` retourne `image`, `fallback` et `resolved_image`. `POST` sur cette même route, sous l’authentification d’administration, enregistre `{ "image": "/uploads/…" }` ou réinitialise avec une chaîne vide. Les fichiers manquants, faux formats, GIF et références distantes sont refusés pour ce réglage.

La configuration publique conserve `links[].image` tel qu’enregistré, et ajoute `campaign_default_image` ainsi que `effective_image` sur les campagnes. Le rafraîchissement public existant détecte les changements de rendu : les campagnes concernées sont actualisées sans réécriture de leurs fiches, dates, statistiques, jetons ou URL. Les images de secours sont aussi utilisées dans les aperçus du back-office.

Les sauvegardes incluent le fichier par défaut et remappent sa référence à la restauration. Une ancienne sauvegarde sans ce réglage conserve le visuel commun actuel. Le stockage reconnaît son propriétaire : une image encore utilisée reste protégée ; un fichier remplacé ou réinitialisé suit le délai de grâce normal s’il n’a plus de propriétaire.

## Planning, ordre et états

La liste des campagnes utilise l’ordre fourni par le serveur et distingue les groupes **Ponctuelles · prioritaires** et **Permanentes**. Les poignées permettent le glisser-déposer à la souris ou au tactile, avec défilement près des bords. Les flèches restent disponibles pour une utilisation sans glisser-déposer. Les mouvements restent dans le même groupe de durée ; la priorité absolue des ponctuelles reste appliquée par le moteur serveur. L’ordre est persisté via `/api/content/reorder`.

Les listes, le calendrier et le tableau de bord affichent les états du serveur : **Programmée**, **Affichée**, **En attente**, **Terminée**, **Archivée**, ainsi que Brouillon et Désactivée. L’éligibilité et les compteurs ne sont pas déduits des dates dans le navigateur.

Le panneau **Aperçu de la sélection** accepte une date et une heure dans le fuseau de l’instance. Il interroge `/api/promotions/selection?at=…` puis affiche les groupes et les compteurs retournés. Les titres viennent également du serveur. Cet aperçu n’exécute aucun nettoyage et ne modifie aucune campagne. Les résultats périmés d’une requête précédente sont ignorés. Les chevauchements supérieurs à trois sont signalés dans le formulaire et dans l’aperçu, sans empêcher l’enregistrement.

## Validation

`scripts/campaign_visual_test.py` couvre les priorités de visuel, la persistance, la réinitialisation, l’absence de mutation des campagnes et des compteurs, les sauvegardes récentes et anciennes, le stockage, les formats et les références invalides, les titres seuls, les noms/types historiques et les images HTTPS.

`scripts/campaign-management-browser-test.cjs` parcourt le formulaire réel, les dates/heures, `featured`, les noms privés, les URL de partage stables, le planning serveur, l’import/remplacement/réinitialisation, une image HTTPS et la persistance de l’ordre après rechargement. Il exerce un glisser-déposer souris et un geste tactile via les événements de l’appareil. Les tests navigateur existants sont adaptés aux champs désormais visibles.

Des captures peuvent être produites en définissant `CAMPAIGNS_SCREENSHOTS` : formulaire ordinateur/mobile, planning ordinateur, réglage du visuel sur mobile. Elles utilisent exclusivement une installation et des données temporaires.

La version de production reste V1.324. Aucun changement de PulSe, aucune fusion, release, publication d’image ou intervention VPS.
