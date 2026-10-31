# Régression des titres V1.331 : diagnostic et correction

## Cause reproduite

Base : V1.331 (`6bdfa4ea03d6adadf14e09936e9fb01e566cc228`).
Le transport de cette version transforme une limite de lecture de 256 Kio en
rejet de la réponse entière. Le contrôle de `Content-Length`, ou la lecture du
262 145e octet, lève « Page trop volumineuse ». Les 262 144 octets déjà reçus sont
alors perdus, même s'ils contiennent le produit et toutes ses métadonnées utiles.

Reproduction locale du 31 octobre 2026 avec le transport de production, DNS et
TLS réels, sans VPS :

| Page fournie | HTTP | Taille observée en clair | V1.331 |
| --- | --- | ---: | --- |
| [Home Assistant Green](https://www.domadoo.fr/fr/produits-compatibles-home-assistant/7046-nabu-casa-box-domotique-home-assistant-green-0860011789703.html) | 200 | 415 788 octets | Page trop volumineuse |
| [Capteur CO MOES](https://www.domadoo.fr/fr/peripheriques/6933-moes-capteur-de-co-monoxyde-de-carbone-zigbee-tuya-zc-hm.html) | 200 | 417 170 octets | Page trop volumineuse |
| [Ko-fi](https://ko-fi.com/domotik_studio) | 200 | 386 618 octets | Page trop volumineuse |

La vérification de Green a aussi utilisé le paramètre d'affiliation fourni : il
n'est ni retiré de la requête ni modifié dans les données. Une page publique
Instagram testée reproduisait également le rejet de taille ; l'URL Instagram
personnelle, les liens Amazon et les 16 destinations complètes n'ont pas été fournis.
Nous ne prétendons donc pas avoir rejoué ces 16 liens ou identifié leur produit Amazon.

Une inspection exploratoire distincte, plafonnée à 2 Mio, a permis de mesurer les
trois pages et de comparer leur contenu aux 256 premiers Kio. Dans les trois cas,
les métadonnées nécessaires étaient déjà présentes dans cette portion. La limite
de production n'a pas été augmentée.

## Parcours et facteurs aggravants

1. `POST /api/tracked-links/title-preview` transmet l'URL et le titre actuel au
   même `url_inspection.suggest_title` que les créations individuelle et en lot.
2. `_target`, DNS public, IP verrouillée et TLS autorisent ces trois destinations.
   Elles répondent HTTP 200 sans redirection lors de la mesure.
3. Le rejet de taille intervient avant le parseur : ni JSON-LD, ni Open Graph,
   ni H1 n'arrive au classement. Ce n'est pas un échec de détection du produit.
4. Toutes les `InspectionError` devenaient `fetch_failed`. L'interface regroupait
   ce résultat avec une absence d'identité, sans expliquer réseau, HTTP ou taille.
5. Les réponses compressées étaient aussi rejetées, même si elles respectaient
   la taille après décompression. Ce facteur était présent dans le code ; la
   mesure initiale en `identity` démontre d'abord le rejet de taille.
6. Une exception supprimait tout repli sur le slug. En cas de réponse HTTP bloquée,
   le slug restait systématiquement de faible fiabilité et ne pouvait remplacer
   un nom courant, même réduit à la marque.
7. Un slug identique pouvait être présenté comme un titre « déjà pertinent » alors
   que l'extraction n'avait rien confirmé. Ce cas est désormais `retained` avec le
   motif `url_matches_current`, et non `unchanged`.

Les premières fixtures synthétiques de V1.331 étaient petites. Elles validaient
le classement mais ne reproduisaient pas les tailles réelles ; le test existant
considérait même le rejet intégral comme attendu. Les tests de régression corrigent
ce contrat et exercent le lecteur de production, pas seulement une réponse injectée.

## Correction dans le moteur existant

- Lire une portion bornée, fermer la réponse dès la limite et garder les éléments
  complets déjà reçus. Ne jamais accepter un H1, titre ou JSON-LD coupé.
- Accepter gzip/deflate avec plafonds distincts sur les octets reçus et décompressés.
  Un octet sentinelle au maximum dépasse chaque plafond de détection ; le HTML
  conservé reste limité à 262 144 octets. Les compressions inconnues ou invalides
  ont un motif explicite et ne sont pas décompressées sans borne.
- Conserver les protections SSRF, validation DNS de chaque destination, IP verrouillée,
  TLS, quatre redirections, trois secondes d'attente réseau/DNS et douze secondes
  de budget global. Aucune exception de sécurité pour les plateformes marchandes.
- Autoriser un slug descriptif d'au moins trois mots utiles à améliorer une marque
  seule ou enrichir un titre sans en perdre les mots utiles. Aucune information
  issue des paramètres d'URL, identifiants opaques ou codes d'invitation.
- Refuser tout repli après un blocage de sécurité ou une redirection invalide.
  Après une erreur de connexion d'un lien court résolu, utiliser l'URL descriptive
  déjà résolue, avec le motif réseau conservé.
- Raccourcir les formes Domadoo attestées. « Capteur CO Zigbee MOES » n'est produit
  que si CO, Zigbee et MOES sont réellement présents. Les références déjà utiles
  dans le titre actuel restent protégées par la comparaison.
- Conserver les noms existants Instagram/Discord. Une erreur de récupération
  conserve le nom avec son motif d'échec, sans prétendre avoir validé le titre.

## Résultats sur les trois URL exactes

| Titre actuel du test | Résultat corrigé | État | Fiabilité |
| --- | --- | --- | --- |
| Home Assistant Green | Home Assistant Green | Déjà pertinent, confirmé par Product et H1 | Élevée |
| Capteur CO MOES | Capteur CO Zigbee MOES | Amélioration | Élevée |
| Paye-moi un café | Paye-moi un café | Page identifiée ; aucun gain à remplacer le français | Élevée |

Les trois pages ont été récupérées avec HTTP 200 en gzip, lecture plafonnée à
256 Kio décompressés. La portion lue contient les mêmes noms produits ou profil
qu'avec la mesure exploratoire complète. Le nombre de propositions n'est pas
un objectif : le titre Green déjà correct et le titre Ko-fi français sont conservés.

Amazon est vérifié hors ligne avec un produit accessible et avec HTTP 403, 404,
429 et 503 : nom produit attesté dans le premier cas, titre actuel et code HTTP
précis dans les autres. Aucun ASIN n'est transformé en référence inventée.

## Diagnostic exploitable et exécution réelle

L'API privée expose un petit objet `diagnostics` par analyse :

- `fetch` : état, code, étape en échec, statut HTTP, nombre de redirections,
  statuts des sauts (au maximum cinq), octets lus/transférés, compression, limite atteinte ;
- `extraction` : état, nombre de métadonnées/H1/JSON-LD, JSON-LD invalides,
  candidats retenus/génériques, source choisie et score ;
- `decision` : statut, motif, source et fiabilité.

`engine.id` vaut `bounded-metadata-v2` et `engine.fingerprint` contient les douze
premiers caractères du SHA-256 du fichier chargé. L'interface donne le motif précis
et un volet « Diagnostic » discret. Pas de journal automatique supplémentaire,
ni URL, paramètres d'affiliation, IP, HTML, cookies, en-têtes ou texte d'exception
dans ces diagnostics. Les liens n'y sont pas sérialisés.

Le test HTTP appelle la vraie route, le vrai moteur et le lecteur gzip avec une
réponse locale contrôlée, et compare l'empreinte au fichier attendu. Le smoke test
des images appelle aussi la vraie API et vérifie son empreinte : une URL privée
est refusée avant DNS/réseau, ce qui ne dépend d'aucun site extérieur. Cette
vérification s'exécute dans les images jetables AMD64/ARM64 du workflow existant.
Elle ne vérifie pas une instance déjà déployée, puisque le VPS est exclu du périmètre.

## Tests

82 tests Python ciblés et trois parcours navigateur réussis localement. Les
11 nouveaux tests de récupération comprennent de multiples sous-cas : pages
volumineuses avec/sans Content-Length, gzip, deflate, expansion compressée de 5 Mio,
balises coupées, erreur réseau/DNS/TLS, HTTP, redirections, métadonnées absentes,
rejet par score, repli descriptif et confidentialité du diagnostic.

Les fixtures minimales de `scripts/fixtures/titles/` reprennent uniquement les
titres, métadonnées et noms structurés observés sur les pages publiques fournies.
Le remplissage recrée les tailles en mémoire. Aucun site externe n'est requis
pour les tests automatisés. La validation complète de la PR inclut les tests
applicatifs existants et les contrôles Docker, sans publication d'image.

Aucune modification de version, release, fusion sur main ou intervention sur le VPS
n'est nécessaire pour soumettre ce correctif à validation.
