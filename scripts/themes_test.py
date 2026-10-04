import base64, importlib.util, json, os, sqlite3, tempfile, unittest, uuid
from pathlib import Path
from unittest.mock import patch
import themes

class ThemeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.env=patch.dict(os.environ,{'ANALYTICS_DB':str(self.root/'db.sqlite'),'UPLOAD_DIR':str(self.root/'uploads'),'APP_RELEASE_VERSION':'','APP_RELEASE_ID':''});self.env.start()
  spec=importlib.util.spec_from_file_location('appearance_api',Path(__file__).with_name('analytics.py'));self.a=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.a);self.a.init()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def save(self,**data):
  with self.a.connection() as db:return themes.save(db,data,self.a.UPLOADS)
 def custom(self,name='Test',tokens=None):return {'id':str(uuid.uuid4()),'name':name,'author':'Test','tokens':tokens or {}}
 def test_migration_and_restart(self):
  with self.a.connection() as db:
   before=[dict(r) for r in db.execute('SELECT * FROM content_blocks')];db.execute("DELETE FROM settings WHERE key LIKE 'appearance.%'")
  self.a.init()
  with self.a.connection() as db:self.assertEqual(before,[dict(r) for r in db.execute('SELECT * FROM content_blocks')]);self.assertEqual(themes.public(db)['id'],themes.ORIGINAL)
  theme=self.custom(tokens={'--links-primary':'#abcdef'});self.save(theme=theme,publish=True);self.a.init()
  with self.a.connection() as db:self.assertEqual(themes.public(db),theme)
 def test_three_limit_crud_and_original(self):
  rows=[self.custom(str(i)) for i in range(3)]
  for row in rows:self.save(theme=row)
  with self.assertRaises(ValueError):self.save(theme=self.custom())
  with self.assertRaises(ValueError):self.save(action='duplicate',id=rows[0]['id'])
  rows[0]['name']='Renommé';self.save(theme=rows[0]);self.save(action='activate',id=rows[0]['id']);self.save(action='activate',id=themes.ORIGINAL)
  with self.a.connection() as db:self.assertEqual(len(themes.state(db)['items']),4)
  for action in ['delete','save']:
   with self.assertRaises(ValueError):self.save(action=action,id=themes.ORIGINAL,theme={'id':themes.ORIGINAL,'name':'Change','tokens':{}})
  self.save(action='delete',id=rows[0]['id']);self.save(action='duplicate',id=rows[1]['id'])
  self.save(action='activate',id=rows[2]['id']);self.save(action='delete',id=rows[2]['id'])
  with self.a.connection() as db:self.assertEqual(themes.public(db)['id'],themes.ORIGINAL)
 def test_draft_is_not_public(self):
  theme=self.custom(tokens={'--links-card-radius':25});self.save(theme=theme)
  self.assertEqual(self.a.public_config()['appearance']['id'],themes.ORIGINAL)
  self.save(theme=theme,publish=True);self.assertEqual(self.a.public_config()['appearance']['tokens']['--links-card-radius'],25)
 def test_typed_validation(self):
  for token,value in [('--links-card-radius',-1),('--links-card-radius',999),('--links-card-radius','20px'),('--links-primary','red;display:none'),('--links-page-image','url(javascript:alert(1))'),('--links-evil','x'),('--links-primary',{}),('--links-motion','infinite'),('--links-card-height',float('nan'))]:
   with self.subTest(token=token,value=value),self.assertRaises(ValueError):themes.validate_tokens({token:value})
 def test_expert_css(self):
  theme=self.custom();values=themes.css_import(themes.css_export(theme))['tokens'];self.assertEqual(len(values),len(themes.SCHEMA))
  result=themes.css_import('body { display:none; } :root { --links-primary:#abcdef; }');self.assertEqual(result['tokens'],{'--links-primary':'#abcdef'});self.assertTrue(result['ignored_rules'])
  for value in ['body{display:none}',':root{--links-evil:5}',':root{--links-page-width:9999px}',':root{--links-primary:var(--evil)}',':root{--links-page-image:url(https://evil)}']:
   with self.assertRaises(ValueError):themes.css_import(value)
 def test_portable_personal_assets_and_backup(self):
  raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWZkAAAAASUVORK5CYII=');ref='/uploads/'+str(uuid.uuid4())+'.png';(self.a.UPLOADS/ref[9:]).write_bytes(raw)
  row=self.custom(tokens={'--links-page-image':ref,'--links-card-image':'system:shopping'});self.save(theme=row,publish=True)
  package=themes.export(row,self.a.UPLOADS)
  with self.a.connection() as db:result=themes.import_package(db,package,self.a.UPLOADS)
  incoming=result['items'][-1];self.assertNotEqual(incoming['tokens']['--links-page-image'],ref);self.assertEqual(incoming['tokens']['--links-card-image'],'system:shopping')
  self.assertEqual((self.a.UPLOADS/incoming['tokens']['--links-page-image'][9:]).read_bytes(),raw)
  backup=json.loads(self.a.export_backup());self.a.restore_backup(backup)
  with self.a.connection() as db:
   restored=themes.state(db);self.assertEqual(len(restored['items']),3);self.assertEqual(restored['active'],row['id'])
   for ref in themes.references(restored['items']):self.assertTrue((self.a.UPLOADS/ref[9:]).exists())
 def test_secure_package_rejection(self):
  package=themes.export(self.custom(),self.a.UPLOADS)
  for changes in [{'version':2},{'format':'bad'},{'scripts':'alert(1)'},{'assets':{'../evil.svg':'x'}},{'compatibility':{'engine':2}}]:
   with self.subTest(changes=changes),self.a.connection() as db,self.assertRaises(ValueError):themes.import_package(db,{**package,**changes},self.a.UPLOADS)
  for i in range(3):self.save(theme=self.custom())
  with self.a.connection() as db,self.assertRaises(ValueError):themes.import_package(db,package,self.a.UPLOADS)
 def test_system_background_and_icons(self):
  self.assertEqual(len(themes.BACKGROUNDS),12)
  for asset in themes.LIBRARY['backgrounds']:self.assertTrue((themes.STATIC/asset['url'][1:]).exists())
  data={'type':'classic','internal_name':'Test','title':'Test','url':'https://example.com','image':'system:shopping','icon':'homeassistant'}
  self.assertEqual(self.a.block_data(data)['image'],'system:shopping');self.assertEqual(self.a.block_data(data)['icon'],'homeassistant')
  with self.assertRaises(ValueError):self.a.block_data({**data,'image':'system:nope'})

if __name__=='__main__':unittest.main()
