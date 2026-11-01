# Audit du connecteur portail Amazon — chantier local

Base : tag V1.4.7, commit 6c50cdacb1fda6194671ff6e2b72441b01801162.
Branche : feat/amazon-portal-connector.

## Accès et éléments manquants

Précision utilisateur : Amazon a validé la clé MFA TOTP de 52 caractères, pas l’automatisation du portail. La configuration MFA est terminée ; aucune autorisation spécifique de collecte automatisée n’a été reçue. Aucune interdiction générale de lire les rapports privés n’est déduite des clauses visant les clics artificiels ou le contenu publicitaire. Les pages publiques ne suffisent cependant pas à confirmer le périmètre d’accès automatisé.

Sources consultées :
- https://partenaires.amazon.fr/help/operating/policies : règles de participation et licence, portée à distinguer des rapports privés.
- https://partenaires.amazon.fr/help/topic/reports/faq : téléchargement des rapports, sans parcours public documenté de connexion automatisée.
- https://partenaires.amazon.fr/help/node/topic/GK5TZZ4AWML2QSLA : Tracking IDs dans les rapports.
- https://partenaires.amazon.fr/help/node/topic/GMWAK55DQX8JEK7C : commandes en cours de journée et gains arrêtés à la veille.

Certaines lectures directes des pages françaises ont renvoyé leur variante anglaise ; les conditions générales liées depuis le pied de page ont renvoyé HTTP 503. Cela ne prouve pas un refus du compte ou du navigateur serveur. Aucun appel authentifié au compte Amazon n’a été effectué.

## Architecture existante auditée

- amazon-auth.mjs : identifiants côté serveur, sélection explicite d’une source MFA, refus des conflits, confirmation versionnée, TOTP et stockage AES-256-GCM. ensureAmazonSession attend encore un adaptateur concret verify/signIn/capture.
- affiliation-browser.mjs : Playwright Firefox/Chromium disponible, mais navigation, diagnostic, cookies et sessionStorage sont limités à Domadoo. Ne pas élargir ces règles pour intégrer Amazon ; utiliser un contexte Amazon distinct et ne transmettre ni secrets d’environnement au processus navigateur ni erreurs brutes aux API.
- affiliation-worker.mjs : un worker local authentifié, requêtes sérialisées, sessions chiffrées. Les identifiants Amazon et la clé MFA sont globaux au serveur : une association explicite au compte de reporting sera nécessaire pour ne pas importer le même compte dans plusieurs comptes LinKs.
- amazon_affiliation.py : moteur unique normalize/ingest/report, correspondance de colonnes explicite, versions de rapports et déduplication. Un fichier identique ne crée pas de doublon ; les corrections d’un périmètre identique remplacent sa contribution aux totaux en conservant l’historique. Les chevauchements partiels sont refusés.
- Les commandes, articles commandés, articles expédiés, commissions, paiements et Tracking IDs disposent déjà de champs. Les clics, conversions et autres métriques quotidiennes n’en disposent pas : ne pas les transformer en commissions ou commandes.
- Scheduler et start_sync : limités à Domadoo. configure autorise déjà l’enregistrement d’un horaire Amazon désactivé ; aucun changement SQLite nécessaire pour cette préparation.

## Contrat de collecte à valider sur le compte

1. Examiner les modalités Amazon autorisées et les domaines effectivement utilisés par la connexion normale.
2. Examiner le parcours de connexion sans enregistrer mot de passe, seed MFA, codes, cookies, captures de formulaires ou URLs de redirection dans les journaux. Un CAPTCHA ou une vérification supplémentaire suspend le parcours.
3. Identifier explicitement le magasin France et son compte LinKs ; vérifier que la session restaurée correspond à ce magasin.
4. Télécharger un rapport de gains, commandes et, si disponible, paiements ; relever colonnes, formats, dates, période, couverture, timezone, Tracking IDs et éventuels agrégats/totaux.
5. Réutiliser normalize/ingest avec une correspondance validée, une période fixe et une transaction SQLite pour tout le lot. Une fenêtre glissante chevauchant des imports existants doit être refusée ou faire l’objet d’une stratégie explicite, jamais additionnée.
6. Rapprocher les totaux d’une période connue, tester le réimport et une correction, puis autoriser la collecte quotidienne. Aucun calcul de pertes Amazon.

## État de cette étape

Développé : présentation honnête de l’accès non vérifié, bouton Synchroniser indisponible, distinction dernier import/dernière collecte, configuration d’un horaire souhaité via les paramètres existants en imposant enabled=false. Import CSV et assistant MFA conservés.

Vérifié : syntaxe JavaScript et cohérence du diff ; inspection du chemin serveur qui refuse enabled=true pour Amazon. Aucun test ne démontre un accès réel au portail.

Non développé ou non validé : adaptateur navigateur Amazon, téléchargement authentifié, correspondance des rapports du compte, synchronisation financière automatique. Ces éléments dépendent des modalités d’accès et du parcours réel à examiner. Aucune PR, CI, release ou publication de cette branche.

## Avancement : archives et vues de rapports

Les trois archives Category-01nov2026-114521.zip, Linked-Product-01nov2026-114521.zip et Tracking-Id-01nov2026-114521.zip sont annoncées par l’utilisateur comme couvrant le 31/10/2026. Elles ne sont pas présentes dans Documents/Codex ni dans les pièces jointes accessibles à cette étape. Les colonnes Date des vues Catégories et Produits liés sont signalées par l’utilisateur et restent à examiner ; la date du nom de fichier ne devient jamais la date des statistiques.

Développé : lecture ZIP côté serveur en mémoire (CSV/TXT UTF-8, 16 entrées, 1 Mo compressé et décompressé, refus des chemins dangereux, liens symboliques, fichiers chiffrés, doublons et archives imbriquées). L’interface permet de choisir un membre, d’inspecter ses colonnes et de passer par le moteur existant de préparation/confirmation/import. Aucune somme automatique des membres.

La vue est identifiée explicitement : Catégories, Produits liés, Tracking IDs ou Tendances quotidiennes. Une autre vue du même indicateur et périmètre ne peut plus remplacer silencieusement une vue déjà importée. Les chevauchements restent refusés par le moteur existant. Les vues complémentaires doivent être analysées séparément ; leur conservation simultanée hors totaux et la sélection d’une référence par indicateur restent à développer après examen des fichiers réels. Les anciens imports sans vue sont conservés. Les nouveaux exports de sauvegarde avec vue nécessitent cette version du moteur pour leur restauration.

Tendances quotidiennes est prévu comme vue explicite ; les dates sont celles des colonnes associées manuellement. Les clics peuvent être lus dans l’aperçu brut mais ne sont pas encore intégrés aux statistiques. Ne pas déduire des commandes distinctes à partir du nombre d’articles. Aucun calcul de pertes.

Accès étudiés : téléchargement manuel documenté par la FAQ française ; Creators API officielle avec diagnostic ListReports/GetReport existant, dont les droits de reporting financier France restent à vérifier sur le compte. La validation MFA ne démontre ni ces droits API ni l’autorisation de robotiser le portail. Aucun formulaire de connexion Amazon automatisé, téléchargement authentifié ou planification quotidienne activé.

Vérifications nouvelles uniquement : quatre tests synthétiques réussis (ZIP et limites, non-cumul entre vues, sauvegarde/restauration, dates et compatibilité des imports anciens) et syntaxe JavaScript. Aucune archive réelle ni compte Amazon testé.
