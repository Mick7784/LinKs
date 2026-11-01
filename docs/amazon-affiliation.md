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

## Disponible dans LinKs

Dans Affiliation → Gérer les partenaires → Ajouter un partenaire, choisir Amazon Partenaires. Le compte propose l’import CSV et une vue détaillée Amazon, sans activer un faux connecteur de collecte.

- CSV UTF-8 jusqu’à 1 Mo / 10 000 lignes. Choix de la ligne d’en-tête, détection virgule/point-virgule/tabulation, correspondance explicite des colonnes. Formats de date ISO ou JJ/MM/AAAA ; décimales virgule ou point, montants en EUR.
- Types séparés : Commandes (commandes distinctes si fournies, articles commandés), Rémunérations (articles expédiés, commissions), Paiements. Une quantité d’articles ne devient jamais un nombre de commandes. Un champ absent reste inconnu.
- ASIN, produit, Tracking ID, statut et identifiant éventuellement fournis restent disponibles sans déduire une identité de transaction fiable ou un statut approuvé. Les Tracking IDs ne sont pas reliés automatiquement aux sources YouTube/Instagram/LinKs.
- Vérification des lignes et montants avant confirmation. Les totaux/sous-totaux doivent être exclus du fichier : ils ne sont pas devinés. Le format n’est pas annoncé comme compatible automatiquement avec tout export Amazon ; la correspondance doit être validée sur votre fichier réel.
- Période et périmètre explicites (`all` ou Tracking ID exact). Les chevauchements d’un même type/périmètre sont refusés ; les corrections du même périmètre créent une version supplémentaire. Seule la dernière version contribue aux totaux ; un réimport identique ne crée pas de doublon.
- Statistiques Amazon filtrées par les dates du rapport, intégrées au total global des commissions avec un indicateur Amazon distinct. Le graphique historique approuvé/non approuvé reste explicitement Domadoo. Les commandes, paiements et commissions sont affichés séparément dans le détail Amazon.
- Conservation dans les observations financières existantes (`aff_snapshots`) ; les versions précédentes restent dans les sauvegardes. Pas de modification de schéma ni des lignes financières Domadoo. Les anciens exports Affiliation restent acceptés. Les sauvegardes contenant des rapports Amazon doivent être restaurées avec cette version ou une version ultérieure.
- Aucune perte Amazon calculée : ni fenêtre glissante, ni correction d’agrégat, ni produit absent ne devient une transaction perdue. Le moteur Domadoo n’accepte pas les rapports Amazon.

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

Le module serveur `amazon-auth.mjs` prépare un code TOTP à six chiffres conforme à RFC 6238 depuis la clé Base32, réutilise le chiffrement AES-256-GCM des sessions d'affiliation dans un fichier Amazon distinct et prévoit la réutilisation d'une session puis une seule reconnexion normale si elle a expiré. Une vérification supplémentaire ou une connexion non confirmée arrête ce flux. Aucune interface, API ou journal n'expose les identifiants ou codes. L'absence de cette configuration n'empêche pas le démarrage et ne change ni l'import CSV ni Domadoo.

**État réel :** aucun adaptateur de navigation du portail Amazon n'est activé. Les trois variables ne déclenchent donc aucune connexion ni synchronisation à elles seules. La [FAQ officielle des rapports français](https://partenaires.amazon.fr/help/topic/reports/faq) documente les téléchargements manuels CSV/TXT, XLSX et XML, sans procédure d'automatisation avec identifiant/mot de passe. Les [politiques du programme français](https://partenaires.amazon.fr/help/operating/policies) encadrent les robots et logiciels automatisés, mais ne fournissent pas ici d'autorisation explicite pour la collecte automatisée des rapports privés. La possibilité technique d'une connexion normale avec MFA et les éventuels contrôles supplémentaires doivent être vérifiés sur un compte réel. La voie API Creators reste distincte et prioritaire ; si elle ne donne pas accès aux revenus, demander à Amazon les modalités autorisées de collecte du portail avant d'activer cet adaptateur. Aucun contrôle supplémentaire ne sera contourné.

## Vérifications ciblées

Tests locaux du parseur, des réimports/corrections, chevauchements, fenêtres partielles, métriques inconnues, sauvegardes/restauration, isolation Domadoo et contrat API simulé. Ils ne prouvent pas l’accès réel à l’API France. Aucun workflow CI, release ou déploiement engagé.

Résultat : 20 tests ciblés réussis (11 Amazon, 9 financiers existants) et un parcours navigateur réussi, de l’import fictif à la vue globale. Aucun appel Amazon authentifié pendant ces vérifications.
