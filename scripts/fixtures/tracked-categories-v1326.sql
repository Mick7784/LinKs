-- Synthetic historical baseline, frozen from LinKs eacfe4c (V1.326).
-- Tests only: contains categories intentionally; never load into a live instance.
-- No category removal or migration is implemented by this fixture.
BEGIN TRANSACTION;
CREATE TABLE admin_accounts(id INTEGER PRIMARY KEY CHECK(id=1),username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL);
CREATE TABLE admin_sessions(token_hash TEXT PRIMARY KEY,csrf TEXT NOT NULL,expires INTEGER NOT NULL);
CREATE TABLE affiliate_partners(
        id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
        code TEXT NOT NULL, domains TEXT NOT NULL, template TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO "affiliate_partners" VALUES('77a0505754665a0da4f806609c449cf2','Domadoo','117','["domadoo.fr"]','{url}?domid={code}','2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
INSERT INTO "affiliate_partners" VALUES('85b232baa7cf52d094a43be3839e3e59','Reolink','CURRENT1404','["reolink.com"]','{url}?aff={code}','2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
INSERT INTO "affiliate_partners" VALUES('0ab9544b5b7f5ffd991b132656c9ccd9','Sanyipace','DomotiK','["sanyipacetoilet.com"]','{url}?ref={code}','2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
CREATE TABLE auth_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE campaign_partners(
        campaign_id TEXT PRIMARY KEY REFERENCES content_blocks(id) ON DELETE CASCADE,
        partner_id TEXT REFERENCES affiliate_partners(id) ON DELETE RESTRICT,
        original_url TEXT NOT NULL, final_url TEXT NOT NULL);
INSERT INTO "campaign_partners" VALUES('30000000-0000-0000-0000-000000000001','85b232baa7cf52d094a43be3839e3e59','https://partner.example/active#offre','https://partner.example/active?ref=117#offre');
CREATE TABLE content_blocks(
          id TEXT PRIMARY KEY,type TEXT NOT NULL,internal_name TEXT NOT NULL,title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',url TEXT NOT NULL,icon TEXT NOT NULL DEFAULT 'website',
          image TEXT NOT NULL DEFAULT '',badge TEXT NOT NULL DEFAULT '',cta TEXT NOT NULL DEFAULT '',
          position INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1,draft INTEGER NOT NULL DEFAULT 0,
          start_at TEXT,end_at TEXT,archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
          priority TEXT NOT NULL DEFAULT 'normal', promo_code TEXT NOT NULL DEFAULT '', retired INTEGER NOT NULL DEFAULT 0 CHECK(retired IN (0,1)));
INSERT INTO "content_blocks" VALUES('30000000-0000-0000-0000-000000000001','promo','Campagne active','Titre public active','Description conservée','https://partner.example/active?ref=117#offre','website','','','',0,1,0,'2026-10-01T00:00:00Z','2026-11-30T23:00:00Z',0,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z','normal','ETE10',0);
INSERT INTO "content_blocks" VALUES('30000000-0000-0000-0000-000000000002','promo','Campagne archived','Titre public archived','Description conservée','https://partner.example/archived?ref=117#offre','website','','','',1,1,0,'2026-10-01T00:00:00Z','2026-11-30T23:00:00Z',1,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z','normal','ETE10',1);
INSERT INTO "content_blocks" VALUES('30000000-0000-0000-0000-000000000003','classic','Campagne classic','Titre public classic','Description conservée','https://partner.example/classic?ref=117#offre','website','','','',2,1,0,NULL,NULL,0,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z','normal','',0);
CREATE TABLE counts(day TEXT,source TEXT,kind TEXT,link TEXT,total INTEGER NOT NULL,PRIMARY KEY(day,source,kind,link));
INSERT INTO "counts" VALUES('2001-01-01','tracked:00000000000000000000000000000001','tracked','tracked:tk_0000000000000001:09',11);
INSERT INTO "counts" VALUES('2026-10-29','tracked:00000000000000000000000000000001','tracked','tracked:tk_0000000000000001:12',7);
INSERT INTO "counts" VALUES('2026-10-28','youtube','view','',23);
INSERT INTO "counts" VALUES('2026-10-29','youtube','click','block:30000000-0000-0000-0000-000000000003',4);
INSERT INTO "counts" VALUES('2026-10-29','youtube','click','block:30000000-0000-0000-0000-000000000001',6);
INSERT INTO "counts" VALUES('2026-10-29','youtube','impression','block:30000000-0000-0000-0000-000000000001',50);
INSERT INTO "counts" VALUES('2026-10-29','youtube','promo_code_copy','{"id": "30000000-0000-0000-0000-000000000001", "name": "Offre historique", "code": "OLD10", "timestamp": "2026-10-29T10:00:00Z"}',2);
INSERT INTO "counts" VALUES('2026-10-29','instagram','story','story:st_000000000000000f:12',5);
CREATE TABLE footer_quotes(id TEXT PRIMARY KEY,text TEXT NOT NULL UNIQUE,active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),created_at TEXT NOT NULL);
INSERT INTO "footer_quotes" VALUES('50000000000000000000000000000001','Une citation à conserver.',1,'2026-10-01T08:00:00Z');
CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
INSERT INTO "settings" VALUES('app.config_schema_version','1');
INSERT INTO "settings" VALUES('app.setup_completed','true');
INSERT INTO "settings" VALUES('auth.mode','external');
INSERT INTO "settings" VALUES('profile.name','Test Creator');
INSERT INTO "settings" VALUES('profile.tagline','Une page de test');
INSERT INTO "settings" VALUES('profile.description','Liens de test');
INSERT INTO "settings" VALUES('profile.logo','');
INSERT INTO "settings" VALUES('profile.avatar','');
INSERT INTO "settings" VALUES('footer.owner','Test Creator');
INSERT INTO "settings" VALUES('app.timezone','Europe/Paris');
INSERT INTO "settings" VALUES('site.url','https://links.example');
INSERT INTO "settings" VALUES('analytics.enabled','true');
INSERT INTO "settings" VALUES('video.enabled','true');
INSERT INTO "settings" VALUES('analytics.source_rules','[]');
INSERT INTO "settings" VALUES('affiliate.sanyipace_domain_v1','1');
INSERT INTO "settings" VALUES('app.instance_id','0000000000000000000000000000000b');
INSERT INTO "settings" VALUES('appearance.themes','[]');
INSERT INTO "settings" VALUES('appearance.active','links-original');
INSERT INTO "settings" VALUES('app.version','V1.326');
INSERT INTO "settings" VALUES('app.release_id','bundled:V1.326');
INSERT INTO "settings" VALUES('analytics.metric_aliases','{"Ancien lien public": "block:30000000-0000-0000-0000-000000000003"}');
INSERT INTO "settings" VALUES('content.initialized','1');
CREATE TABLE short_aliases (
        code TEXT PRIMARY KEY,
        target_token TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1))
    );
INSERT INTO "short_aliases" VALUES('000000002','tk_0000000000000001','tracked:00000000000000000000000000000001','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('000000004','tk_0000000000000003','tracked:00000000000000000000000000000009','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('000000006','tk_0000000000000005','tracked:0000000000000000000000000000000c','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('000000008','tk_0000000000000007','tracked:00000000000000000000000000000003','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('00000000a','tk_0000000000000009','tracked:0000000000000000000000000000000c','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('00000000c','tk_000000000000000b','tracked:0000000000000000000000000000000d','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('00000000e','tk_000000000000000d','tracked:0000000000000000000000000000000a','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('000000010','st_000000000000000f','instagram','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('000000011','st_000000000000000f','youtube','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('000000013','st_0000000000000012','instagram','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('000000014','st_0000000000000012','youtube','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('000000016','tk_0000000000000015','tracked:00000000000000000000000000000009','2026-10-01T08:00:00Z',0);
INSERT INTO "short_aliases" VALUES('Revoked01','tk_0000000000000001','tracked:00000000000000000000000000000001','2026-10-01T08:00:00Z',1);
CREATE TABLE story_links(
          token TEXT PRIMARY KEY,promotion_id TEXT NOT NULL UNIQUE,name TEXT NOT NULL,
          created_at TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0);
INSERT INTO "story_links" VALUES('st_000000000000000f','30000000-0000-0000-0000-000000000001','Campagne active','2026-10-01T08:00:00Z',0);
INSERT INTO "story_links" VALUES('st_0000000000000012','30000000-0000-0000-0000-000000000002','Campagne archived','2026-10-01T08:00:00Z',0);
CREATE TABLE top_buttons(
          id TEXT PRIMARY KEY,icon TEXT NOT NULL,label TEXT NOT NULL,url TEXT NOT NULL,position INTEGER NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL, custom_icon TEXT NOT NULL DEFAULT '', retired INTEGER NOT NULL DEFAULT 0 CHECK(retired IN (0,1)));
INSERT INTO "top_buttons" VALUES('40000000000000000000000000000001','mail','Contact','mailto:contact@example.org',0,1,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z','',0);
CREATE TABLE tracked_link_partners(
        link_id TEXT PRIMARY KEY REFERENCES tracked_links(id),
        partner_id TEXT NOT NULL REFERENCES affiliate_partners(id) ON DELETE RESTRICT, original_url TEXT NOT NULL DEFAULT '');
INSERT INTO "tracked_link_partners" VALUES('20000000000000000000000000000001','85b232baa7cf52d094a43be3839e3e59','https://shop.reolink.com/Produit?variant=a%2Bb&variant=c+d#d%C3%A9tails');
CREATE TABLE tracked_links (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
        archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO "tracked_links" VALUES('20000000000000000000000000000001','Caméra été — façade','https://shop.reolink.com/Produit?variant=a%2Bb&variant=c+d&aff=1404#d%C3%A9tails','Éclairage / été','Référence durable : été, + et %2B.',0,1,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
INSERT INTO "tracked_links" VALUES('20000000000000000000000000000002','Lien affilié direct','https://amzn.to/exemple?tag=historique-21#offre','','Référence durable : été, + et %2B.',0,1,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
INSERT INTO "tracked_links" VALUES('20000000000000000000000000000003','Doublon confirmé','https://shop.reolink.com/Produit?variant=a%2Bb&variant=c+d&aff=1404#d%C3%A9tails','Produit','Référence durable : été, + et %2B.',0,1,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
INSERT INTO "tracked_links" VALUES('20000000000000000000000000000004','Ancien équipement','https://shop.example/archive?ref=ancienne#fiche','Archives','Référence durable : été, + et %2B.',1,1,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
INSERT INTO "tracked_links" VALUES('20000000000000000000000000000005','Lien suspendu','https://shop.example/suspendu?ref=fixe','Accessoire','Référence durable : été, + et %2B.',0,0,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
INSERT INTO "tracked_links" VALUES('dbd29cffcd1a536ea699c99ee087ea31','Vidéo historique — domotique','https://www.youtube.com/watch?v=abcdefghijk','YouTube','Créé depuis PulSe pour une vidéo précise',0,1,'2026-10-01T08:00:00Z','2026-10-02T09:30:00Z');
CREATE TABLE tracked_tokens (
        token TEXT PRIMARY KEY, link_id TEXT NOT NULL REFERENCES tracked_links(id),
        source_id TEXT NOT NULL REFERENCES tracking_sources(id),
        click_total INTEGER NOT NULL DEFAULT 0 CHECK(click_total >= 0),
        created_at TEXT NOT NULL, UNIQUE(link_id,source_id));
INSERT INTO "tracked_tokens" VALUES('tk_0000000000000001','20000000000000000000000000000001','00000000000000000000000000000001',1099511627793,'2026-10-01T08:00:00Z');
INSERT INTO "tracked_tokens" VALUES('tk_0000000000000003','20000000000000000000000000000001','00000000000000000000000000000009',2,'2026-10-01T08:00:00Z');
INSERT INTO "tracked_tokens" VALUES('tk_0000000000000005','20000000000000000000000000000001','0000000000000000000000000000000c',0,'2026-10-01T08:00:00Z');
INSERT INTO "tracked_tokens" VALUES('tk_0000000000000007','20000000000000000000000000000002','00000000000000000000000000000003',0,'2026-10-01T08:00:00Z');
INSERT INTO "tracked_tokens" VALUES('tk_0000000000000009','20000000000000000000000000000003','0000000000000000000000000000000c',17,'2026-10-01T08:00:00Z');
INSERT INTO "tracked_tokens" VALUES('tk_000000000000000b','20000000000000000000000000000004','0000000000000000000000000000000d',0,'2026-10-01T08:00:00Z');
INSERT INTO "tracked_tokens" VALUES('tk_000000000000000d','20000000000000000000000000000005','0000000000000000000000000000000a',0,'2026-10-01T08:00:00Z');
INSERT INTO "tracked_tokens" VALUES('tk_0000000000000015','dbd29cffcd1a536ea699c99ee087ea31','00000000000000000000000000000009',3,'2026-10-01T08:00:00Z');
CREATE TABLE tracking_source_keys(key TEXT PRIMARY KEY,source_id TEXT REFERENCES tracking_sources(id));
INSERT INTO "tracking_source_keys" VALUES('instagram','00000000000000000000000000000001');
INSERT INTO "tracking_source_keys" VALUES('youtube','00000000000000000000000000000003');
INSERT INTO "tracking_source_keys" VALUES('facebook','00000000000000000000000000000005');
INSERT INTO "tracking_source_keys" VALUES('tiktok','00000000000000000000000000000006');
INSERT INTO "tracking_source_keys" VALUES('discord','00000000000000000000000000000007');
INSERT INTO "tracking_source_keys" VALUES('instagram-story','00000000000000000000000000000008');
INSERT INTO "tracking_source_keys" VALUES('shared-unknown','00000000000000000000000000000008');
INSERT INTO "tracking_source_keys" VALUES('platform:instagram','00000000000000000000000000000009');
INSERT INTO "tracking_source_keys" VALUES('platform:youtube','0000000000000000000000000000000a');
INSERT INTO "tracking_source_keys" VALUES('platform:facebook','00000000000000000000000000000005');
INSERT INTO "tracking_source_keys" VALUES('platform:tiktok','00000000000000000000000000000006');
INSERT INTO "tracking_source_keys" VALUES('platform:discord','00000000000000000000000000000007');
INSERT INTO "tracking_source_keys" VALUES('platform:other','00000000000000000000000000000008');
CREATE TABLE tracking_sources (
        id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
        story_click_total INTEGER NOT NULL DEFAULT 0 CHECK(story_click_total >= 0),
        created_at TEXT NOT NULL);
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000001','Anciennes Stories Instagram',1,13,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000002','Instagram Bio',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000003','YouTube Post',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000004','YouTube Description',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000005','Facebook',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000006','TikTok',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000007','Discord',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000008','Autre / Direct',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('00000000000000000000000000000009','Instagram renommé',1,5,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('0000000000000000000000000000000a','YouTube',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('0000000000000000000000000000000c','Newsletter indépendante',1,0,'2026-10-01T08:00:00Z');
INSERT INTO "tracking_sources" VALUES('0000000000000000000000000000000d','Source archivée publiée',0,0,'2026-10-01T08:00:00Z');
CREATE TABLE upload_trash(name TEXT PRIMARY KEY, orphaned_at REAL NOT NULL);
CREATE TABLE user_files(name TEXT PRIMARY KEY, created_at REAL NOT NULL, category TEXT NOT NULL DEFAULT 'other');
CREATE INDEX short_alias_lookup ON short_aliases(target_token,source,revoked);
COMMIT;
