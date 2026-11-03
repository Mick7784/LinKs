# Amazon Partenaires France — première étape locale

État au 1er novembre 2026. Aucun compte réel connecté, aucune requête authentifiée Amazon effectuée. Aucun scraping, contournement de CAPTCHA, automatisation de connexion ou recours à Selling Partner API/Appstore Reporting API.

## Ce que les sources officielles confirment

La [documentation SDK Amazon](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/get-started/using-sdk) mentionne le reporting depuis la version 1.1.0. L’archive Python officielle liée par cette page a été lue, sans installer ni exécuter son code. Ses exemples `sample_list_reports.py` et `sample_get_report.py` utilisent les opérations suivantes :

Archive examinée : `https://affiliate-program.amazon.com/creatorsapi/docs/assets/sdk-archived/creatorsapi-python-sdk.zip` ; SHA-256 `37a87e0059454d8987f4dbd1b7eabf578c2d4005d4ca0f19571211bd85ed5923`.

| Opération | Résultat du SDK |
| --- | --- |
| POST `/reports/v1/listReports` | Liste des fichiers : filename, md5, size, lastModified, reportType facultatif |
| POST `/reports/v1/getReport` | URL de téléchargement pour filename et, si fourni, reportType |

Le modèle `ReportType` déclare CREATOR_CENTRAL et CREATOR_CONNECTIONS. Ces catégories ne prouvent ni l’accès aux rémunérations ordinaires Amazon Partenaires France, ni un format financier spécifique. Le SDK ne décrit pas les colonnes des fichiers. Aucune garantie vérifiée de transaction unique stable, de relevé exhaustif, de cadence de génération ou de rétention n’a été trouvée pour ces opérations. L’ASIN identifie un produit, le Tracking ID un périmètre d’attribution : aucun des deux n’identifie une vente.

L’[inscription officielle](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/onboarding/register-for-creators-api) demande un compte Partenaires accepté, son propriétaire principal et une application donnant Credential ID, Secret et Version. [La France est une locale EU](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/concepts/common-request-headers-and-parameters), avec `x-marketplace: www.amazon.fr`. Les seuils documentés pour l’accès au catalogue produit ne doivent pas être présentés comme une autorisation de reporting financier.

Le [centre de rapports France](https://partenaires.amazon.fr/welcome/topic/reports) décrit gains, commandes, primes, Tracking IDs et historique des paiements. La [FAQ France](https://partenaires.amazon.fr/help/topic/reports/faq) confirme les téléchargements CSV/TXT, XLSX et XML, avec dates de transaction dans les exports détaillés. Elle indique des commandes actualisées en cours de journée et des rémunérations arrêtées à la veille, ainsi que des sélections de moins de 90 jours. Cela décrit le portail, pas les garanties de la Creators API. Les paiements sont distincts des gains et des articles expédiés. Les schémas exacts de votre compte restent à vérifier.

## Import ZIP automatique

Dans Affiliation → Amazon, **Importer un ZIP Amazon** propose : choisir le fichier,
cliquer sur **Envoyer**, puis lire le bilan. Le parcours normal ne demande ni dates,
ni devise, ni périmètre, ni correspondance de colonnes.

- Lecture en mémoire des CSV/TXT UTF-8 ; limites : 16 Mo compressés, 64 Mo
  décompressés, 64 entrées, 8 Mo et 10 000 lignes par fichier. Les chemins dangereux,
  doublons de noms, liens symboliques, archives imbriquées et compressions excessives
  sont rejetés avant toute conservation.
- Reconnaissance par les colonnes et le contenu, indépendamment du nom de la vue.
  Séparateurs virgule, point-virgule, tabulation ; formats numériques FR/EN ;
  symboles EUR ; lignes de total étiquetées exclues.
- Dates issues des lignes ou d'une plage explicite dans les métadonnées ou le nom
  du fichier interne. Une date de téléchargement isolée ne prouve jamais une période.
  Le périmètre et la devise doivent être démontrés ; aucune valeur n'est inventée.
- Une référence par indicateur et couverture. Les vues complémentaires ne sont
  jamais additionnées aux totaux. Une correction conserve l'historique.
  Les fenêtres quotidiennes chevauchantes de même vue et périmètre remplacent les
  jours effectivement renseignés, en conservant les autres jours et indicateurs.
- Les totaux non datés ne sont ni proratisés ni répartis arbitrairement. Un
  chevauchement non résoluble, une information manquante ou un format inconnu donne
  un bilan **Archive conservée à vérifier** : ZIP original et motifs persistés,
  statistiques inchangées. Le fichier se récupère dans **Archives à vérifier**.
  Un réenvoi identique n'ajoute pas une deuxième archive en attente.
- Réimport d'une archive déjà acceptée sans effet, même après correction. Les
  rapports identiques réemballés ou renommés ne réactivent pas une ancienne version.
- Les sauvegardes comprennent les archives en attente ; leur plafond global reste
  applicable. La restauration contrôle leur empreinte et leur contenu. Les
  anciennes sauvegardes sont acceptées ; les nouvelles nécessitent ce correctif.
- Le mode manuel avancé reste séparé pour le diagnostic. Il ne fait pas partie du
  parcours normal. Les commissions déclarées Amazon et les paiements restent distincts.

La décision automatique est isolée dans `scripts/amazon_imports.py`. Le parseur et
la lecture des références restent partagés avec CSV et portail. Aucun volume réel
n'est reclassé au démarrage. Les variantes non reconnues sont conservées, pas devinées.

## Diagnostic API sécurisé, à connecter

Les variables sont propres à chaque compte LinKs (son ID est visible dans la réponse privée `/api/affiliation/overview`) :

```text
AMAZON_CREATORS_<ID_DU_COMPTE_LINKS_EN_MAJUSCULES>_CREDENTIAL_ID
AMAZON_CREATORS_<ID_DU_COMPTE_LINKS_EN_MAJUSCULES>_CREDENTIAL_SECRET
AMAZON_CREATORS_<ID_DU_COMPTE_LINKS_EN_MAJUSCULES>_VERSION
```

Configurer ces secrets exclusivement dans l’environnement privé du service serveur, jamais dans Git, le navigateur ou un export. Versions EU prises en charge : 2.2 (OAuth Cognito) et 3.2 (Login with Amazon), selon les endpoints et scopes du SDK officiel. Ce mode API ne demande aucun mot de passe du portail Amazon. Aucun secret ni jeton n’entre dans SQLite ou les sauvegardes ; le code ne journalise pas les réponses brutes et renvoie des erreurs génériques.

Dans le détail Amazon → Import et accès API, « Vérifier les rapports disponibles » appelle ListReports côté serveur. « Préparer l’import » appelle GetReport pour un fichier effectivement retourné par ListReports, puis lit le CSV côté serveur. L’URL signée n’est jamais transmise à l’interface. Le téléchargement est limité aux URL HTTPS S3 Amazon standard, sans redirection, et à 1 Mo. Les archives ZIP, autres formats ou destinations non reconnues sont refusés ; utiliser alors le CSV téléchargé manuellement depuis le portail. La lecture API prépare l’import mais ne valide pas automatiquement les chiffres.

## Ce qui reste bloqué par l’accès réel

1. Vérifier les droits de reporting de votre compte France via ListReports ; si refus, demander à Amazon si le programme et le compte sont éligibles.
2. Examiner un export de rémunérations, commandes et éventuellement paiements du compte : intitulés, unités, dates, encodage, granularité, Tracking IDs, corrections, couverture et identifiants. Aucun de ces détails n’est inventé à partir des modèles du SDK.
3. Valider un rapprochement sur une période connue, puis seulement définir une sélection de fichiers et un mapping stables pour les synchronisations financières manuelles/automatiques.

La synchronisation quotidienne Amazon reste désactivée. Le bouton de collecte manuelle expérimentale est raccordé au worker navigateur ; l’import local ZIP ne nécessite aucun secret API.

La recette du portail et des modalités d’accès sur un compte réel reste distincte des tests locaux. Les connecteurs financiers futurs ne sont pas activés par ce correctif.

## Préparation locale de l'authentification au portail

Docker Compose accepte facultativement `AMAZON_LOGIN`, `AMAZON_PASSWORD` et `AMAZON_MFA_SECRET` depuis un fichier `.env` local ou l'environnement privé du serveur. Copier `.env.example` vers `.env` puis renseigner les valeurs uniquement sur le serveur. `.env` et ses variantes sont ignorés par Git. Ces trois variables sont transmises uniquement au worker d'affiliation ; le processus web et les navigateurs lancés par le worker ne les reçoivent pas.

Le module serveur `amazon-auth.mjs` prépare un code TOTP à six chiffres conforme à RFC 6238 depuis la clé Base32, réutilise le chiffrement AES-256-GCM des sessions d'affiliation dans un fichier Amazon distinct et prévoit la réutilisation d'une session puis une seule reconnexion normale si elle a expiré. Une vérification supplémentaire ou une connexion non confirmée arrête ce flux. Aucune interface, API ou journal ne renvoie le mot de passe ou la clé MFA enregistrée ; seul le code temporaire demandé par l'assistant est transmis à la page privée. L'absence de cette configuration n'empêche pas le démarrage et ne change ni l'import CSV ni Domadoo.

Dans Affiliation → Amazon → Connexion, l'assistant accepte une clé TOTP Base32 de 52 caractères. Il l'enregistre d'abord comme clé **en attente**, chiffrée côté serveur, et renvoie uniquement le code à six chiffres avec le temps restant dans sa fenêtre de 30 secondes. L'utilisateur saisit ce code **sur Amazon** puis confirme l'activation dans LinKs ; aucune requête de validation n'est envoyée à Amazon. La clé n'est jamais renvoyée ni réaffichée. Une clé active peut être remplacée (l'ancienne reste active jusqu'à confirmation) ou supprimée. Si `AMAZON_MFA_SECRET` est encore défini dans l'environnement, sa suppression dans l'interface est refusée : il faut d'abord retirer cette variable du serveur. La variable d'environnement désigne la source active et verrouille la gestion dans LinKs. Des clés différentes bloquent l'authentification jusqu'au retrait de la variable.

**État courant :** un adaptateur de collecte manuelle expérimentale est présent. Il sélectionne et vérifie « tous les Tracking IDs » avant de générer les trois vues ; sans contrôle non ambigu, la collecte s'arrête et conserve le dernier relevé. Le serveur exige cette preuve de périmètre. Les identifiants et la clé MFA sont globaux au serveur, la session est liée au compte LinKs. Aucun CAPTCHA ou contrôle supplémentaire n'est contourné. La collecte quotidienne demeure désactivée ; les droits et le DOM du compte réel restent à recetter..
