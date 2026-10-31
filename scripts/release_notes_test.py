import importlib.util, tempfile, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('notes',Path(__file__).with_name('release-notes.py'));notes=importlib.util.module_from_spec(spec);spec.loader.exec_module(notes)
class NotesTests(unittest.TestCase):
 def test_sections_and_skip(self):
  value=notes.render(['feat: Bibliothèque','theme: Thèmes publics','fix: Aperçu','Reserve production V1.3 [skip ci]','Merge pull request #1','perf: Chargement'])
  self.assertIn('✨ Nouveautés',value);self.assertIn('🐛 Corrections',value);self.assertNotIn('Technique',value);self.assertNotIn('Reserve',value)
 def test_manual_notes_and_idempotence(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);path=root/'docs/releases/V1.3.md';path.parent.mkdir(parents=True);path.write_text('## Nouveautés\n\n- Thèmes publics\n',encoding='utf-8')
   notes.prepare(root,'V1.3','source');first=(root/'CHANGELOG.md').read_bytes();notes.prepare(root,'V1.3','source');self.assertEqual(first,(root/'CHANGELOG.md').read_bytes());self.assertEqual(first.count(b'## V1.3'),1)
 def test_previous_dotted_patch_is_release_boundary(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder,patch.object(notes.subprocess,'check_output',side_effect=['V1.4.1\nV1.4\n','fix: Correction ciblée\n']) as git:
   root=Path(folder);notes.prepare(root,'V1.4.2','source')
   self.assertEqual(git.call_args_list[1].args[0],['git','log','--format=%s','V1.4.1..source'])
   self.assertIn('## V1.4.2',(root/'CHANGELOG.md').read_text(encoding='utf-8'))
if __name__=='__main__':unittest.main()
