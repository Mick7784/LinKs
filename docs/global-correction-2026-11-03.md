# Correctif global du 3 novembre 2026

Base : V1.4.10, commit 1aa234481d769ad535d52b1b30c0f1f65624d68c.
Ce document décrit le correctif local ; il ne certifie pas un déploiement.

## Changements

| Audit | Correction |
|---|---|
| BUG-01 | Réponse de mutation différée jusqu'à sortie des transactions ; une erreur remplace le succès en attente. |
| BUG-02 | Plafond de restauration propre aux règles de sources, compatible avec leur maximum valide ; validation métier conservée. |
| BUG-03 | Filtre portail tous les Tracking IDs vérifié avant génération, preuve exigée par le serveur et rapprochement des trois vues. |
| BUG-04 | La ventilation Tracking IDs remplace uniquement les cellules de même couverture, tag et indicateur. |
| BUG-05 | Chevauchement CSV calculé sur les métriques présentes ; corrections partielles sans perte via ZIP. |
| BUG-06 | Intention de rendu conservée si un polling devance la navigation ; import actualisé sans fermer son bilan. |
| BUG-07 | Identité métier Amazon/Domadoo explicite dans les sous-sections personnalisées, indépendante de leur UUID. Modèles historiques compatibles. |
| BUG-08 | Partenaire capturé après résolution du doublon effectif. |
| BUG-09 | Contradiction de référence entre titre HTML crédible et slug signalée comme ambiguë. |
| BUG-10 | Même normalisation d'alias pour les compteurs de campagnes et les autres statistiques. |
| BUG-11 | Stories PulSe limitées aux sources Instagram ; total toutes sources conservé. |
| BUG-12 | Setup clos rejeté avant limitation ; budgets setup/login séparés, limites par client et plafond global. Aucun en-tête de proxy arbitraire utilisé. |
| DOC-01 | Documentation Amazon actuelle : ZIP automatique, portail manuel expérimental, quotidien désactivé. |
| TEST-01 | Test campagne attend la fin réelle du chargement, y compris le chargement préalable des liens. |
| REC-01 | Décision d'import automatique isolée dans amazon_imports.py ; contrat de réponse centralisé. Pas de refonte générale. |
| REC-02 | Playwright de test aligné sur la version déclarée du runtime ; Pillow de test fixé ; inventaire des versions et paquets intégré à l'image. |

## ZIP automatique

Choisir le ZIP → Envoyer → bilan. Aucun formulaire de couverture dans le parcours
normal. Les faits manquants ne sont pas inventés. Un ZIP sûr mais indécidable est
conservé dans les snapshots, sous amazon_pending, sans contribuer aux statistiques.
L'original peut être téléchargé et survit à la sauvegarde/restauration.

La résolution conserve les indicateurs et jours non remplacés. Elle refuse de
proratiser des totaux agrégés ou de cumuler un périmètre global et son sous-ensemble.
Les vues complémentaires importées séparément restent hors des totaux quand une
référence plus prioritaire couvre déjà la même période. Les empreintes empêchent
les réimports historiques, y compris après renommage ou réemballage.

Les limites ZIP, contrôle de chemins, formats et quotas globaux de sauvegarde restent
applicables. Aucun fichier non reconnu n'est interprété comme un rapport financier.
La mise à niveau ne reclassifie pas les données financières existantes.

## Vérification

- Régressions métier : global_audit_test.py, amazon_automatic_test.py.
- Concurrence UI : affiliation-loading.test.cjs.
- Parcours ZIP réel sur serveur jetable : amazon-zip-browser-test.cjs.
- Suites existantes des transactions, sauvegardes, statistiques, descriptions,
  titres, Amazon, PulSe et migrations.

Les tests utilisent des données synthétiques. Les droits et exports d'un compte
réel, les sélecteurs du portail actuel et l'image Linux finale doivent être recettés
sur un environnement autorisé avant déploiement. L'inventaire runtime-versions.json
ne constitue pas à lui seul un scan de vulnérabilités ou une certification de l'image.
Les images de base et paquets OS restent à résoudre par leur digest/version lors de
la recette Linux ; aucun digest de production n'est inventé ici.

Résultat local : 468 tests Python dans 44 modules, 71 tests JavaScript/collecteur,
7 parcours navigateur ciblés réussis. Analyse syntaxique Python et 109 fichiers
JavaScript réussie. Les tests Python de release/commit/push sont exclus. Chrome
local et Playwright 1.62.1 ont été utilisés ; la CI configurée vise la version 1.64.1
déclarée par le dépôt et doit être exécutée séparément avant publication. Docker,
Firefox fournisseur, ARM64 et comptes réels n'ont pas été validés dans cette session.

Après la suite globale, 69 tests Amazon/consolidation ont été rejoués avec succès,
dont un cas supplémentaire de ventilation partielle d'un total non daté. Ces 69 cas
recouvrent les suites précédentes et ne s'ajoutent pas intégralement aux 468.
