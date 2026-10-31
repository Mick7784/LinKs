# Connexion Domadoo — comparaison ciblée du 31 octobre 2026

## Résultat et limite

L’échec rapporté avec LinKs V1.4.2 se situe **avant le formulaire de connexion**,
sur la vérification Cloudflare. Aucune preuve ne permet de l’attribuer au matériel
ou au VPS : Creator Studio a déjà fonctionné sur ce VPS, selon l’administrateur.

Une ouverture publique, sans authentification, a été comparée depuis le même
ordinateur Windows et avec la même politique de requêtes de LinKs :

| Navigateur local, sans furtivité | Réponse initiale | Formulaire |
| --- | --- | --- |
| Chrome/Chromium 156.0.8078.74, headless | HTTP 403 | Absent |
| Firefox Playwright 157.0, headless | HTTP 200 | Présent |

Firefox montre un formulaire POST vers `/fr/authentification` avec
`#field-email`, `#field-password` et `#submit-login`. Aucun identifiant n’a été
saisi et aucune protection n’a été actionnée. Des ressources de marketing,
cartographie et polices hors liste étaient bloquées ; cela n’empêchait pas le
formulaire Firefox d’apparaître. Aucune capture ni session réelle n’a été conservée.

Cela justifie Firefox par défaut. Ce n’est **pas** une validation du compte, du
challenge depuis le VPS ou du binaire Linux Chromium de l’ancienne image : le
test local utilise Chrome installé sur Windows. Le portail peut appliquer des
décisions différentes selon le navigateur, sa version, le réseau et le moment.
Seuls Domadoo/Cloudflare peuvent expliquer exactement leur décision de contrôle.

## Parcours comparés

Source Creator Studio examinée : commit `6660e2d869871ebbfb9eeadcc5918f57875397a2`,
[DomadooScraper.ts](https://github.com/AymericLeFeyer/aylabs-creator-studio/blob/6660e2d869871ebbfb9eeadcc5918f57875397a2/apps/api/src/infrastructure/integration/api/DomadooScraper.ts)
et [browser.ts](https://github.com/AymericLeFeyer/aylabs-creator-studio/blob/6660e2d869871ebbfb9eeadcc5918f57875397a2/apps/api/src/infrastructure/integration/api/browser.ts).
La version exacte anciennement déployée sur le VPS n’a pas été vérifiée.

| Point | Creator Studio audité | LinKs V1.4.2 | Correctif |
| --- | --- | --- | --- |
| Moteur | Firefox Playwright via playwright-extra | Chromium système via Playwright Core | Firefox officiel correspondant au verrouillage Playwright ; Chromium optionnel |
| Exécution | Headless, viewport 1280×720 | Headless, 1100×760 | Headless, 1100×760 ; aucune dissimulation ajoutée |
| Connexion | Remplit email/mot de passe puis clique `#submit-login` | Actions humaines transmises par la fenêtre LinKs | Actions humaines conservées, commandes sérialisées |
| Cookies/session | Nouveau navigateur et nouvelle connexion à chaque appel ; aucun état restauré dans `withSession` | État chiffré pour la collecte, mais `login/start` part toujours à vide | Reprise de l’état compatible ; état intermédiaire et état validé séparés |
| Stockages | Vie du navigateur de la collecte | Cookies et localStorage | Cookies, localStorage, IndexedDB et sessionStorage Domadoo, chiffrés |
| Navigation | `goto(affiliation)`, puis soumission réelle ; aucune liste réseau dans ce code | Liste fixe d’hôtes et de navigations ; POST authentification/vérification seulement en mode humain | Politique conservée, historique classé des réponses/redirections et blocages |
| Délais | `goto`/actions par défaut Playwright ; attend `#my_affiliate_link` 60 s | Navigation 30 s, actions 15 s ; fenêtre 15 min ; ferme sur erreur de navigation initiale | Lancement borné à 20 s, navigation 30 s, appel initial 60 s ; actions 15 s et fenêtre 15 min ; timeout affiché sans détruire la page, aucune relance de défi automatique |
| Succès | Présence `#my_affiliate_link` | Résumé affilié sur l’origine/chemin attendus, sans challenge | Même preuve de succès ; aucun clic accepté après reconnaissance |
| Erreurs | Message groupant identifiants/protection/page modifiée | Message générique et indicateur challenge | Étapes distinctes, HTTP, navigateur, reprise, navigation, Ray ID si fourni ; aucun texte privé du formulaire |

Le contrôle du formulaire confirme que sa destination POST actuelle est autorisée
par LinKs. Le retour **après** authentification réelle reste à observer : un autre
chemin ou une protection supplémentaire sera signalé, sans élargissement automatique
des autorisations. Le routage Playwright n’est pas un pare-feu réseau ; notamment,
les redirections HTTP ne déclenchent pas systématiquement un nouveau handler.
Les diagnostics enregistrent leurs catégories sans recopier les URLs sensibles.

## Rôle de la furtivité

Creator Studio charge `puppeteer-extra-plugin-stealth` et désactive son remplacement
du user-agent. Ce module vise à modifier des indices d’automatisation ; sa présence
ne démontre pas qu’il est responsable du succès observé. Son propre projet décrit
une compatibilité et une optimisation principalement Chromium : l’effet exact de
cette combinaison Firefox n’a pas été mesuré. Aucun essai de dissimulation,
résolution de CAPTCHA, rotation de proxy ou rejeu externe de jeton n’a été réalisé.

Références : [playwright-extra](https://github.com/berstend/puppeteer-extra/tree/master/packages/playwright-extra#plugins),
[navigateurs Cloudflare](https://developers.cloudflare.com/cloudflare-challenges/reference/supported-browsers/).
Cloudflare ne garantit pas la résolution de ses challenges dans Playwright.

## Défauts de code corrigés et portée

- Une réouverture jetait l’état déjà enregistré. Elle restaure maintenant l’état
  compatible et reprend un checkpoint chiffré récent ; un échec ne remplace pas
  la session validée ni le dernier relevé financier.
- Le rafraîchissement d’image et les commandes pouvaient se chevaucher, recevoir
  une réponse « navigateur occupé » et fermer la fenêtre. La file de commandes
  évite cette concurrence et ignore les réponses d’une ancienne fenêtre.
- « Vérifier » pouvait recharger un formulaire en cours de saisie. Le formulaire,
  la MFA et le challenge sont maintenant inspectés sans rechargement.
- Un timeout de navigation détruisait la fenêtre initiale. La page reste visible
  avec son diagnostic, et le lancement du navigateur est distingué de l’accès HTTP.
- Les erreurs de collecte sur challenge ne sont plus présentées comme preuve
  d’une session expirée. Une page inconnue ou un refus HTTP reste une erreur
  distincte ; l’historique financier n’est jamais remis à zéro.

La session persistante est un état d’authentification chiffré, pas un profil Firefox
complet. Elle ne garantit ni la durée de validité des cookies ni l’acceptation du
portail lors d’une collecte ultérieure. Les versions antérieures sont lisibles
avec Chromium ; un passage à Firefox demande une connexion humaine initiale.

## Validation et exploitation

Les tests utilisent des valeurs synthétiques, sans compte réel : soumission
humaine autorisée, POST automatique refusé, redirections observables, challenge
sans rechargement, HTTP 403 distinct, formulaire/MFA, session chiffrée après
redémarrage, checkpoint, promotion et déconnexion, commandes UI concurrentes,
diagnostic sans secrets et affichage mobile/clair/sombre.

L’image installe Firefox via la CLI de la version Playwright verrouillée, avec
ses dépendances Debian. Les contrôles natifs AMD64 et ARM64 doivent valider son
lancement, le rendu et une reprise chiffrée, avec UID 101, système en lecture seule,
capabilities supprimées, `init: true`, `/tmp` noexec de 512 Mo et `/data` inchangé.
Références : [navigateurs Playwright](https://playwright.dev/docs/browsers),
[authentification et stockages](https://playwright.dev/docs/auth).

Après déploiement par l’administrateur : ouvrir la connexion, confirmer l’arrivée
au formulaire Firefox, s’authentifier personnellement, vérifier la reconnaissance
de l’espace affilié, puis lancer une collecte et comparer ses chiffres. Tester
ensuite une reprise après redémarrage. Aucun accès au VPS n’est nécessaire pour
développer ou publier ; aucun déploiement n’est effectué par l’agent.

Si le blocage persiste : copier **uniquement le diagnostic de connexion** depuis
la fenêtre LinKs. Il fournit heure UTC, version navigateur, reprise, étape, HTTP,
redirections classées, blocages classés et éventuel Ray ID. Préciser si le formulaire
est apparu et si le blocage précède ou suit l’envoi manuel. Ne pas transmettre de
mot de passe, cookie, fichier `.session`, clé, HAR ou capture contenant des données
personnelles. En cas de `security_check`, arrêter les essais et demander à Domadoo
la vérification du Ray ID/heure ou un accès officiellement autorisé. Aucun succès
de connexion en production n’est annoncé sans ce test réel.
