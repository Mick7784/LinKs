# Descriptions — phases 1 à 4

Base d'intégration : V1.4.3, commit `55c64e8`. Les PR #60 (affiliation) et
#61 (titres), ainsi que les correctifs ultérieurs de main, sont intégrés.
Ces phases ajoutent modèles, stockage, éditeur, analyse locale et préparation
marchande ; elles ne dupliquent aucun service de titres, partenaires, liens ou sources.

## Périmètre livré

- Une entrée **Descriptions**, avec liste et consultation des brouillons et
  gestionnaire de modèles : création, édition, duplication, suppression,
  sections et sous-sections marchandes, déplacement souris/clavier et position
  numérique, textes et règles d'affichage.
- Modèle **YouTube — DomotiK Studio**, exactement sept sections. Les textes
  permanents proviennent du fichier fourni, conservé intégralement dans
  `scripts/fixtures/descriptions/smlight.txt`. Les produits, résumé, vidéo
  complémentaire, chapitres et hashtags spécifiques ne sont pas préremplis.
- Les liens Ko-fi, boutique Domadoo, Instagram et Discord portent une URL de
  référence et une association explicite `link_id` / `source_id`. La référence
  n'est jamais publiée en remplacement d'une association manquante.
- Sélection des liens déjà publiés, y compris **YouTube Description** historique
  et sources renommées, par identifiants stables. Aucun nouveau jeton, alias,
  fiche ou source ; aucun regroupement de statistiques.
- Aperçu textuel et signalement des références manquantes ou indisponibles.
- Création d'un brouillon avec texte initial, copie du modèle et associations
  de sections, puis ouverture dans l'espace de rédaction.
- Éditeur texte libre desktop (65 %), assistant à droite (35 %), séparation
  réglable à la souris ou au clavier. L'aperçu affiche le texte exact, sans HTML.
- Import explicite par collage d'une description complète, annulation et
  rétablissement du texte et des associations (100 étapes pendant la session).
- Suivi des sections par identifiant, indépendamment du titre visible. Les
  déplacements exacts et les modifications à l'intérieur d'une section
  conservent son identité. Après une modification ambiguë, les titres servent
  uniquement à proposer des emplacements : l'utilisateur confirme une
  proposition ou une sélection dans le texte. Les chevauchements sont refusés.
- Restauration annulable d'une section confirmée depuis son contenu initial
  figé, y compris les URL permanentes rendues à la création. Modifier le modèle
  ou le catalogue ultérieurement ne change pas cette copie.

Le partenaire d'une sous-section est choisi dans le catalogue existant.
L'association reste configurable : aucune règle `domid` n'est recopiée ici.
La boutique Domadoo reste affichée sans produit ; Amazon vide est masqué.

## Conservation et concurrence

`scripts/descriptions.py` travaille dans la transaction et sous le verrou
SQLite existants, avec trois tables additives : `description_templates`,
`description_drafts`, `description_versions`. Chaque document possède un
identifiant, une révision, des dates et un contenu JSON validé. Les références
externes sont des identifiants dans ce contenu : elles ne bloquent pas la
restauration du catalogue et leur absence est signalée lors de l'aperçu.

Une écriture exige la révision attendue. Un conflit renvoie HTTP 409 et conserve
la saisie locale. Une édition effectuée pendant une réponse d'enregistrement
reste non enregistrée, sans être remplacée par la réponse précédente.
Les identifiants de sections ne dépendent ni du titre ni de la position.
Supprimer un modèle conserve une tombstone, ses brouillons et leurs copies du
modèle ; le modèle initial ne réapparaît pas au redémarrage.

Le schéma de brouillon conserve séparément texte, modèle d'origine et sa copie,
associations, produits, sélections et ordre manuel. Les positions initiales sont
exprimées en points de code Unicode ; `description-sections.js` convertit
explicitement les indices UTF-16 du navigateur, sans normaliser les accents,
emojis ou URL. Les séquences de substitution Unicode isolées sont refusées.
Aucune analyse ne régénère le
texte. Les versions finalisées sont réservées pour la phase 5 : aucun endpoint
de finalisation n'est exposé, et le service refuse leur mise à jour.

L'éditeur enregistre après 700 ms d'inactivité et sérialise ses requêtes. Un
accusé de réception met à jour uniquement la révision et les métadonnées :
jamais le texte, les associations ou la sélection en cours. Chaque mutation
porte un identifiant et une empreinte pour permettre une répétition exacte
après perte de réponse. La saisie reste possible pendant l'enregistrement.

Un conflit bloque la sauvegarde automatique. L'utilisateur peut consulter le
texte serveur, ouvrir cette version en gardant sa récupération locale, ou
enregistrer sa propre copie dans un nouveau brouillon. Aucun écrasement forcé.
L'API conserve la copie du modèle et les liens. Les champs éditables sont le
titre interne, le texte et les repères de sections, complétés en phase 3 par
les références, sélections et classements explicitement versionnés et validés.

Chaque modification non enregistrée est copiée dans `localStorage`, sous une
clé propre à l'instance, au brouillon et à l'éditeur. Une interruption propose
une reprise explicite au prochain chargement. Les copies d'autres onglets sont
distinctes ; une base de révision périmée déclenche aussi un conflit à la reprise.
Un stockage local indisponible est signalé. Ces récupérations dépendent du même
navigateur et appareil, et ne remplacent pas la sauvegarde serveur. L'historique
Annuler/Rétablir reste limité à la session ; le texte et ses repères, eux, sont
persistants. Les sections masquées sans emplacement doivent être associées
explicitement, éventuellement à une sélection vide, avant restauration.

Les brouillons de phase 1 sont adaptés en mémoire lors de l'ouverture, sans
écriture ni consultation des liens actuels. Leur texte initial déjà enregistré
sert de référence ; leurs sections absentes restent à confirmer. Le premier
enregistrement conserve cette adaptation dans l'enveloppe existante.

## Sauvegarde et restauration

L'export existant `links-backup` inclut dès cette phase une enveloppe
`descriptions: {version: 1, tables: ...}`, suivant le principe d'extension déjà
utilisé pour l'affiliation. Les trois tables et les tombstones y sont incluses.
Une sauvegarde ancienne sans cette enveloppe conserve les données Descriptions.
Une enveloppe partielle ou invalide annule la restauration.

La restauration fusionne sans écraser les éditions actuelles. Les éléments
absents sont ajoutés. Si un modèle ou brouillon sauvegardé diffère d'un élément
existant, celui-ci est conservé et une copie **— restauré** est récupérée avec un
identifiant déterministe. Réimporter le même fichier ne multiplie pas les copies.
Les copies de modèles restent indépendantes des copies déjà incluses dans les
brouillons. Un conflit de contenu sur une version finalisée est refusé.
La prévisualisation utilise la même validation puis annule sa transaction.
La confirmation de restauration indique les ajouts, éléments conservés et copies.

Une version ancienne de LinKs ne connaît pas cette enveloppe : conserver le
fichier de sauvegarde complet et la copie du volume avant tout retour de version.
Pas de suppression de table historique, de nouveau service ou de variable
d'environnement. `Dockerfile` embarque le module et son modèle initial.

## Frontières des phases suivantes

4. Fournisseurs de recherche séparés par marchand, avec capacités déclarées :
   recherche intégrée Domadoo si un accès fiable et autorisé est disponible,
   ouverture du site et collage en secours. L'association au partenaire est déjà
   stockée ; aucun code de collecte du portail d'affiliation n'est détourné.
   Amazon : URL fournie intacte, insertion directe avec absence de statistiques
   LinKs annoncée ; aucune redirection implicite. La phase 1 refuse de rendre
   une association Amazon en URL courte, même si elle existe dans le catalogue.
5. Comparaison, opérations indépendantes validées, finalisation, copie et
   historique consultable/restaurable en nouveau brouillon.

L'aperçu d'un modèle ne prétend pas vérifier la santé distante d'un lien.
Les intitulés du modèle n'écrivent jamais dans les noms des fiches globales.

## Analyse locale et catalogue (phase 3)

Le panneau **Analyse et catalogue** se met à jour automatiquement après 400 ms
d'inactivité. L'endpoint privé `POST /api/descriptions/drafts/{id}/analyze` est
en lecture seule : il travaille côté LinKs sur le texte courant et le catalogue
SQLite, sans DNS, HTTP externe, suivi de redirection, comptage, création ou
modification de lien, source ou jeton. Le bouton **Actualiser le catalogue**
relance cette même lecture locale. Une réponse dépassée est ignorée ; les choix
actuels sont toujours appliqués à la vue des résultats, jamais remplacés par
ceux d'une ancienne requête.

Les URL HTTP(S), `www.`, `amzn.to` et `link.amazon` sont reconnues avec leurs
positions Unicode. Une même URL répétée conserve une identité et ses différentes
occurrences. Les jetons `/go/` et alias ne sont reconnus que sur l'origine LinKs
configurée, à partir des enregistrements existants, y compris les campagnes.
Un alias révoqué ou une fiche/source indisponible est signalé. La comparaison
des destinations réutilise `tracked_links.canonical_destination` sans réécrire
les URL ; les destinations et URL d'origine du catalogue sont consultées.

Les sources YouTube actuelles, historiques « YouTube Description » / « YouTube
Post » et les identités explicitement associées au modèle sont proposées. Le
jeton déjà cité conserve sa source même si elle a été renommée. Une destination
avec plusieurs fiches ou plusieurs publications YouTube nécessite un choix
explicite. Les autres sources existantes restent accessibles manuellement.

La reconnaissance des produits est volontairement conservatrice : libellés
commerciaux devant les URL, noms du catalogue réellement cités et références
marque/modèle explicites. Les textes permanents, les hashtags (y compris dans
une ligne), les technologies seules, les boutiques et les vidéos complémentaires
ne servent pas à déduire des produits. Les accessoires absents de la mention
ne sont pas proposés par rapprochement de mots. Une variante imprécise reste
une correspondance possible ; les références proches ne sont pas fusionnées
arbitrairement. Une référence non reconnue peut être ajoutée et corrigée
manuellement, et les liens peuvent être associés au produit choisi.

Les propositions sont regroupées par produit et marchand indépendant. Les
liens déjà présents sont présélectionnés ; les ajouts et déplacements restent
décochés. Un choix devenu indisponible est inactif, sans perte de son intention
enregistrée. Un lien direct Amazon conserve exactement l'URL fournie ; aucune
source de redirection n'est activée pour lui. L'absence de statistiques LinKs
dans ce mode est affichée.
Un lien LinKs déjà présent vers Amazon est identifié mais sa réutilisation est
inactive tant que l'utilisateur n'a pas confirmé une URL affiliée directe dans
le texte. Son association historique reste lisible ; aucune redirection Amazon
n'est préparée silencieusement.

`url_inspection.suggest_local_title` expose les règles locales du moteur de
titres existant, sans sa couche réseau. Les intitulés écrits dans le texte sont
conservés ; les corrections du panneau restent propres au brouillon. Il n'y a
ni catalogue produit supplémentaire ni second moteur d'affiliation.

Les références manuelles sont conservées dans `products`, les décisions dans
`selections.description_analysis` et l'ordre souris/clavier dans `manual_order`.
Le marqueur `analysis_version: 1` valide ce complément au format existant.
Les résultats automatiques sont recalculables, identifiés par le texte exact de
l'URL ou la référence normalisée ; les décisions devenues obsolètes restent
inactives et peuvent retrouver leur proposition après une annulation. Les
anciens clients qui n'envoient pas ces champs ne les effacent pas. Les révisions,
la récupération après interruption et les sauvegardes couvrent aussi ces choix.

Aucune opération n'est appliquée au texte. La préparation marchande est décrite
ci-dessous ; comparaison et application finale restent en phase 5. L'aperçu
rapide continue d'afficher le texte réellement saisi.

## Phase 4 — recherche marchande et préparation

Le panneau de chaque produit comporte un volet compact **Recherche marchande**.
**Rechercher tous les produits** parcourt les références de l'analyse courante,
en consultant d'abord le catalogue LinKs et les URL explicitement présentes.
Les marchands déjà résolus sont ignorés individuellement. **Rechercher à nouveau**
relance un seul produit, avec des mots-clés modifiables. Aucune recherche marchande
ne part pendant la frappe, le chargement ou la récupération d'un brouillon.

Les fiches existantes et les destinations fournies sont proposées séparément par
marchand, avec titre, référence et URL. Plusieurs correspondances demandent un
choix explicite. Les références du catalogue sont ses noms existants : aucune
référence fabricant manquante n'est inventée. Les états sont : lien existant,
produit trouvé, recherche nécessaire, lien Amazon à fournir, aucune correspondance
et erreur de recherche. Une absence de résultat peut être signalée manuellement
après recherche sur le site ; elle n'est pas déduite d'une erreur technique.

### Domadoo : parcours assisté effectif

Vérification ciblée du 31 octobre 2026 : la page publique
[Domadoo](https://www.domadoo.fr/fr/) expose un formulaire GET
`https://www.domadoo.fr/fr/recherche?s=…`. Le fichier public
[robots.txt](https://www.domadoo.fr/robots.txt) exclut notamment les chemins de
recherche et `controller=search`. Aucune API produit publique autorisée n'a été
identifiée. Les deux pages publiques ont répondu HTTP 200 ; aucune interrogation
automatisée des résultats, connexion affilié ou tentative de contournement n'a
été effectuée. La recherche intégrée distante n'est donc **pas activée**.

Le bouton **Ouvrir sur Domadoo** ouvre les résultats dans un nouvel onglet.
L'utilisateur choisit une fiche et colle son URL dans le panneau. Le point
d'entrée `description_search.merchant_search` est isolé et remplaçable par un
futur fournisseur officiellement autorisé ; il retourne actuellement un parcours
assisté et n'utilise ni `affiliation.py`, ni le connecteur de reporting.

**Préparer ce lien** utilise `affiliate_partners.preview_tracked`, la détection du
partenaire existant, sa règle courante et `tracked_links.duplicate_destinations`.
La règle Domadoo retire les occurrences existantes de sa clé avant de l'ajouter
une seule fois (`domid=117` avec la configuration initiale). Une règle absente ou
une destination incompatible bloque la préparation. Une fiche existante choisie
conserve sa destination enregistrée. Les doublons sont proposés pour réutilisation ;
plusieurs fiches équivalentes demandent un choix. Aucun doublon n'est créé.

### Amazon : URL officielle fournie par l'utilisateur

Les correspondances disponibles proviennent du catalogue et du texte, sans
requête automatique à Amazon. **Ouvrir sur Amazon** ouvre les résultats de la
recherche ; chaque résultat connu permet aussi d'ouvrir sa fiche. **J'ai déjà un
lien affilié** donne accès au champ de collage du lien généré officiellement.

La préparation conserve exactement la chaîne fournie : `amzn.to`, `link.amazon`,
URL longues, paramètres répétés, encodages et fragments. Aucun appel au moteur
d'affiliation, résolution de lien court, reconstruction d'ASIN, changement de tag
ou redirection LinKs. Le seul mode proposé est **direct**, avec le message
**sans statistiques de clics LinKs**. Les liens nus reconnus peuvent être validés
sur une copie absolue, mais la destination stockée reste la chaîne originale.
Les champs acceptent 2 000 caractères, comme le moteur de liens existant.

### Conservation et limites

Les intitulés courts proviennent de `suggest_local_title`, sans requête distante.
Ils sont modifiables dans le brouillon uniquement. Chaque préparation indique la
destination, la sous-section de la copie du modèle et, pour Domadoo, une source
YouTube existante. Une publication historique disponible est réutilisée ; si elle
n'existe pas, son état reste à préparer, sans allocation de jeton.

Les nouvelles propositions sont décochées. Les recherches et préparations restent
dans `selections.merchant_search` (version 1), sous les identifiants stables des
produits et des marchands : mots-clés, résultats temporaires, saisie d'URL,
destination préparée, choix, intitulé, source et emplacement. Ces instantanés
appartiennent exclusivement au brouillon ; ils ne constituent pas un catalogue
produit supplémentaire. Les sauvegardes/restaurations, révisions et récupération
locale de l'éditeur les couvrent sans migration de table. Les anciens clients
omettant l'état d'analyse conservent ces données.

Une réponse tardive ne remplace ni une recherche plus récente ni une saisie
d'URL ou d'intitulé récente. Une erreur conserve les résultats et choix précédents.
Les références retirées deviennent inactives, leurs choix restant disponibles
après annulation. Une recherche interrompue demande une relance manuelle. Les
liens marchands s'ouvrent avec `noopener noreferrer` sans navigation de l'éditeur.

La préparation ne crée aucun lien suivi, source, jeton, alias ou version finalisée.
Elle ne modifie jamais le texte. La phase 5 devra revalider la disponibilité des
fiches/sources et la règle du partenaire avant toute application : les instantanés
du brouillon ne sont pas une autorisation de créer. Comparaison, application,
copie et historique finalisé restent hors du périmètre livré.

## Validation

- `python3 scripts/description_search_test.py` : fournisseurs simulés, catalogue
  prioritaire, destinations exactes, doublons, sources historiques, aucune écriture
  catalogue, erreurs, états de recherche et sauvegarde/restauration des choix.
- `node --test scripts/description-search.test.cjs` : déclenchement explicite,
  relance ciblée, marchands résolus ignorés, choix conservés et réponses tardives.
- `node scripts/descriptions-search-browser-test.cjs` : SMLIGHT, recherche globale
  et individuelle, plusieurs fiches, erreur simulée, onglet marchand simulé,
  intitulés/sélections/ordre, URL Amazon exacte, reprise hors ligne et thèmes.
  Aucun test ne dépend de la disponibilité de Domadoo ou d'Amazon.

- `python3 scripts/description_analysis_test.py` : référence SMLIGHT, absence
  d'IO externe et d'écriture catalogue, alias/jetons/campagnes, sources historiques,
  ambiguïtés, exclusions, URL Amazon exactes et sauvegarde des choix.
- `node --test scripts/description-analysis.test.cjs` : conservation des choix,
  invalidation ciblée, classements et présélections.
- `node scripts/descriptions-analysis-browser-test.cjs` : catalogue réel de test,
  sources YouTube, intitulés locaux, réponses d'analyse retardées, références
  manuelles, classements et persistance après modification/rechargement.
- `python3 scripts/descriptions_test.py` : référence, modèle initial, absence
  d'effets sur les liens/sources/compteurs, reprise historique, isolation des
  brouillons, conflits concurrents, Amazon, sauvegardes et versions immuables ;
  positions Unicode, répétition des mutations, copie séparée, validation des
  associations et migration des anciens brouillons.
- `node --test scripts/description-sections.test.cjs` : conversion UTF-16,
  déplacements, renommage, couper/coller, ambiguïtés et confirmations.
- `node scripts/descriptions-editor-browser-test.cjs` : 65/35, saisie pendant
  une réponse retardée, annulation, restauration figée, déplacement, import de
  la référence SMLIGHT, sélection Unicode, conflit entre onglets, récupération
  hors ligne, accusé perdu et navigation pendant un enregistrement.
- `node scripts/descriptions-browser-test.cjs` : serveur sur port aléatoire et
  base temporaire, aucun accès marchand, associations historiques, ordres souris
  et clavier, conflits, duplication, création/consultation de brouillon,
  suppression du modèle et thèmes desktop clair/sombre.
- Tests existants de sauvegardes historiques, partenaires, doublons et sources.
  Les nouveaux tests sont ajoutés au workflow de PR existant. Aucun changement
  des conditions de publication, de `VERSION` ou de release intermédiaire.
