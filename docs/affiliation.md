# Affiliation V1 — exploitation et validation

Le reporting financier est distinct des liens affiliés, des campagnes et du pont
privé PulSe. Le seul collecteur disponible est Domadoo. Amazon, Affiliatly,
GoAffPro, Awin et Impact sont des plateformes configurables sans collecte en V1.
Un partenaire commercial peut posséder plusieurs comptes de reporting. Ajouter
un compte Domadoo réutilise le même moteur, sans changer le code ni les URLs.

## Déploiement Docker

- Image habituelle `ghcr.io/mick7784/links`, mêmes ports 8080 et 8081.
- Aucun nouveau port public, service Compose, secret ou variable obligatoire.
- Conserver le volume `/data` et son propriétaire UID/GID 101. Le changement de
  base Linux conserve cet utilisateur pour les volumes existants.
- Ajouter `init: true` et porter le tmpfs `/tmp` de 32 à **512 Mo** :
  `/tmp:rw,noexec,nosuid,size=512m,mode=1777`. C’est une limite, pas une réservation
  permanente de mémoire. Prévoir environ 1 Go de mémoire disponible pendant une
  collecte ; une seule instance de navigateur travaille à la fois.
- Firefox est désormais le navigateur par défaut, sans module de furtivité.
  Son binaire officiel correspond exactement à Playwright Core, verrouillé dans
  `package-lock.json`. Chromium système reste disponible pour diagnostic avec
  `AFFILIATION_BROWSER=chromium` ; aucune variable n’est nécessaire pour Firefox.
  Les deux navigateurs sont intégrés à l’image Debian pour AMD64 et ARM64. Chaque CI lance
  un contrôle hors réseau du navigateur livré, sur les deux architectures natives.
  Le contrôle ARM64 est un job préalable obligatoire, car l’émulation QEMU ne
  permet pas de qualifier le sous-processus graphique de Chromium. Le contrôle
  de l’application sous émulation reste également exécuté avant publication.
- L’administration doit être protégée par HTTPS et son authentification LinKs
  ou le contrôle d’accès externe déjà prévu. Ne pas publier directement 8081 sur
  Internet. Les commandes de connexion utilisent les mêmes contrôles d’origine
  et de session que les autres mutations administrateur.

Le processus interne écoute exclusivement `127.0.0.1:3004`, avec un jeton aléatoire
renouvelé à chaque démarrage et absent des fichiers de configuration. Il n’est
pas accessible par le serveur public ni par le pont PulSe. Aucun port de débogage
de navigateur n’est publié. Le conteneur reste non privilégié, en lecture seule et sans
capabilities. Chromium utilise le mode sans sandbox interne de Playwright ; la
restriction aux hôtes autorisés et l’isolation Docker sont donc importantes.
Ne pas utiliser ce service comme navigateur généraliste.

## Première connexion

1. Ouvrir **Affiliation → Domadoo → Connexion et synchronisation**.
2. Choisir **Ouvrir la connexion Domadoo**. La fenêtre montre le navigateur du
   serveur ; cliquer le champ souhaité, saisir dans le champ masqué sous l’image,
   puis choisir **Transmettre la saisie**. Tab, Entrée et défilement sont disponibles.
   L’ancienne session est reprise si elle est compatible. Après passage de Chromium
   à Firefox, une nouvelle authentification humaine est nécessaire ; les cookies
   d’un autre navigateur ne sont pas transférés automatiquement.
3. Effectuer personnellement l’authentification et toute double vérification.
   La fenêtre se ferme lorsque l’espace affilié est reconnu. Si elle reste ouverte
   après votre authentification, choisir **Vérifier mon accès affilié**. Aucun identifiant
   ni mot de passe n’est enregistré dans la configuration ou la base de LinKs.
4. Cliquer **Synchroniser**. Le travail continue côté serveur même en fermant
   l’administration. Une collecte complète peut prendre plusieurs minutes.
5. Vérifier les montants et les dernières pages avec le portail réel. Activer
   ensuite la collecte quotidienne et choisir l’heure/fuseau, après vérification
   des conditions d’utilisation du fournisseur.

La fenêtre expire après 15 minutes et se ferme automatiquement. Les captures
restent en mémoire, sans cache ni fichier. L’utilisateur peut réaliser les
contrôles présentés dans cette fenêtre ; le collecteur automatique s’arrête sur
une protection ou une session expirée. Aucune technique de furtivité ni résolution
automatique de CAPTCHA n’est utilisée. Si la protection refuse ce navigateur ou
nécessite un hôte/une navigation non autorisés, la V1 ne la contourne pas : la
connexion reste à qualifier avec Domadoo. Le bouton Déconnecter efface la session
et désactive le passage quotidien, sans effacer l’historique financier.

La persistance porte sur les cookies, localStorage, IndexedDB et le sessionStorage
de Domadoo, chiffrés avec la même clé locale que précédemment. Aucun profil complet,
historique, cache disque ou mot de passe du navigateur n’est sauvegardé. Un état
intermédiaire chiffré permet de reprendre la connexion pendant 24 heures après sa
fermeture ; il n’est jamais utilisé pour une collecte avant reconnaissance de
l’espace affilié, et ne remplace pas la dernière session validée. Déconnecter
supprime les deux états. Les sauvegardes portables restent sans session.

### Vérification Cloudflare persistante

Un accès réussi depuis votre ordinateur ne valide pas le navigateur utilisé par
LinKs depuis le serveur. Cloudflare indique que les navigateurs automatisés ne
sont pas pris en charge pour résoudre ses défis en production. Si la vérification
persiste, fermer la fenêtre et demander à Domadoo un accès automatisé autorisé,
un export ou un flux officiel. Aucun changement Compose ne garantit cet accès.

La fenêtre signale les pages de vérification reconnues et ne les recharge pas
avec « Vérifier mon accès affilié ». Les échanges POST du chemin de vérification
`/cdn-cgi/challenge-platform/` sont autorisés uniquement pendant la connexion
humaine ; ils restent bloqués pendant la collecte. Corriger ce filtrage ne garantit
pas l'acceptation du navigateur serveur. Aucun mécanisme de furtivité, rejeu de
jeton de validation ou résolution automatique de défi n'est ajouté.

Référence : [Navigateurs pris en charge par Cloudflare](https://developers.cloudflare.com/cloudflare-challenges/reference/supported-browsers/).

La fenêtre fournit désormais **Diagnostic de connexion → Copier le diagnostic** :
étape, navigateur/version, état de reprise, code HTTP, redirections classées,
blocages réseau classés, heure UTC et éventuel Ray ID. Aucun corps, saisie,
URL complète, paramètre, cookie ni jeton ne figure dans ce diagnostic. Les états
« formulaire », « erreur du formulaire », « vérification de sécurité », « HTTP
refusé » et « navigation interrompue » sont distincts. Une erreur de formulaire
ne prouve pas à elle seule que le mot de passe est incorrect.

Voir [la comparaison ciblée et les limites de validation](domadoo-connexion.md).

## Données et interprétation

- Les valeurs sont des entiers signés en centimes EUR, avec parsing strict des
  montants français. Un montant illisible invalide le relevé, sans zéro de secours.
- `check` signifie **approuvée**, `close` **non approuvée**. Cette dernière valeur
  ne permet pas de distinguer attente, refus ou annulation. Aucun montant
  « refusé » ou « commission en attente » n’est inventé.
- La période du graphique et du tableau est la **date de vente**, dans le fuseau
  non documenté du portail. Le statut est celui de la dernière observation ; ce
  graphique ne prétend pas représenter une date de validation comptable.
- Les compteurs du bloc **Last 30 days**, les cumuls et le solde gardent leurs
  périodes natives. Ils ne sont pas recalculés selon le filtre des transactions.
  Les clics uniques ne sont pas corrigés s’ils excèdent les clics.
- **Mes bons de paiement** garde date, montant, approbation et utilisation. Les
  codes des bons ne sont jamais lus. Les lignes n’ayant pas d’identifiant public
  stable observé, elles sont des observations complètes successives, pas un
  registre de virements. Les changements restent dans les snapshots SQLite.
- Les transactions sont identifiées par compte + ID fournisseur. Une correction
  financière, un changement de statut ou une disparition crée une révision.
  Une disparition n’est jamais classée automatiquement comme annulation.
- Les ventes absentes restent consultables, mais ne sont plus comptées dans les
  totaux du dernier état observé. Les diminutions et commissions négatives sont
  conservées ; le cumul du portail n’est pas remplacé par une somme supposée.
- L’export CSV provient de LinKs et suit la sélection de transactions. Il ne
  constitue pas un export natif Domadoo ni une preuve de paiement bancaire.

## Complétude, sessions et reprise

Le navigateur suit uniquement les liens de pagination de la page, jusqu’à la
dernière page annoncée, sans plafond de 50 pages. Les libellés, les colonnes,
les IDs, la pagination et les doublons sont vérifiés. Le début de l’historique,
le nombre de pages et les agrégats sont relus à la fin. Toute incohérence, page
vide inattendue, statut inconnu ou limite de 30 minutes interrompt la collecte.
Une modification ancienne isolée pendant la lecture peut néanmoins échapper
aux contrôles de bord : le portail ne fournit pas de snapshot transactionnel
ni de nombre exact de ventes vérifié indépendamment. La prochaine lecture
complète quotidienne réconcilie l’historique.

L’ingestion est atomique : aucun relevé partiel ne remplace le dernier valide.
L’administration sépare session enregistrée, collecte en cours, dernier succès
et dernier échec. Une session enregistrée ne garantit pas sa validité actuelle.
Après un redémarrage, un travail interrompu est marqué en échec. Le prochain
passage quotidien ou une synchronisation manuelle relit tout l’historique ; aucun
rejeu de mot de passe n’a lieu. Une échéance quotidienne manquée est exécutée au
prochain passage du planificateur (environ 30 secondes), sans rafale de rattrapage.

La session fournisseur est chiffrée AES-256-GCM dans `/data/affiliation/*.session`.
La clé aléatoire est dans `/data/affiliation/session.key`, permissions 0600 et
répertoire 0700. La clé et les sessions ne figurent ni dans SQLite ni dans la
sauvegarde JSON exportée. Une sauvegarde du volume contient les deux : la protéger
comme un secret ; le chiffrement ne protège pas contre un accès à tout le volume.
Les profils temporaires Chromium sont sous `/tmp` et supprimés à la fermeture.

## Sauvegardes

Une copie SQLite cohérente `pre-affiliation-v1.db` est créée avant la première
migration d’une base existante. Les nouvelles tables sont additives.
La sauvegarde JSON habituelle de LinKs inclut comptes, transactions, révisions,
relevés et journaux financiers, sans session navigateur. Sur une instance vierge,
la restauration importe cet historique avec collecte désactivée et reconnexion
humaine obligatoire. Sur une instance ayant déjà un historique financier ou des
comptes supplémentaires, cet historique est conservé pour éviter tout retour
en arrière ; le résultat de restauration l’indique. Une ancienne sauvegarde sans
Affiliation ne supprime pas les données financières existantes.

Pour une restauration exacte de l’instance, arrêter le conteneur et sauvegarder
le volume `/data` complet, puis le restaurer avec les permissions d’origine.
Ne pas copier seulement un fichier SQLite en cours d’écriture, en ignorant son
journal WAL. Ces opérations relèvent de l’administrateur du VPS.

## Validation réelle après déploiement

Les tests livrés utilisent uniquement des données synthétiques. La connexion
au compte réel et le comportement depuis l’adresse IP du VPS restent à valider.

1. Comparer exactement les 12 valeurs du résumé aux libellés du portail.
2. Comparer les IDs, dates, commandes, commissions et statuts d’au moins une
   vente de première, de milieu et de dernière page, ainsi que le nombre de pages.
3. Vérifier la distinction entre bons, paiements cumulés, paiement en attente et
   solde. Demander à Domadoo la signification comptable et les règles de correction.
4. Relancer sans changement : même état financier, aucune révision supplémentaire.
5. Après une correction réelle, vérifier le montant signé et sa révision, sans
   doublon. Comparer plusieurs fenêtres historiques, sans imposer une égalité
   entre gains du portail et somme de commissions de statuts différents.
6. Redémarrer puis relancer ; vérifier ensuite une déconnexion et une reconnexion
   humaine. Confirmer qu’un échec laisse le dernier relevé intact.
7. Vérifier un passage quotidien, le fuseau, la consommation mémoire et les temps
   de collecte. Confirmer l’autorisation d’automatisation et l’existence éventuelle
   d’un export ou flux officiel auprès de Domadoo.

Références runtime : [Docker Playwright](https://playwright.dev/docs/docker) et
[lancement Chromium](https://playwright.dev/docs/api/class-browsertype#browser-type-launch).
