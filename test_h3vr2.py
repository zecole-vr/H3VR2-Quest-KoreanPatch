import hashlib,json,unittest
from unittest.mock import patch
from test_engine import EngineTests,sha
import quest_patch as e
class H3VR2Tests(EngineTests):
 def test_bsdiff_variable_size(self):
  target=b'ORIGINAL plus translated data';blob=e.bsdiff4.diff(b'ORIGINAL',target)
  recipe=json.dumps({'format':2,'operations':[['bsdiff',0,len(target),0,8,len(blob),sha(target)]]}).encode()
  (self.b/'data/payload.bin').write_bytes(blob);(self.b/'data/recipe.json').write_bytes(recipe)
  self.m.update(target_bytes=len(target),target_sha256=sha(target),recipe_sha256=sha(recipe),payload_sha256=sha(blob))
  (self.b/'manifest.json').write_text(json.dumps(self.m));self.install();self.assertEqual(self.d.files[self.d.main],target)
  e.restore(self.d,self.m,self.w);self.assertEqual(self.d.files[self.d.main],b'ORIGINAL')
 def test_entrypoint_prevents_duplicate_engine(self):
  with e.operation_lock(e.STORAGE/'engine'):
   with self.assertRaises(e.PatchError):self.install()
  self.assertFalse(self.d.mutations)
 def test_legacy_migration_validated(self):
  path='/sdcard/ZECOLE/H3VR2/legacy-original';self.m.update(legacy_builds={sha(b'PATCHED!'):'v42-local'},legacy_original_paths=[path]);self.d.files[path]=b'ORIGINAL';self.d.files[self.d.main]=b'PATCHED!'
  self.install();self.assertEqual(self.d.files[path],b'ORIGINAL');self.assertEqual(self.d.files[self.d.back],b'ORIGINAL');self.assertEqual(self.d.files[self.d.main],b'PATCHED!');self.assertEqual(json.loads((self.w/'migration.json').read_text())['status'],'complete')
 def test_legacy_wrong_original_untouched(self):
  path='/sdcard/ZECOLE/H3VR2/legacy-original';self.m.update(legacy_builds={sha(b'PATCHED!'):'v42-local'},legacy_original_paths=[path]);self.d.files[path]=b'UNKNOWN';self.d.files[self.d.main]=b'PATCHED!'
  with self.assertRaises(e.PatchError):self.install()
  self.assertFalse(self.d.mutations)
 def test_foreign_migration_temp_preserved(self):
  path='/sdcard/ZECOLE/H3VR2/legacy-original';self.m.update(legacy_builds={sha(b'PATCHED!'):'v42-local'},legacy_original_paths=[path]);self.d.files[path]=b'ORIGINAL';self.d.files[self.d.main]=b'PATCHED!';self.d.files[self.d.back+'.migration-pending']=b'ALIEN'
  with self.assertRaises(e.PatchError):self.install()
  self.assertEqual(self.d.files[self.d.back+'.migration-pending'],b'ALIEN');self.assertFalse(self.d.mutations)
 def test_wrong_version_name_untouched(self):
  original=self.d.shell
  def shell(*a,**kw):return ('versionCode=200502 versionName=NEWGAME',0) if a[0]=='dumpsys' else original(*a,**kw)
  self.d.shell=shell
  with self.assertRaises(e.PatchError):self.install()
  self.assertFalse(self.d.mutations)
if __name__=='__main__':unittest.main(verbosity=2)
