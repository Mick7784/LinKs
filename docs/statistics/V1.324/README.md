# Comparaison visuelle — V1.323 → V1.324

Les captures proviennent de deux copies locales du dépôt (main V1.323 et branche de refonte), avec le même navigateur, la même base temporaire et le même fuseau Europe/Paris. Les noms et événements marqués « test » sont des fixtures de validation ; aucune donnée du VPS n’a été lue ou modifiée.

## Desktop : 1672 × 941 px

Cette largeur correspond à la maquette fournie. Le menu latéral existant est conservé. La composition reprend les trois niveaux de la référence : six KPI de 116 px de hauteur ; évolution et provenance côte à côte (ratio 1,6:1) ; détail quotidien, top liens et campagnes alignés dès le premier écran. La rangée centrale commence à environ 688 px ; les contrôles supplémentaires du rapport réel restent accessibles.

Les icônes occupent 46–50 px dans les KPI ; chiffres à 28 px et titres de panneaux à 17 px. Les séries et barres conservent les familles cyan (visites), bleu (clics), violet (suivis), rose (campagnes). Les provenances ont leur propre palette stable et l’inconnue reste neutre. L’anneau est agrandi, avec légende, nombres et activation clavier. Les doublons de total et aides sont retirés du premier niveau de lecture. Aucun glow, texture ou delta fictif.

| Thème | Avant | Après |
|---|---|---|
| Sombre | [V1.323](before-desktop-dark.png) | [V1.324](after-desktop-dark.png) |
| Clair | [V1.323](before-desktop-light.png) | [V1.324](after-desktop-light.png) |

## Mobile : 390 px, page entière

| Thème | Avant | Après |
|---|---|---|
| Sombre | [V1.323](before-390-dark.png) | [V1.324](after-390-dark.png) |
| Clair | [V1.323](before-390-light.png) | [V1.324](after-390-light.png) |

## Contrôles

- Aucun débordement horizontal de la page ni du conteneur statistique à 320, 390, 768, 1024, 1440 et 1920 px, en clair/sombre ; vérification supplémentaire à 1672 px. Aucun masquage global par `overflow-x:hidden` ajouté.
- Sur desktop, six KPI et trois panneaux d’action ; sur tablette, deux colonnes et campagnes sur la ligne suivante ; sur mobile, panneaux empilés et KPI en une ou deux colonnes.
- Logo identique au PNG officiel fourni : SHA-256 `2aed7e131718a5b4072c49e5efacc845f65769a90d150a8d91288b431434a25d`.
- Composants réutilisés : `StudioCharts`, `StudioCollection`, `StudioDailyReport`, `StudioSourcePlatforms`, `StudioPartnerReport`, état partagé des filtres et fiches existantes. Aucune dépendance ajoutée.
- Test navigateur existant adapté à la nouvelle composition : mêmes contrôles des métriques, filtres, historiques, provenances, partenaires, archives, pagination, fiches et retours de focus ; contrôle du volet de recherche, des familles de classements et de la rangée desktop. Les contrastes, le tactile, le clavier et les animations réduites restent contrôlés.
