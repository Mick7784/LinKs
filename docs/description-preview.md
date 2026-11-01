# Référence de l’aperçu des modèles YouTube

Observation du 1er novembre 2026, Chrome ordinateur, fenêtre de 1440 × 900 pixels CSS, session temporaire non connectée, page de lecture classique : https://www.youtube.com/watch?v=jNQXAC9IVRw.

Mesures de styles calculés : `ytd-watch-metadata #description` = 996 px ; `#description-inline-expander` = 972 px ; police Roboto/Arial/sans-serif, taille 14 px, interligne 20 px. La différence de 24 px correspond à 12 px de marge intérieure de chaque côté. Le bloc observé était replié. Une seconde tentative de mesure dépliée à 1280 px a été empêchée par une superposition YouTube ; aucune dimension dépliée à 1280 px n’est revendiquée.

LinKs retient **996 px de bloc / 972 px de texte** comme référence de travail pour son aperçu intégral. Ce choix est une référence mesurée, pas une largeur officielle universelle. La largeur réelle dépend notamment de la fenêtre, du mode cinéma, du zoom, de la connexion et des variantes de présentation YouTube. L’aperçu intégral extrapole la typographie mesurée à tout le texte ; il ne reproduit pas le bouton « afficher plus » ni les métadonnées de la vidéo.

Les colonnes côte à côte demandent au moins 1462 px disponibles dans Descriptions : 400 px pour les champs, 24 px d’espace, 1038 px pour l’aperçu avec son cadre. Sinon, elles s’empilent, alignées à gauche ; les formulaires restent limités à 720 px. Sur petit écran, l’aperçu rétrécit sans débordement : les coupures de lignes changent donc naturellement.

Roboto normal 400 (sous-ensemble latin, incluant les caractères français courants) est embarqué localement ; aucun appel à Google Fonts n’est fait par l’application. Source : https://fonts.googleapis.com/css2?family=Roboto:wght@400&display=swap ; fichier : https://fonts.gstatic.com/s/roboto/v51/KFOMCnqEu92Fr1ME7kSn66aGLdTylUAMQXC89YmC2DPNWubEbVmUiAo.woff2. Licence SIL OFL jointe à la police, issue de https://github.com/google/fonts/blob/main/ofl/roboto/OFL.txt. Les autres glyphes et emojis dépendent des polices de secours du système.

Le texte renvoyé par la prévisualisation est conservé caractère pour caractère via des nœuds texte : espaces, lignes vides, Unicode, emojis et URL. Les URL HTTP(S) sont simplement colorées, sans raccourcissement, navigation ni réécriture. Les retours automatiques sont visuels seulement. YouTube peut appliquer ses propres enrichissements, raccourcir des URL ou afficher des cartes : ces transformations ne sont pas simulées afin de préserver le contenu exact. Les descriptions enregistrées, brouillons et calculs de génération ne sont pas modifiés.
