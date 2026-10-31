# Domadoo — connexion automatique et diagnostic (V1.4.4)

## Parcours retenu

Le compte Domadoo intégré (`domadoo`) peut recevoir `DOMADOO_LOGIN` et
`DOMADOO_PASSWORD`, exclusivement dans l'environnement serveur. Sans ces variables,
la connexion humaine reste disponible. Les autres comptes de reporting ne les
réutilisent pas, afin de ne pas mélanger les comptes financiers.

Une synchronisation ouvre d'abord le portail avec la session chiffrée compatible.
Si l'espace affilié est reconnu, aucun identifiant n'est demandé ni soumis. Si le
formulaire de connexion apparaît, LinKs vérifie sa structure et sa destination,
remplit les champs `#field-email` et `#field-password`, puis clique `#submit-login`.
Il attend au maximum 60 secondes le marqueur visible `#my_affiliate_link` et le
résumé sur `/fr/affiliation`. La collecte commence sur cette page, sans navigation
initiale supplémentaire. Sa pagination et ses contrôles financiers sont conservés.

La session est enregistrée après une collecte complète. Un échec conserve la
session validée et le dernier relevé. Une vérification supplémentaire peut laisser
un état intermédiaire chiffré, repris par la fenêtre de connexion humaine pendant
24 heures. Aucun mot de passe, corps de formulaire ou capture automatique n'est
retourné à l'interface ni ajouté aux diagnostics. La saisie est effacée du champ
mot de passe à la fin de la tentative automatique.

## Requêtes et autorisations

- Le formulaire public observé le 31 octobre 2026 utilise POST
  `/fr/authentification`, avec un retour `/fr/affiliation` dans l'action et le champ
  caché `back`. Aucun identifiant réel n'a été soumis pendant cette inspection.
- Seule la phase d'authentification automatique autorise ce POST comme navigation
  principale, sur les hôtes Domadoo déjà autorisés. Les champs cachés sont soumis
  naturellement par le navigateur ; aucun POST fabriqué ni API interne n'est utilisé.
- Le retour observé reste dans les chemins déjà autorisés. Aucun chemin de profil,
  paiement, déconnexion, domaine tiers ou nouvel endpoint n'est ajouté.
- Avant collecte, cette permission est révoquée, succès ou échec. La collecte
  conserve GET/HEAD seulement. Les POST de vérification restent réservés au mode
  humain ; aucun défi n'est résolu ou relancé automatiquement.
- Le routage Playwright n'est pas un pare-feu : les redirections HTTP ne déclenchent
  pas systématiquement un nouveau handler. La validation du formulaire et de son
  retour, les hôtes fixes et la reconnaissance stricte de la page d'arrivée sont
  conservés. Les tests n'utilisent aucun réseau marchand, même pour les redirections.

## Comparaison avec Creator Studio

Référence actuelle : commit `43232392d4de2242e354a0b4a684725e9bf9c7bf`,
[DomadooScraper.ts](https://github.com/AymericLeFeyer/aylabs-creator-studio/blob/43232392d4de2242e354a0b4a684725e9bf9c7bf/apps/api/src/infrastructure/integration/api/DomadooScraper.ts),
[browser.ts](https://github.com/AymericLeFeyer/aylabs-creator-studio/blob/43232392d4de2242e354a0b4a684725e9bf9c7bf/apps/api/src/infrastructure/integration/api/browser.ts).
La version exacte de l'image installée chez l'administrateur n'a pas été vérifiée.

Creator Studio lance Firefox headless, crée une session neuve à chaque opération,
remplit le formulaire et attend le même marqueur pendant 60 secondes. Il n'utilise
pas d'API particulière. LinKs reprend ce parcours fonctionnel et ajoute la reprise
de session, sans reprendre son plafond de 50 pages ni ses traitements financiers.

Le verrouillage Creator Studio utilise Playwright 1.63.0 ; LinKs conserve
Playwright Core 1.64.1 avec son Firefox officiel correspondant (157.0). Aucun essai
comparatif authentifié ne prouve qu'une rétrogradation corrigerait le refus.
Firefox headless reste le moteur par défaut, Chromium reste optionnel. La version
exacte est visible dans le diagnostic et les deux binaires sont testés dans Docker.

Creator Studio active `playwright-extra` et `puppeteer-extra-plugin-stealth`, sauf
le remplacement du user-agent. Certaines injections JavaScript peuvent fonctionner
avec Firefox ; les fonctions CDP propres à Chromium ne prouvent pas que tout le
module est inactif. Sa nécessité n'a pas été mesurée. LinKs n'ajoute aucun de ces
composants de dissimulation, ni proxy tournant, solveur ou rejeu externe de jeton.

## Échec observé et limites

L'essai réel rapporté sous Firefox 157.0 montre : affiliation HTTP 302, formulaire
HTTP 200, puis authentification HTTP 403 avec `cf-mitigated: challenge`. La session
était neuve. Il s'agit d'un contrôle Cloudflare réel, avant accès confirmé aux données.
Une navigation classée `domadoo:autre` a aussi été bloquée ; son chemin n'était pas
conservé, donc son rôle reste indéterminé. Le formulaire public retourne vers
l'affiliation autorisée, sans preuve d'un détour nécessaire par « Mon compte ».

Le POST interdit en collecte était un obstacle à l'ajout de la connexion automatique,
mais n'explique pas à lui seul le 403 du parcours humain, où ce POST était autorisé.
Aucune preuve ne permet d'attribuer cet échec au matériel ou au VPS. Un changement
vers le NAS n'est pas requis par ce correctif.

## Validation et informations utiles en cas d'échec

Les tests synthétiques couvrent formulaire et champs cachés, authentification,
collecte financière, session valide et expirée, redémarrage, permissions révoquées,
formulaire modifié, erreur de formulaire, HTTP 403, contrôle Cloudflare, MFA,
navigation bloquée et reprise humaine. Les tests natifs Docker AMD64/ARM64 vérifient
les deux navigateurs avec UID 101, lecture seule, `/tmp` noexec de 512 Mo et `/data`.
La CI conserve les tests Affiliation, titres, campagnes et pont PulSe existants.

Après déploiement par l'administrateur : configurer les deux variables, cliquer
Synchroniser, vérifier les chiffres, puis tester une seconde collecte et un
redémarrage. L'acceptation réelle par Cloudflare reste à valider ; aucune réussite
de connexion au compte n'est annoncée sur la seule base des tests synthétiques.

En cas d'échec, conserver le message de synchronisation et, si la fenêtre humaine
est utilisée, copier son diagnostic : étape, version du navigateur, session,
HTTP, Ray ID, catégories de navigation bloquées et heure UTC. Ne transmettre aucun
identifiant, cookie, fichier de session ou HAR. Les erreurs `security_check`,
`authentication_rejected`, `request_policy` et HTTP restent distinctes. Un 401
classé Cloudflare ne suffit pas, seul, à expliquer un échec de vérification.

Voir [configuration et exploitation](affiliation.md),
[documentation Playwright](https://playwright.dev/docs/auth) et
[navigateurs Cloudflare](https://developers.cloudflare.com/cloudflare-challenges/reference/supported-browsers/).
