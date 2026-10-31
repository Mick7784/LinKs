# Descriptions — phase 1

Base d'intégration : V1.4.1, commit `0c26ee2`. Les PR #60 (affiliation) et
#61 (titres) sont fusionnées. Cette phase ajoute les modèles et le stockage ;
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
  de sections. La consultation est en lecture seule dans cette phase.

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
exprimées en points de code Unicode ; l'adaptateur de l'éditeur devra convertir
explicitement les indices UTF-16 du navigateur. Aucune analyse ne régénère le
texte. Les versions finalisées sont réservées pour la phase 5 : aucun endpoint
de finalisation n'est exposé, et le service refuse leur mise à jour.

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

2. Éditeur libre, enregistrement automatique, récupération locale, import,
   suivi des sections après éditions et annulation.
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
  brouillons, conflits concurrents, Amazon, sauvegardes et versions immuables.
- `node scripts/descriptions-browser-test.cjs` : serveur sur port aléatoire et
  base temporaire, aucun accès marchand, associations historiques, ordres souris
  et clavier, conflits, duplication, création/consultation de brouillon,
  suppression du modèle et thèmes desktop clair/sombre.
- Tests existants de sauvegardes historiques, partenaires, doublons et sources.
  Les nouveaux tests sont ajoutés au workflow de PR existant. Aucun changement
  des conditions de publication, de `VERSION` ou de release intermédiaire.
