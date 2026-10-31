# Génération des titres : audit et règles de décision

## Audit initial — 31 octobre 2026

Base examinée : `d3ae6c4`, branche `feat/links-backoffice-ergonomie-20261031`.

Le service `scripts/url_inspection.py` est partagé par la création individuelle,
la création en lot et la révision des titres. L'API de prévisualisation est en
lecture seule ; la validation utilise le service existant de mise à jour atomique
des noms avec contrôle des modifications concurrentes.

Avant correction, la première valeur exploitable gagnait : premier `Product`
JSON-LD, Open Graph, Twitter, titre HTML, puis segment descriptif d'URL. Aucun
classement qualitatif, lecture du H1 ou comparaison serveur avec le nom courant.
Le nettoyage coupait au premier séparateur : un titre « NABU CASA - Home Assistant
Green » pouvait devenir « NABU CASA ». Une catégorie Amazon ou une marque seule
étaient acceptées comme un produit. La formulation anglaise de Ko-fi pouvait
remplacer un nom français. Ces causes sont constatées dans le code ; les exemples
HTML des tests sont des fixtures synthétiques, pas des captures des sites réels.

La fenêtre proposait déjà une édition manuelle et une sélection explicite. Elle
excluait les chaînes strictement identiques, mais ne distinguait pas une variation
cosmétique d'une amélioration réelle.

Le transport validait les IP publiques avant chaque connexion, refusait les
résolutions DNS mixtes et conservait la vérification TLS du domaine. Il limitait
les redirections à quatre, le délai socket à trois secondes et la lecture à
256 Kio. La limite de lecture permettait toutefois d'analyser une page tronquée ;
le DNS et la durée totale de la chaîne n'étaient pas bornés.

## Décision dans le service existant

La régression de récupération introduite en V1.331 et sa correction sont décrites
dans [l'audit de régression](audits/2026-10-31-title-regression.md).

Les candidats viennent de `Product` (nom, marque, modèle explicitement fourni),
des articles et profils structurés, du H1, du titre produit Amazon, d'Open Graph,
de Twitter, du titre HTML et du segment d'URL. Les listes de recommandations ne
servent pas à désigner le produit principal. Plusieurs produits incompatibles
entraînent l'abstention.

Le nettoyage retire les enseignes et formulations commerciales reconnues ; il
ne coupe plus au premier séparateur et ne tronque pas une référence longue.
La limite d'une proposition automatique est de 120 caractères ; au-delà, ce
candidat est écarté. Le champ manuel reste limité à 160 caractères.

La provenance et la concordance de sources distinctes déterminent une fiabilité
`high`, `medium` ou `low`. Ce sont des niveaux heuristiques, pas des probabilités.
Un segment descriptif d'au moins trois mots utiles a une fiabilité moyenne et peut
enrichir un nom ou remplacer une marque seule ; un segment moins précis reste de
faible fiabilité. Les identifiants opaques et les codes d'invitation ne sont pas des noms.
Les identités ou modèles contradictoires entraînent l'abstention, même lorsqu'une
source est prioritaire. Le titre HTML n'est jamais privilégié automatiquement.

Avec `current_title`, le moteur conserve les mots utiles et les références du nom
courant. Il accepte un enrichissement démontrable ou le remplacement d'une marque
ou d'un libellé générique reconnu. L'ajout de la seule marque connue, les variations
de ponctuation, de casse ou d'ordre ne sont pas comptés comme des améliorations.
Une formulation plus courte mais sémantiquement incertaine est volontairement
écartée. Les noms existants inconnus d'un seul mot ne sont pas réputés génériques.

Les adaptateurs de `_platform_candidates` alimentent cette même décision : profil
Instagram explicite dans l'URL, nom de serveur Discord attesté par les métadonnées,
formulation Ko-fi traduite à partir du nom effectivement présent. Un code
d'invitation Discord n'est pas utilisé comme nom du serveur. Aucune traduction
générale, API d'IA, référence inventée ou dépendance supplémentaire.
Les noms existants d'Instagram et Discord sont conservés. Les formes produit
Domadoo reconnues sont raccourcies seulement lorsque les mots du nom ou du slug
attestent chaque caractéristique : par exemple, « Zigbee » n'est jamais ajouté
à un capteur dont les indices ne le mentionnent pas.

L'API renvoie `title`, `source`, `status`, `confidence`, `reason`, ainsi que
`engine` (identifiant et empreinte du fichier chargé) et `diagnostics` :

| État | Signification |
| --- | --- |
| `ok` | Proposition nouvelle ou amélioration démontrable |
| `unchanged` | Nom déjà pertinent, conservé exactement |
| `retained` | Titre conservé sans gain démontré ; un slug concordant n'atteste pas une extraction réussie |
| `unavailable` | Identification impossible, contradictoire ou récupération refusée |

Sans `current_title`, le contrat de création reste `ok` ou `unavailable`.
La prévisualisation ne modifie aucune donnée. La fenêtre laisse toutes les cases
décochées, affiche les états et la fiabilité, permet une correction manuelle même
après un échec et n'active la validation que pour des modifications sélectionnées.

## Récupération distante

Les contrôles SSRF et le verrouillage de la connexion sur l'IP validée sont conservés.
Les adresses multicast/réservées sont également refusées. Le validateur LinKs est
réappliqué aux redirections pour ne pas suivre un retour vers ses liens suivis.
Les URL, paramètres d'affiliation et destinations enregistrées ne sont jamais
réécrits.

Limites : quatre redirections, trois secondes d'attente réseau/DNS, budget global
de douze secondes par récupération. Le moteur conserve au maximum 256 Kio de HTML
et borne également les octets transférés (un octet sentinelle supplémentaire permet
de constater la limite). Gzip et deflate sont décompressés dans cette même limite.
La lecture s'arrête dès qu'une limite est atteinte ; le reste n'est pas téléchargé.
Les métadonnées complètes de la portion lue restent utilisables, contrairement au
rejet intégral de V1.331. Un titre, H1 ou JSON-LD coupé n'est jamais exploité.
Les résolutions DNS bloquées sont bornées à huit tâches en attente.

Les erreurs réseau, HTTP, compression, redirection, extraction et classement sont
distinctes. Une erreur réseau ou HTTP peut autoriser un repli sur le slug descriptif
de l'URL validée, en conservant le motif d'échec dans le diagnostic. Un refus de
sécurité ou une redirection invalide ne déclenche jamais ce repli. Un slug concordant
avec le titre actuel produit `retained`, jamais `unchanged` : les métadonnées n'ont
pas confirmé ce titre. Les diagnostics ne contiennent ni URL, paramètres, IP, corps
de page, en-têtes ou messages d'exception ; ils ne sont pas journalisés automatiquement.

Limites assumées : absence d'exécution JavaScript, pas de contournement de CAPTCHA,
pas d'identification d'un produit Amazon à partir du seul ASIN. Lorsque la portion
lue et l'URL ne suffisent pas, le titre actuel est conservé avec un motif précis.

## Tests reproductibles

`scripts/fixtures/title_metadata.json` couvre les exemples Domadoo, Amazon, Ko-fi,
Discord, Instagram, les titres déjà corrects, catégories, marques seules,
contradictions et références. Les produits et pages sont synthétiques ; le moteur
est testé sans accès externe, via transport et DNS injectés.
`scripts/fixtures/titles/` contient les métadonnées minimales observées sur les
trois pages réelles fournies. Le test de régression recrée leur taille par remplissage
et exerce le transport de production en clair, gzip et deflate, sans sites externes.

Commandes depuis le dépôt :

```sh
python3 scripts/url_inspection_test.py
python3 scripts/title_quality_test.py
python3 scripts/title_fetch_regression_test.py
python3 scripts/tracked_title_preview_test.py
python3 scripts/tracked_title_batch_test.py
python3 scripts/tracked_copy_test.py
python3 scripts/tracked_batch_test.py
python3 scripts/affiliate_partners_test.py
python3 scripts/links_pulse_integration_test.py
node scripts/tracked-titles-browser-test.cjs
node scripts/tracked-title-browser-test.cjs
node scripts/tracked-batch-browser-test.cjs
```

Les tests HTTP utilisent des bases SQLite temporaires. Les tests navigateur
utilisent le serveur local et des réponses de prévisualisation contrôlées. Ils
vérifient l'édition, la sélection, les états, les compteurs, les thèmes et largeurs
320/390/1440 px ainsi que la conservation des URL, affiliations et statistiques.
Le test de qualité est ajouté à la suite existante du workflow, sans modifier ses
conditions de publication. Aucun lancement de workflow, release ou déploiement
n'est nécessaire pour exécuter ces tests locaux.
Le test HTTP vérifie l'empreinte du module réellement appelé. `scripts/smoke.py`
vérifie la même empreinte via l'API réelle de chaque image jetable AMD64/ARM64,
avec une URL privée refusée avant tout accès réseau.
