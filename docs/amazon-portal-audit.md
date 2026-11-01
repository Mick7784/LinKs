> État courant : voir « Implémentation locale du parcours manuel » en fin de document. Les sections précédentes retracent les audits antérieurs.

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

## Examen des archives transmises

Les trois archives ont été lues depuis le Bureau, sans copie dans Git et sans import financier. Chacune contient un CSV UTF-8 à virgules. Les trois vues concordent sur les totaux des clics, articles commandés, expédiés et revenus totaux ; aucune addition entre vues n’est permise. Les chiffres privés et Tracking IDs réels ne sont pas enregistrés dans cette documentation ni dans les fixtures.

Catégories et Produits liés contiennent Date au format MM-JJ-AAAA. Tracking IDs ne contient pas de date et répète certains libellés de colonnes : les répétitions sont distinguées par leur position. Le rattachement de ce fichier à un jour nécessite une confirmation explicite début=fin ; cette origine est historisée par date_basis=confirmed_single_day. Le nom de l’archive ne fournit aucune date statistique implicite.

Les valeurs manquantes « - » deviennent inconnues, jamais zéro. Les artefacts de représentation flottante de montants sont acceptés uniquement à moins de 0,00000001 centime d’un entier ; une vraie fraction de centime reste refusée. La colonne « revenus totaux » a été utilisée pour vérifier la normalisation des revenus affiliés, sans confusion avec le chiffre d’affaires des articles expédiés. Les quantités et valeurs de conversion ne démontrent pas un nombre de commandes distinctes.

Validation : lecture ZIP et normalisation des trois fichiers réels réussies sans stockage financier ; quatre nouveaux tests synthétiques ciblés réussis. Les archives réelles restent hors du dépôt. Les clics ne sont pas encore intégrés au moteur statistique. Le rapport Tendances quotidiennes reste à recevoir, et aucun accès authentifié au portail n’a été testé.

## Statistiques intégrées à partir des trois vues disponibles

L’utilisateur a vérifié les sept types de rapports disponibles dans son interface France : Tendances quotidiennes n’y figure pas. Ce fichier n’est donc ni requis ni attendu pour poursuivre.

Le type « Clics, articles et commissions » associe les colonnes des trois formats examinés : clics, articles commandés, articles expédiés et revenus totaux. Les chiffres de commandes distinctes ne sont pas déduits des articles. Un import peut alimenter les totaux (référence) ou être conservé comme vue complémentaire hors totaux. Une référence qui chevauche les mêmes indicateurs d’une autre référence est refusée, y compris entre les anciens types Commandes/Rémunérations et le nouveau type combiné. Réimport identique dédupliqué ; corrections d’une même vue, usage et période historisées.

Pour les trois archives examinées : Catégories peut servir de référence, Produits liés de complément et Tracking IDs de complément de répartition. La répartition est présentée séparément avec sa couverture ; elle ne s’ajoute jamais aux totaux. Les champs Other ou vides ne sont pas assimilés à une plateforme de partage LinKs. Les compléments restent dans les sauvegardes, sans contribuer au cumul financier global.

L’évolution quotidienne (tableau) s’appuie exclusivement sur les dates des lignes des rapports de référence. Les dates issues de la confirmation manuelle d’une journée, dont Tracking IDs, sont exclues de cette évolution. Les jours absents et indicateurs inconnus ne deviennent pas des zéros. Un seul jour disponible donne un seul point ; aucun historique n’est extrapolé.

Validation ciblée : quatre tests supplémentaires (trois vues sans cumul, corrections et sauvegarde/restauration, chevauchements entre types, date absente et ancien format sans clics), traitement des trois archives réelles en SQLite en mémoire, et un parcours navigateur/API synthétique. Les chiffres des trois fichiers réels concordent sans triplement après leurs imports respectifs. Aucun fichier privé ni Tracking ID réel n’est ajouté à Git. Aucun accès automatisé Amazon ni déploiement n’est activé.

## Audit ciblé de récupération automatique — 1 novembre 2026

### Observé et testé

L’URL https://partenaires.amazon.fr/home/reports redirige vers https://www.amazon.fr/ap/signin. Un diagnostic Playwright Chromium classique, dans un contexte neuf, sans identifiants ni cookies, a atteint une page HTTP 200 contenant un formulaire de connexion. Résultat : login_required, connected=false, collection_enabled=false. Aucun identifiant, code TOTP, cookie ou demande de génération de rapport n’a été envoyé. Cette observation ne prouve pas l’acceptation du navigateur hébergé sur le VPS.

Le module amazon-portal.mjs réutilise le choix de moteur, le viewport et la classification des erreurs réseau de l’infrastructure existante. Il ouvre un contexte séparé de Domadoo, supprime les variables de secrets du processus navigateur, interdit les méthodes autres que GET/HEAD et les navigations hors des routes publiques vérifiées. Il ne sauvegarde ni capture, ni contenu de page, ni URL complète de connexion. Il n’est relié ni à une route de synchronisation ni au scheduler.

Diagnostic préparé : login_required, otp_required, intervention_required (CAPTCHA reconnu), access_denied (HTTP 401/403), rate_limited (429), navigation_blocked, network_error, unverified. Les marqueurs reconnus sont couverts par des fixtures ; une nouvelle présentation de contrôle Amazon reste non reconnue et ne peut jamais devenir une réussite. Aucune classification technique ne prétend constater une interdiction contractuelle.

### Autorisation et accès

Les politiques France, consultées en français le 1 novembre 2026, excluent les robots et outils d’extraction du périmètre de la licence du Contenu du Programme : https://partenaires.amazon.fr/help/operating/policies?language=fr_FR . La portée exacte sur les rapports privés du titulaire n’est pas confirmée ici. La clé MFA validée n’établit pas l’autorisation de collecte automatique. L’état contractuel reste « non établi », distinct d’un refus HTTP ou d’un CAPTCHA. Une interdiction explicitement applicable devra maintenir le connecteur désactivé, sans nouvelle tentative.

La FAQ https://partenaires.amazon.fr/help/topic/reports/faq décrit une sélection des données/périodes et une commande de téléchargement. Les trois ZIP réels prouvent l’existence de leurs exports ; ils ne révèlent pas le mécanisme authentifié de génération. La liste effective du compte (sept types, sans Tendances quotidiennes) prévaut sur les exemples génériques de l’aide. Creators API reste une voie officielle distincte, dont ListReports/GetReport et les droits financiers France doivent être vérifiés avec des identifiants API dédiés, non avec le mot de passe du portail.

### Parcours encore à observer sur le compte

Après établissement de l’accès autorisé : connexion normale par formulaire, MFA demandé explicitement, vérification du magasin France et de l’association à un unique compte LinKs, sélection de la période et des types réellement disponibles, demande de génération, attente bornée du résultat, téléchargement terminé. Les sélecteurs, l’état « en génération », la présence éventuelle d’une file de rapports, les délais et les hôtes de téléchargement n’ont pas été observés. Aucun endpoint interne, URL signée ou sélecteur de téléchargement n’est inventé à partir des noms de fichiers.

Le renouvellement de session réutilise ensureAmazonSession : vérification réelle avant réutilisation ; enregistrement chiffré de l’état renouvelé ; une reconnexion normale seulement si la session est expirée ; suspension sur tout autre état. Le correctif de cette étape persiste les cookies tournants après une vérification réussie. Un échec de capture garde l’état précédent et suspend le parcours, sans fuite de l’erreur brute. Restent à valider sur le compte : compatibilité du moteur, cookies/localStorage requis, durée de vie effective, association du magasin et apparition des contrôles supplémentaires. Une session ne sera jamais présumée valide d’après sa seule date locale.

### Raccordement prévu au moteur validé

Le futur adaptateur recevra une configuration de compte, période, vues et mappings validée. Il devra produire les octets ZIP/CSV avec le magasin et la période confirmés par le portail, sans inclure d’URL signée ni de cookies dans sa réponse. Chaque téléchargement sera borné, achevé et validé avant import. Les ZIP passent par inspect_archive, les membres choisis par normalize puis ingest ; aucune nouvelle formule financière. Les trois vues gardent leur rôle référence/complémentaire. La période n’est jamais déduite du nom du fichier. Toutes les écritures d’un lot et son statut de réussite seront regroupés dans une transaction ; aucun last_success ni relevé partiel sur échec de génération/téléchargement. Les contrôles existants de doublons/chevauchements et l’absence de calcul de pertes restent inchangés.

### Vérifications limitées à cette étape

Deux nouveaux tests ciblés réussis : rotation de session sans reconnexion, maintien de l’état précédent sur erreur, et six états diagnostiques sur pages synthétiques dans Chromium. Un diagnostic public réel a observé login_required/HTTP 200. Aucun test authentifié, aucune demande de rapport, aucune collecte quotidienne activée. Le moteur ZIP/CSV et les calculs statistiques n’ont pas été modifiés.


## Implémentation locale du parcours manuel — 1 novembre 2026

Cette étape remplace le diagnostic passif par `amazon/collect` dans le worker navigateur, lancé en tâche de fond par `amazon/sync`. Aucun identifiant réel n’est disponible dans cet environnement. Aucune réussite de connexion/collecte réelle n’est revendiquée. Les modalités contractuelles spécifiques au téléchargement automatisé privé restent non confirmées ; l’activation TOTP n’en constitue pas une autorisation. Le développement avance à la demande explicite de l’utilisateur, sans collecte planifiée.

### Fonctionnement développé

- Navigateur Playwright existant (Firefox/Chromium), identifiants exclusivement serveur, clé TOTP active via le mécanisme existant (conflit de sources bloquant), une seule tentative par étape email/mot de passe/OTP. Formulaires POST et destinations contrôlés avant saisie ; CAPTCHA, refus et étapes supplémentaires arrêtent le parcours. Aucun journal, capture d’écran ou réponse API ne contient les secrets.
- Session chiffrée existante réutilisée, associée au compte LinKs et au moteur navigateur ; rotation enregistrée après vérification puis après téléchargement. Session expirée : connexion normale, sans boucle de tentatives. Bouton pour oublier la session globale Amazon sans toucher au MFA. Aucun cookie exporté au navigateur utilisateur.
- Adaptateur d’export strict pour une journée, tous les Tracking IDs, trois vues : Catégories, Produits liés, Tracking ID. Attente d’un événement de téléchargement jusqu’à 120 secondes par export, arrêt global au bout de huit minutes. CSV/ZIP limité à 1 Mo par fichier, traité en mémoire par le moteur existant. Aucun endpoint privé reconstitué ni récupération d’un ancien travail d’export.
- Batch atomique : validation des trois fichiers et du Tracking ID attendu, catégories comme référence, deux autres vues complémentaires. Réimports idempotents, corrections historisées, refus des chevauchements incompatibles avec les imports précédents. Les dates manquantes du rapport Tracking ID ne créent pas une courbe quotidienne. Aucune perte de transaction déduite.
- Interface : journée, Tracking ID témoin, synchronisation manuelle, dernière collecte réussie distincte du dernier import CSV, erreur et nouvelle tentative. La session n’est pas présentée comme actuellement connectée sur la seule foi d’un ancien succès. Horaire configurable déjà conservé, ordonnanceur Amazon toujours désactivé. Aucun changement SQLite de schéma, ni calcul Domadoo.

### Limites à valider sur le compte réel

Les contrôles accessibles du dialogue d’export n’ont **pas été observés sur le compte** : noms des boutons, champs de dates HTML `date`, liste de type de rapport et sélection de tous les Tracking IDs sont un contrat d’adaptateur testé sur fixtures, pas une description prétendument vérifiée du portail. Si Amazon propose un calendrier différent, un travail asynchrone dans une liste distincte, un téléchargement signé sur un autre hôte ou d’autres noms de contrôles, l’adaptateur s’arrête ; il faudra l’adapter à des observations réelles avant de déclarer la collecte opérationnelle. Les quatre autres types d’exports ne sont pas interprétés automatiquement. Les rapports vides sont refusés plutôt qu’assimilés à une journée à zéro. Un Tracking ID témoin absent d’une journée impose l’import manuel.

La résolution d’un contrôle sur le navigateur personnel peut ne pas débloquer le navigateur serveur : aucun transfert automatique de cookies ni interface de prise en main Amazon n’est implémenté. Il faut alors poursuivre par l’import CSV. La validation réelle doit établir : connexion et OTP, reprise après redémarrage, expiration de session, génération et téléchargement de chaque vue sur une journée connue, égalité avec les exports manuels, réimport sans doublon. Seulement ensuite envisager l’activation quotidienne (non proposée dans cette étape).

### Vérifications ciblées

- `amazon_collection_test.py` : trois tests (idempotence et vues non additives ; période/tag/format/collecte partielle refusés ; rollback après échec tardif).
- `amazon-collector.test.mjs` : trois tests Playwright avec formulaires et téléchargements interceptés (email/mot de passe/OTP ; arrêt CAPTCHA ; dates, périmètre et trois téléchargements).
- `amazon-collection-browser-test.cjs` : parcours interface + serveur/base temporaires, worker substitué par un refus explicite, sélection conservée et bouton réactivé, aucune fausse réussite.
- Aucun test ne constitue une validation Amazon réelle. Pas de CI complète, publication ni déploiement.
