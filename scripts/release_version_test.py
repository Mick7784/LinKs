import importlib.util, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('release',Path(__file__).with_name('release-version.py'));release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
class VersionTest(unittest.TestCase):
 def test_corrections(self):
  for before,after in [('V1.2','V1.201'),('V1.201','V1.202'),('V1.3','V1.301'),('V1.301','V1.302')]:self.assertEqual(release.next_version(before),after)
 def test_minor(self):
  self.assertEqual(release.next_version('V1.202',minor=True),'V1.3')
  self.assertEqual(release.next_version('V1.2',minor=True),'V1.3')
 def test_no_unrequested_release(self):self.assertEqual(release.choose('Merge targeted fixes'), '')
 def test_official(self):
  self.assertEqual(release.choose('Release V1.201'),'V1.201')
  self.assertEqual(release.choose('[release] corrections'),'V1.202')
  self.assertEqual(release.choose('[release minor] changes'),'V1.3')
 def test_patch_overflow(self):
  with self.assertRaises(ValueError):release.next_version('V1.299')
if __name__=='__main__':unittest.main()
