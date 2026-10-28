# V1.326 — Réorganisation du back-office

Base : main V1.325. Étapes 1 et 2 sur une PR unique, avant validation VERT / ROUGE. Les contrôles GitHub de l’étape 1 (a0c6b7b) ont réussi avant le début de l’étape 2.

- Campagnes : gestion, planning et aperçu de sélection déplacés dans une page dédiée, avec les composants V1.325.
- Liens permanents : gestion des liens classiques et classement existant dans une page dédiée.
- Page publique : éditeur visuel d’organisation, utilisant le document, les composants, les styles et le thème publics réels. L’en-tête et le pied de page ne sont pas déplaçables.
- Liens suivis : espace indépendant conservé.
- Archives : accès à la page commune depuis chaque nouvel espace ; restauration, historiques et redirections conservés.

Les listes réutilisent le rendu, les formulaires, les actions et les interactions de classement V1.325. Chaque contenu est édité dans une seule liste. Les raccourcis du tableau de bord ouvrent Campagnes ; Page publique propose des accès aux deux espaces de gestion. Le classement de chaque liste utilise l’API existante sans modifier les fiches de l’autre espace.

L’éditeur conserve son brouillon côté navigateur jusqu’à Enregistrer. Annuler recharge l’organisation enregistrée ; naviguer vers une autre page de gestion conserve le brouillon. Les contenus actuellement invisibles restent gérés dans les bibliothèques ; leur section garde une position même lorsqu’elle est vide.

L’ordre public est enregistré dans SQLite sous `public.section_order`, séparément de l’ancien ordre administratif `admin.content_order`. Sans enregistrement explicite, l’ordre public historique (vidéo, campagnes, liens) reste identique. Les liens utilisent les positions de leurs fiches existantes ; aucune identité n’est remplacée. Un seul enregistrement transactionnel valide les deux ordres et refuse un brouillon devenu obsolète après une autre modification de classement ou de bibliothèque. La sauvegarde/restauration et le fallback public incluent l’ordre des sections.

La page publique applique uniquement l’ordre validé à ses composants existants. Aucun changement du moteur de campagnes, de l’affiliation, de PulSe ou du schéma de /data. Les aperçus n’émettent pas de statistiques. Aucune fusion, release ou intervention VPS dans ce chantier.

Validation : tests ciblés des parcours déplacés, du brouillon/annulation, du rendu réel, des gestes souris/tactiles/clavier, de l’enregistrement atomique, des conflits, du redémarrage et des sauvegardes. Captures ordinateur/mobile, clair/sombre. Les nouveaux tests rejoignent les contrôles GitHub existants.
