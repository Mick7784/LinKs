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
Un segment d'URL seul est de faible fiabilité et ne remplace jamais un nom courant.
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

L'API renvoie `title`, `source`, `status`, `confidence` et `reason` :

| État | Signification |
| --- | --- |
| `ok` | Proposition nouvelle ou amélioration démontrable |
| `unchanged` | Nom déjà pertinent, conservé exactement |
| `retained` | Destination identifiée, gain non démontré |
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
de douze secondes par récupération, 256 Kio maximum. Les résolutions DNS bloquées
sont bornées à huit tâches en attente. Les pages trop grandes ou compressées malgré
la demande `identity`, les contenus non HTML et les pages de challenge reconnues
sont refusés. Un refus de sécurité ne déclenche pas de repli sur un slug non vérifié.
Une réponse HTTP bloquée peut fournir un slug de faible fiabilité à la création,
mais ne remplace pas un titre existant.

Limites assumées : absence d'exécution JavaScript, pas de contournement de CAPTCHA,
pas d'identification d'un produit Amazon à partir du seul ASIN. Les pages lourdes,
dynamiques ou insuffisamment documentées conservent donc leur titre actuel.

## Tests reproductibles

`scripts/fixtures/title_metadata.json` couvre les exemples Domadoo, Amazon, Ko-fi,
Discord, Instagram, les titres déjà corrects, catégories, marques seules,
contradictions et références. Les produits et pages sont synthétiques ; le moteur
est testé sans accès externe, via transport et DNS injectés.

Commandes depuis le dépôt :

```sh
python3 scripts/url_inspection_test.py
python3 scripts/title_quality_test.py
python3 scripts/tracked_title_preview_test.py
python3 scripts/tracked_title_batch_test.py
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
