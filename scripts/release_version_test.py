import importlib.util, unittest, sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('release',Path(__file__).with_name('release-version.py'));release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
class VersionTest(unittest.TestCase):
 def test_corrections(self):
  for before,after in [('V1.2','V1.201'),('V1.201','V1.202'),('V1.3','V1.301'),('V1.301','V1.302')]:self.assertEqual(release.next_version(before),after)
 def test_minor(self):
  self.assertEqual(release.next_version('V1.202',minor=True),'V1.3')
  self.assertEqual(release.next_version('V1.2',minor=True),'V1.3')
 def test_normal_merge(self):self.assertEqual(release.choose('Merge targeted fixes',current='V1.201'), 'V1.202')
 def test_official(self):
  self.assertEqual(release.choose('Release V1.201'),'V1.201')
  self.assertEqual(release.choose('[release] corrections',current='V1.201'),'V1.202')
  self.assertEqual(release.choose('[release minor] changes',current='V1.201'),'V1.3')
 def test_sequence_and_retry(self):
  self.assertEqual(release.next_version(release.next_version('V1.201')),'V1.203')
  self.assertEqual(release.plan('V1.202','abc',{'source_sha':'abc','version':'V1.202'}),'V1.202')
  self.assertEqual(release.plan('V1.202','def',{'source_sha':'abc','version':'V1.202'}),'V1.203')
  self.assertEqual(release.plan('V1.299','def',override='V1.3'),'V1.3')
  self.assertEqual(release.next_version('V1.3'),'V1.301')
 def test_persistent_sequence(self):
  import tempfile
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'VERSION').write_text('V1.201')
   self.assertEqual(release.reserve(root,'first'),'V1.202')
   self.assertEqual(release.reserve(root,'first'),'V1.202')
   self.assertEqual(release.reserve(root,'second'),'V1.203')
   self.assertEqual((root/'VERSION').read_text().strip(),'V1.203')
   self.assertEqual(release.reserve(root,'milestone','V1.3'),'V1.3')
   self.assertEqual(release.reserve(root,'third'),'V1.301')
 def test_real_git_reservation_retry_and_stale_run(self):
  import tempfile,subprocess,shutil,os
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)/'work';remote=Path(directory)/'origin.git';root.mkdir()
   def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
   subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
   git('init','-b','main');git('config','user.name','Test');git('config','user.email','test@example.invalid');git('remote','add','origin',str(remote))
   (root/'scripts').mkdir();shutil.copy(Path(__file__).with_name('release-version.py'),root/'scripts/release-version.py');(root/'VERSION').write_text('V1.201');git('add','.');git('commit','-m','Initial');git('push','origin','main');first=git('rev-parse','HEAD')
   def run(source,override=''):
    output=root/'output';output.write_text('');subprocess.run([sys.executable,str(root/'scripts/release-version.py')],env={**os.environ,'GITHUB_SHA':source,'GITHUB_OUTPUT':str(output),'RELEASE_OVERRIDE':override},check=True,capture_output=True);return dict(line.split('=',1) for line in output.read_text().splitlines())
   output=run(first);self.assertEqual(output['version'],'V1.202');self.assertEqual(output['tag'],'V1.202');reserved=git('rev-parse','HEAD');self.assertIn('[skip ci]',git('log','-1','--format=%s'))
   self.assertEqual(run(first)['version'],'V1.202');self.assertEqual(git('rev-parse','HEAD'),reserved)
   git('commit','--allow-empty','-m','Next validated change');git('push','origin','HEAD:main');second=git('rev-parse','HEAD');self.assertEqual(run(second)['version'],'V1.203')
   self.assertEqual(run(first)['eligible'],'false');self.assertEqual((root/'VERSION').read_text().strip(),'V1.203')
 def test_patch_overflow(self):
  with self.assertRaises(ValueError):release.next_version('V1.299')
if __name__=='__main__':unittest.main()
