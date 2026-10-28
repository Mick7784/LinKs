"""Default visuals are persistent settings, never a rewrite of campaign identity."""
import base64
import copy
import json
import unittest
import uuid

import analytics as a
import campaign_selection_test
from images_test import raster


class CampaignVisualTests(unittest.TestCase):
    setUp=campaign_selection_test.CampaignSelectionTests.setUp
    create=campaign_selection_test.CampaignSelectionTests.create
    server=campaign_selection_test.CampaignSelectionTests.server
    request=campaign_selection_test.CampaignSelectionTests.request

    def image(self,format='PNG'):
        extension={'PNG':'png','JPEG':'jpg','WEBP':'webp'}[format]
        path='/uploads/'+str(uuid.uuid4())+'.'+extension
        (a.UPLOADS/path[9:]).write_bytes(raster(format));return path

    def test_default_priority_reset_and_setting_never_rewrite_campaigns_or_metrics(self):
        own=self.image();default=self.image('WEBP')
        specific=self.create('Specific',image=own,type='featured');inherited=self.create('Inherited')
        a.story_link(inherited,'youtube');a.record('click','youtube','block:'+inherited)
        before=json.loads(a.export_backup())['tables']
        config=a.public_config();self.assertEqual(config['campaign_default_image'],a.CAMPAIGN_FALLBACK)
        self.assertEqual(next(r for r in config['links'] if r['id']==inherited)['image'],'')
        a.save_campaign_image({'image':default});a.init()
        config=a.public_config();links={r['id']:r for r in config['links']}
        self.assertEqual(links[specific]['effective_image'],own)
        self.assertEqual(links[inherited]['effective_image'],default)
        self.assertEqual(links[inherited]['image'],'')
        for table in ['content_blocks','counts','story_links','short_aliases']:
            self.assertEqual(json.loads(a.export_backup())['tables'][table],before[table])
        a.save_campaign_image({'image':''})
        self.assertEqual(next(r for r in a.public_config()['links'] if r['id']==inherited)['effective_image'],a.CAMPAIGN_FALLBACK)

    def test_upload_validation_public_isolation_and_real_formats(self):
        admin=self.server();public=self.server(False)
        self.assertEqual(self.request(public+'/api/appearance/campaign-image')[0],404)
        for format,mime in [('PNG','image/png'),('JPEG','image/jpeg'),('WEBP','image/webp')]:
            status,result=self.request(admin+'/api/upload',{'type':mime,'purpose':'campaign-default','data':base64.b64encode(raster(format)).decode()})
            self.assertEqual(status,201)
            self.assertEqual(self.request(admin+'/api/appearance/campaign-image',{'image':result['url']})[0],200)
        self.assertEqual(self.request(admin+'/api/upload',{'type':'image/gif','purpose':'campaign-default','data':base64.b64encode(raster('GIF')).decode()})[0],400)
        for value in ['https://example.com/a.png','/assets/link-shopping.webp','/uploads/../private.png','/uploads/'+str(uuid.uuid4())+'.png']:
            self.assertEqual(self.request(admin+'/api/appearance/campaign-image',{'image':value})[0],400)

    def test_portable_backup_and_old_backup_keep_default_file_reference(self):
        old=json.loads(a.export_backup());image=self.image();a.save_campaign_image({'image':image})
        exported=json.loads(a.export_backup());self.assertIn(image[9:],exported['images'])
        a.restore_backup(copy.deepcopy(exported))
        with a.connection() as db:restored=a.campaign_image_settings(db)['image']
        self.assertTrue((a.UPLOADS/restored[9:]).is_file())
        self.assertEqual((a.UPLOADS/restored[9:]).read_bytes(),raster())
        a.restore_backup(old)
        with a.connection() as db:self.assertEqual(a.campaign_image_settings(db)['image'],restored)
        a.storage_state('empty');self.assertTrue((a.UPLOADS/restored[9:]).is_file())

    def test_setting_protects_storage_then_reset_uses_existing_grace(self):
        image=self.image();a.save_campaign_image({'image':image})
        with a.connection() as db:
            refs=a.storage.references(db);self.assertEqual(refs[image[9:]][0]['category'],'campaigns')
            a.storage.scan(db,a.UPLOADS,'cleanup',now=100)
            self.assertEqual(list(db.execute('SELECT * FROM upload_trash')),[])
        a.save_campaign_image({'image':''})
        with a.connection() as db:
            a.storage.scan(db,a.UPLOADS,'cleanup',now=200)
            self.assertTrue((a.UPLOADS/image[9:]).is_file())
            a.storage.scan(db,a.UPLOADS,'cleanup',now=200+a.storage.GRACE_SECONDS)
        self.assertFalse((a.UPLOADS/image[9:]).exists())

    def test_title_only_creation_and_legacy_featured_update_keep_private_data(self):
        admin=self.server()
        status,new=self.request(admin+'/api/content',{'type':'promo','title':'Public title','url':'https://example.com'})
        self.assertEqual(status,201)
        current=next(r for r in a.content_list() if r['id']==new['id'])
        self.assertEqual(current['internal_name'],'Public title')
        self.assertEqual(self.request(admin+'/api/content/'+new['id'],{'title':'Renamed public title','url':current['url']},'PUT')[0],204)
        renamed=next(r for r in a.content_list() if r['id']==new['id'])
        self.assertEqual(renamed['internal_name'],'Public title');self.assertEqual(renamed['type'],'promo')
        ident=self.create('Private legacy name',type='featured',description='Description',priority='high')
        with a.connection() as db:db.execute("UPDATE content_blocks SET image='http://legacy.example/old.jpg' WHERE id=?",(ident,))
        current=next(r for r in a.content_list() if r['id']==ident)
        self.assertEqual(self.request(admin+'/api/content/'+ident,{**current,'title':'New public title'},'PUT')[0],204)
        saved=next(r for r in a.content_list() if r['id']==ident)
        self.assertEqual(saved['type'],'featured');self.assertEqual(saved['internal_name'],'Private legacy name')
        self.assertEqual(saved['description'],'Description');self.assertEqual(saved['image'],'http://legacy.example/old.jpg')

    def test_https_image_urls_are_campaign_only_and_preview_names_come_from_server(self):
        ident=self.create('Remote',image='https://images.example/campaign.webp')
        self.assertEqual(next(r for r in a.public_config()['links'] if r['id']==ident)['image'],'https://images.example/campaign.webp')
        for value in ['javascript:alert(1)','data:image/svg+xml,abc','https://user:password@example.com/a.png','http://example.com/a.png']:
            with self.assertRaises(ValueError):self.create('Invalid',image=value)
        with self.assertRaises(ValueError):self.create('Classic',type='classic',image='https://images.example/campaign.webp')
        result=a.campaign_selection();self.assertEqual(result['items'][0]['title'],'Remote')


if __name__=='__main__':unittest.main()
