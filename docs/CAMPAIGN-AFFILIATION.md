# Affiliation automatique des campagnes — étape 4

Cette étape prolonge la PR #50 sur sa branche existante, après les étapes 1 à 3 validées. Elle utilise les partenaires existants de **Liens suivis**. Aucun catalogue, code affilié ou calcul de destination n’est dupliqué dans le navigateur.

## Moteur partagé

`affiliate_partners.resolve_destination` calcule désormais la destination pour les liens suivis et les campagnes. Les deux parcours utilisent les mêmes fonctions de détection de domaine, substitution des modèles, validation des destinations et contrôle des aperçus. Les partenaires Domadoo, Reolink, Sanyipace et les partenaires personnalisés restent dans `affiliate_partners` avec leurs règles actuelles.

La détection conserve les limites de domaine, les sous-domaines et la règle du domaine le plus précis. Une correspondance ambiguë demande un choix manuel. Les modèles existants utilisant `{url}` et `{code}` restent pris en charge.

Pour les modèles qui ajoutent des paramètres (`{url}?…` ou `{url}&…`), le moteur :

- utilise le bon séparateur avec ou sans requête existante ;
- conserve les autres paramètres, y compris les valeurs répétées, encodages et signes `+` ;
- remplace les paramètres définis par le modèle au lieu d’empiler des codes identiques ;
- place les paramètres avant le fragment `#`, conservé sauf remplacement explicite par le modèle.

Les codes placés dans une valeur de paramètre sont encodés comme données. Une URL imbriquée dans un paramètre de modèle personnalisé conserve ses `?`, `&`, `%` et `#` par encodage. Un fragment défini par le modèle remplace le fragment existant. La substitution reste en une seule passe : des accolades contenues dans l’URL ou le code ne deviennent pas de nouvelles variables.

L’édition et le recalcul repartent de l’origine enregistrée, même si un client renvoie l’URL finale. Les enveloppes personnalisées déjà appliquées avec le même modèle et le même code sont reconnues lorsqu’elles contiennent une URL imbriquée, afin d’éviter un second enveloppement.

## Formulaire et conservation des destinations

Le formulaire de campagne propose :

- la détection automatique pour une nouvelle campagne ;
- le choix manuel d’un partenaire ou **Aucun** ;
- **Détecter depuis l’URL** pour relancer la détection et **Recalculer l’URL finale** pour appliquer les règles actuelles ;
- une URL finale actualisée et cliquable dans un nouvel onglet, sans accès à la fenêtre d’origine.

Pendant une édition, un choix manuel, y compris Aucun, reste prioritaire sur la détection automatique. À l’ouverture d’une fiche existante, son choix et sa destination sont conservés ; une modification explicite de son URL relance la détection tant qu’aucun choix manuel n’a été fait dans cette édition. **Aucun n’ajoute aucun code** : si l’URL fournie contenait déjà un code, elle est conservée telle quelle. Le moteur ne devine pas quels paramètres d’origine il faudrait supprimer lors du changement de partenaire ; il remplace uniquement les paramètres du modèle sélectionné.

Une campagne historique s’ouvre avec sa destination actuelle et sans affiliation déduite rétroactivement. Modifier uniquement le titre, la description, les dates ou le visuel ne recalcule pas sa destination. Une modification des règles du partenaire ne modifie pas non plus les destinations déjà enregistrées. Le changement d’origine, le choix d’un partenaire ou un recalcul explicite prépare une nouvelle URL ; le remplacement de la destination existante demande confirmation, car les liens déjà partagés utiliseront cette nouvelle destination.

Les réponses tardives d’aperçus précédents sont ignorées. Le serveur recalcule sous transaction avant l’enregistrement et exige le même aperçu, la même destination précédente et la confirmation du remplacement. Une modification concurrente des règles ou de la destination invalide un aperçu devenu périmé.

## Données et API

Une table additive `campaign_partners` conserve `campaign_id`, `partner_id` (nul pour Aucun), `original_url` et `final_url`. `content_blocks.url` reste la destination finale utilisée par la page publique et toutes les redirections existantes. Les deux écritures partagent la transaction existante. Aucun identifiant, compteur, type historique, image ou jeton n’est remplacé.

La table est vide à la migration : aucune campagne historique n’est réécrite. Les partenaires associés à des campagnes sont protégés contre la suppression, comme ceux associés aux liens suivis. Les doublons en brouillon conservent la provenance de leur destination, sans copier de statistiques.

`POST /api/content/preview`, réservé à l’administration, accepte `id` facultatif, `url` d’origine, `partner_id`, `detect` et `apply_partner`. Il retourne notamment `url` finale, `original_url`, `partner_id`, `previous_url`, `changed`, `duplicates` et `duplicate_confirmation_required`. Cet aperçu est sans mutation, y compris sans écriture du secours public.

Le parcours d’affiliation sur les routes de création/modification de contenu transmet également `expected_url`, `previous_url`, `confirm_destination` et, si nécessaire, `allow_duplicate` avec les `duplicate_ids` triés (`campaign:…` ou `tracked:…`). Les anciennes requêtes sans protocole d’affiliation continuent à fournir une destination explicite. Un aller-retour GET/PUT qui renvoie les nouvelles métadonnées sans demander d’affiliation ne déclenche aucun recalcul. Une modification explicite de destination par cette ancienne API retire une provenance qui ne correspondrait plus à l’URL enregistrée.

Les sauvegardes incluent la nouvelle association ; une ancienne sauvegarde sans cette table conserve les associations présentes. La restauration reste conservatrice sur la provenance et la dernière destination des campagnes déjà associées, et conserve les URL partagées et leurs compteurs.

## Doublons et réutilisation

La recherche utilise le comparateur de destinations existant de `tracked_links`, appliqué à l’URL finale. Elle inclut les campagnes et les liens suivis, y compris leurs archives. Les différences significatives de paramètres ou de fragments ne sont pas fusionnées.

Le formulaire propose de réutiliser une campagne active en ouvrant la même fiche, ou de consulter une campagne archivée dans Archives, où ses liens partagés restent accessibles. Pour un lien suivi, il ouvre le dialogue existant de réutilisation de ses sources et URL courtes. Aucun compteur n’est copié, fusionné ou remis à zéro. Une nouvelle campagne avec une destination identique reste possible après confirmation explicite du doublon ; les doublons historiques inchangés restent éditables.

La provenance d’affiliation est une donnée appartenant à la campagne, pas une publication externe. Elle est supprimée en cascade uniquement lorsqu’une ponctuelle est réellement sans activité et sans autre référence selon l’étape 2. Les compteurs, liens courts, redirections et autres références nécessaires continuent d’imposer l’archivage.

## Validation et limites du chantier

Les tests ciblés couvrent les trois partenaires intégrés, les domaines trompeurs, le choix manuel et Aucun, le changement de partenaire, les modèles personnalisés, les URL complexes, les codes déjà présents, le recalcul, les aperçus périmés, les doublons et réutilisations, les sauvegardes et les campagnes historiques. Les tests navigateur exercent les choix réels, l’aperçu cliquable, l’annulation d’un remplacement, les mêmes URL courtes et compteurs, ainsi que les réutilisations de campagnes et de liens suivis aux formats ordinateur/mobile.

Les routes et contrats de PulSe restent inchangés : ils utilisent la destination finale enregistrée dans `content_blocks`. Aucun changement du dépôt PulSe, aucune fusion, release, publication d’image ou intervention VPS. La version de production reste V1.324.
