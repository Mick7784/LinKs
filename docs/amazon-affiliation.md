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

## Import ZIP manuel — refonte du 3 novembre 2026

Dans Affiliation → Amazon, **Importer un ZIP Amazon** ouvre une zone de dépôt.
La sélection d'une archive lance `POST /api/affiliation/amazon/import-zip` : analyse
de tous les CSV/TXT, détection des colonnes connues, choix des références par
indicateur, contrôle des chevauchements et enregistrement atomique. Le bilan reste
visible et les statistiques sont actualisées sans rechargement manuel.

- Limites : 16 Mo compressés, 64 Mo décompressés, 64 entrées, 8 Mo et 10 000 lignes
  par fichier. Lecture en mémoire sans extraction ; chemins dangereux, liens
  symboliques, chiffrement, archives imbriquées, noms dupliqués et compression
  excessive sont refusés. Seuls CSV/TXT UTF-8 et ZIP stored/deflate sont acceptés.
- Vues Category, Linked-Product, Tracking-Id, Daily Trends et colonnes connues de
  commandes/rémunérations/paiements. Séparateurs virgule, point-virgule et tabulation,
  dates ISO, MM-JJ-AAAA ou JJ/MM/AAAA, nombres décimaux à virgule/point, symboles EUR,
  bruit flottant inférieur à la tolérance existante, tirets et en-têtes répétés.
  Les lignes de total explicitement étiquetées sont exclues avec un avertissement.
- La période vient des métadonnées, d'une plage de dates du nom de fichier, ou des
  dates réellement présentes. Le périmètre et la devise doivent être explicites.
  Si une donnée indispensable manque, aucun import n'a lieu : le formulaire demande
  uniquement cette donnée. Les dates du filtre et la date d'import ne servent jamais
  de valeurs implicites. Le mapping technique reste dans le mode manuel secondaire.
- Pour chaque indicateur d'un même périmètre et d'une même période, la priorité est
  Category, Daily Trends, Tracking-Id, Linked-Product puis format générique. Une vue
  datée dont le total est identique peut fournir la référence quotidienne. Les
  divergences sont signalées ; les autres vues ne s'ajoutent pas aux montants.
- SHA-256 de chaque archive conservé dans les observations existantes. Un réimport
  historique est sans effet, même après correction. Une correction remplace les
  références du même périmètre/période, y compris un ancien import manuel, à condition
  de préserver tous ses indicateurs. L'historique et les sauvegardes sont conservés.
  Les chevauchements incompatibles et fichiers invalides annulent tout le lot.
- Une période sans ventilation quotidienne est stockée avec des dates de lignes
  nulles, contribue seulement aux sélections qui la contiennent entièrement et
  figure dans la part non ventilée de la vue générale. Les statuts restent distincts :
  Domadoo approuvé observé, Amazon déclaré ; aucun solde retirable n'est calculé.
- Aucune migration de table, modification des transactions Domadoo, perte Amazon
  inférée ou activation de connexion automatisée au portail. Les anciennes sauvegardes
  sont acceptées ; les nouvelles métadonnées exigent cette version ou une ultérieure.

Limites connues : les variantes de colonnes non reconnues ou ambiguës nécessitent
le diagnostic manuel. Un rapport sans preuve de période/périmètre/devise demande
une précision. Les archives contenant un fichier autre que CSV/TXT sont refusées.
Aucun export privé réel n'est utilisé pour les tests ; la reconnaissance est validée
sur des fixtures synthétiques représentatives, pas sur tous les formats Amazon.

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

La synchronisation automatique Amazon **n’est pas implémentée/activée** dans cette étape : programmer des téléchargements sans connaître leur contenu, couverture et droits donnerait des statistiques trompeuses. Le diagnostic manuel et l’import confirmé sont utilisables dès configuration de l’accès correspondant. Le CSV local ne nécessite aucun secret API.

La récupération autorisée actuellement vérifiée depuis le portail est le téléchargement manuel des rapports. Aucune automatisation du portail n’est ajoutée sans confirmation des modalités d’accès autorisées. Les connecteurs Reolink, Sanyipace, Awin et Impact restent disponibles comme futurs comptes, sans changement de comportement.

## Préparation locale de l'authentification au portail

Docker Compose accepte facultativement `AMAZON_LOGIN`, `AMAZON_PASSWORD` et `AMAZON_MFA_SECRET` depuis un fichier `.env` local ou l'environnement privé du serveur. Copier `.env.example` vers `.env` puis renseigner les valeurs uniquement sur le serveur. `.env` et ses variantes sont ignorés par Git. Ces trois variables sont transmises uniquement au worker d'affiliation ; le processus web et les navigateurs lancés par le worker ne les reçoivent pas.

Le module serveur `amazon-auth.mjs` prépare un code TOTP à six chiffres conforme à RFC 6238 depuis la clé Base32, réutilise le chiffrement AES-256-GCM des sessions d'affiliation dans un fichier Amazon distinct et prévoit la réutilisation d'une session puis une seule reconnexion normale si elle a expiré. Une vérification supplémentaire ou une connexion non confirmée arrête ce flux. Aucune interface, API ou journal ne renvoie le mot de passe ou la clé MFA enregistrée ; seul le code temporaire demandé par l'assistant est transmis à la page privée. L'absence de cette configuration n'empêche pas le démarrage et ne change ni l'import CSV ni Domadoo.

Dans Affiliation → Amazon → Connexion, l'assistant accepte une clé TOTP Base32 de 52 caractères. Il l'enregistre d'abord comme clé **en attente**, chiffrée côté serveur, et renvoie uniquement le code à six chiffres avec le temps restant dans sa fenêtre de 30 secondes. L'utilisateur saisit ce code **sur Amazon** puis confirme l'activation dans LinKs ; aucune requête de validation n'est envoyée à Amazon. La clé n'est jamais renvoyée ni réaffichée. Une clé active peut être remplacée (l'ancienne reste active jusqu'à confirmation) ou supprimée. Si `AMAZON_MFA_SECRET` est encore défini dans l'environnement, sa suppression dans l'interface est refusée : il faut d'abord retirer cette variable du serveur. La variable d'environnement désigne la source active et verrouille la gestion dans LinKs. Des clés différentes bloquent l'authentification jusqu'au retrait de la variable.

**État réel :** aucun adaptateur de navigation du portail Amazon n'est activé. Les trois variables ne déclenchent donc aucune connexion ni synchronisation à elles seules. La [FAQ officielle des rapports français](https://partenaires.amazon.fr/help/topic/reports/faq) documente les téléchargements manuels CSV/TXT, XLSX et XML, sans procédure d'automatisation avec identifiant/mot de passe. Les [politiques du programme français](https://partenaires.amazon.fr/help/operating/policies) encadrent les robots et logiciels automatisés, mais ne fournissent pas ici d'autorisation explicite pour la collecte automatisée des rapports privés. La possibilité technique d'une connexion normale avec MFA et les éventuels contrôles supplémentaires doivent être vérifiés sur un compte réel. La voie API Creators reste distincte et prioritaire ; si elle ne donne pas accès aux revenus, demander à Amazon les modalités autorisées de collecte du portail avant d'activer cet adaptateur. Aucun contrôle supplémentaire ne sera contourné.

## Vérifications ciblées

Tests locaux du parseur, des réimports/corrections, chevauchements, fenêtres partielles, métriques inconnues, sauvegardes/restauration, isolation Domadoo et contrat API simulé. Ils ne prouvent pas l’accès réel à l’API France. Aucun workflow CI, release ou déploiement engagé.

La liste des commandes ciblées est maintenue dans `docs/affiliation-overview.md`. Les tests ZIP couvrent les lots multi-vues, les corrections, les échecs atomiques, les périodes non ventilées et le contrôle 9,92 € + 51,87 € = 61,79 €. Aucun appel Amazon authentifié pendant ces vérifications.

La confirmation porte sur une version aléatoire de la clé présentée. Le worker sérialise les opérations MFA : une version remplacée par un autre onglet est refusée avant toute activation.
