import unittest,tempfile,os,json
from pathlib import Path
from unittest.mock import patch
import youtube
class YouTubeTests(unittest.TestCase):
 def setUp(self):youtube.CACHE.clear();self.calls=[]
 def fetch(self,resource,params,key):
  self.calls.append((resource,params));self.assertEqual(key,'private-test-key')
  if resource=='channels':return {'items':[{'id':'UC'+'a'*22,'snippet':{'title':'Chaîne test'},'contentDetails':{'relatedPlaylists':{'uploads':'UUplaylist'}}}]}
  if resource=='playlistItems':return {'items':[{'contentDetails':{'videoId':'abcdefghij'+str(i)}} for i in range(4)]}
  return {'items':[{'id':'abcdefghij'+str(i),'status':{'privacyStatus':'private' if i==2 else 'public'},'snippet':{'title':'Video '+str(i),'publishedAt':['2026-01-01T00:00:00Z','2026-02-01T00:00:00Z','2026-03-01T00:00:00Z','2099-01-01T00:00:00Z'][i],'thumbnails':{'high':{'url':'https://i.ytimg.com/vi/abcdefghij1/hqdefault.jpg'}}}} for i in range(4)]}
 def test_latest_public_video_and_cache(self):
  result=youtube.latest('@test','private-test-key',fetcher=self.fetch)
  self.assertEqual(result['video']['title'],'Video 1');self.assertEqual(self.calls[0][1]['forHandle'],'test')
  self.assertTrue(youtube.latest('@test','private-test-key',fetcher=self.fetch)['cached']);self.assertEqual(len(self.calls),3)
  youtube.latest('@test','private-test-key',force=True,fetcher=self.fetch);self.assertEqual(len(self.calls),6)
  self.assertNotIn('private-test-key',json.dumps(result));self.assertNotIn('private',json.dumps(result['video']))
 def test_errors_stale_cache_and_isolation(self):
  clock=lambda:1800000000
  youtube.latest('@test','private-test-key',fetcher=self.fetch,clock=clock)
  def fail(*args):raise ValueError('Source indisponible')
  self.assertTrue(youtube.latest('@test','private-test-key',fetcher=fail,clock=lambda:1800000400)['stale'])
  with self.assertRaises(ValueError):youtube.latest('@test','private-test-key',force=True,fetcher=fail)
  with self.assertRaises(ValueError):youtube.latest('@other','private-test-key',fetcher=fail)
 def test_channel_input_and_private_key(self):
  self.assertEqual(youtube.channel_query('https://youtube.com/@test/videos'),{'forHandle':'test'})
  for value in ['https://evil.example/@test','https://youtube.com/watch?v=foo','foo']:
   with self.assertRaises(ValueError):youtube.channel_query(value)
  with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{},clear=True):
   youtube.store_key(directory,'a'*39);self.assertEqual(youtube.read_key(directory),'a'*39)
   if os.name!='nt':self.assertEqual(youtube.key_path(directory).stat().st_mode&0o777,0o600)
   youtube.store_key(directory,'');self.assertEqual(youtube.read_key(directory),'')
if __name__=='__main__':unittest.main()
