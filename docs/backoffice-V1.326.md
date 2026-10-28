# V1.326 — Réorganisation du back-office

Base : main V1.325. Étape 1 uniquement, avant validation VERT / ROUGE.

- Campagnes : gestion, planning et aperçu de sélection déplacés dans une page dédiée, avec les composants V1.325.
- Liens permanents : gestion des liens classiques et classement existant dans une page dédiée.
- Page publique : accès conservé aux réglages de composition existants pendant la transition.
- Liens suivis : espace indépendant conservé.
- Archives : accès à la page commune depuis chaque nouvel espace ; restauration, historiques et redirections conservés.

Les listes réutilisent le rendu, les formulaires, les actions et les interactions de classement V1.325. Chaque contenu est édité dans une seule liste. Les raccourcis du tableau de bord ouvrent Campagnes ; Page publique propose des accès aux deux espaces de gestion. Le classement de chaque liste utilise l’API existante sans modifier les fiches de l’autre espace.

Aucun changement du rendu public, des API, du moteur de campagnes, de l’affiliation, de PulSe ni du stockage /data. Aucun éditeur visuel, aucune fusion, release ou intervention VPS dans ce chantier.

Validation : tests ciblés des parcours déplacés et contrôles GitHub existants.
