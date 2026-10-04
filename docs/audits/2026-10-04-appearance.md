# Validation — Apparence et publication

Base inspectée : `Mick7784/links`, branche `main`, HEAD `7e6e0d79c9712bb03b003d78d4589a783d54d05a`. Les 73 fichiers ont été récupérés par le connecteur GitHub authentifié et vérifiés par leur empreinte Git. La copie de travail reproduit le tree et le HEAD du dépôt privé ; aucun fork ni autre dépôt distant.

## Validation locale

- 63 tests Python : contenus/analytics (31), installation/authentification (11), thèmes (8), versions (8), notes de release (2), YouTube (3).
- 10 tests JavaScript : dates, calendrier, collecte des métriques et API vidéo.
- Neuf suites navigateur Chromium : installation, Stories, administration, identité/UI, calendrier, paramètres, contrôles ciblés, page publique et Apparence.
- Apparence : comparaison pixel à pixel de LinKs Original avec le CSS du HEAD initial, Desktop/Mobile ; données réelles du fixture, campagne et code promo ; brouillon/publication ; couleurs et contraste ; douze fonds ; bibliothèque/import/URL/retrait ; icônes ; CSS Expert/export/import ; responsive.
- SQLite : migration additive, redémarrage, trois thèmes maximum, protection d’Original, CRUD/activation/restauration, import sécurisé, images personnelles et sauvegarde/restauration v3.
- Versionnement : réservation persistante, relance sans double incrément, rejet d’un ancien run, jalons manuels et tags identiques à VERSION. Notes et changelog partagent le même texte.
- Génération de configuration réussie ; syntaxe des scripts et `git diff --check` contrôlées.

Les tests ont utilisé des bases temporaires. Sous Windows, un lanceur local collecte les connexions SQLite temporaires laissées ouvertes par les fixtures historiques avant leur suppression ; les assertions ne sont pas modifiées. Le contrôle des permissions POSIX de la clé YouTube s’applique sur Linux. Aucun contenu ou volume de production n’a été utilisé.

## Contrôles de production

Le build Docker, les smoke tests en conteneur, la publication AMD64/ARM64 et l’identité des manifests version/latest sont exécutés par le workflow GitHub. Leur résultat doit être vérifié sur le commit publié avant de considérer la release comme terminée.

Le dépôt ne décrit pas de cible de déploiement ou de connexion permettant de redémarrer l’instance. Publier une image n’est pas un déploiement ; le redémarrage et les contrôles post-déploiement nécessitent cette cible.
