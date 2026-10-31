# Descriptions — phases 1 et 2

Base d'intégration : V1.4.1, commit `0c26ee2`. Les PR #60 (affiliation) et
#61 (titres) sont fusionnées. Ces phases ajoutent les modèles, le stockage et l'éditeur ;
elle ne duplique aucun service de titres, partenaires, liens ou sources.

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
L'API ne permet de modifier que le titre interne, le texte et les repères de
sections : copie du modèle, liens, sélections et classements restent conservés.

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

3. Analyse locale et reconnaissance produit, sans requête marchande pendant la
   saisie ; adaptation du catalogue existant et du moteur de titres partagé.
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

## Validation

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
