# Statistiques agrégées

La collecte est activable depuis les paramètres. Sa désactivation ne coupe ni l’administration, ni l’API de contenu, ni les redirections Story. Les anciens compteurs restent consultables.

## Événements

- `view` : affichage de la page.
- `click` : activation d’un lien public.
- `impression` : présentation d’une campagne.
- `story` : ouverture directe via un lien de campagne partagé (`/go/st_…`), distincte du clic depuis la page publique.
- `promo_code_copy` : copie réussie, séparée du clic d’offre.

Les liens /go/ existants conservent leur jeton et leur destination. Copier un lien pour Instagram ou YouTube ajoute simplement `?utm_source=instagram` ou `?utm_source=youtube` ; cette information est utilisée pour attribuer les nouvelles ouvertures. Les anciens événements `instagram-story` restent conservés sans réécriture : leur véritable origine ne peut pas être reconstruite. Les liens sans paramètre d'origine sont suivis sous `shared-unknown`.

Les ouvertures de liens partagés sont rattachées à la campagne associée lors du rapport sans dupliquer un événement `click`. Le dashboard distingue les clics de la page (pour le CTR page), les ouvertures de liens partagés et leur total par campagne. Les impressions correspondent uniquement à la page publique. Aucune modification rétroactive des comptes ni des URLs n'est nécessaire.

Les copies conservent le code réellement copié, l’identifiant, le nom de campagne et une tranche horaire UTC. L’historique ne dépend pas du code actuel. Le graphique principal conserve deux séries : visites et clics ; les copies sont présentées séparément.

## Sources et dates

Les sources génériques et règles d’instance utilisent le même moteur. `utm_source` est prioritaire sur le domaine référent. Les sources non reconnues sont regroupées. Les anciennes clés et correspondances de liens sont conservées après migration.

Les journées utilisent le fuseau configuré. Changer de fuseau ne recalcule pas l’historique. Les campagnes restent enregistrées sous forme d’instants UTC.

## Confidentialité

SQLite contient des compteurs agrégés, sans IP, cookie analytics, identifiant visiteur ou notion de personne unique. La provenance complète n’est pas conservée. Do Not Track et Global Privacy Control sont respectés. La rétention glissante est de 400 jours, appliquée lors de la collecte.

Les sessions administrateur sont distinctes des statistiques. Ces garanties ne décrivent pas les journaux HTTP de votre hébergement.

## Sauvegardes

Le format version 3 inclut compteurs, snapshots de copies, associations Story, citations et réglages. Les anciens formats restent compatibles. Voir [Installation](docs/INSTALL.md).
