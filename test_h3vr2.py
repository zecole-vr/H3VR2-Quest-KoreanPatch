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
 def _release(self,payload,prev):
  b=self.r/('bundle-'+sha(payload)[:8]);(b/'data').mkdir(parents=True);recipe=b'{"format":2,"operations":[["data",0,8]]}'
  (b/'data/payload.bin').write_bytes(payload);(b/'data/recipe.json').write_bytes(recipe)
  m=dict(self.m,target_sha256=sha(payload),recipe_sha256=sha(recipe),payload_sha256=sha(payload),compatible_previous=prev)
  (b/'manifest.json').write_text(json.dumps(m));return m,b
 def _extra(self):return sorted(p for p in self.d.files if p not in (self.d.main,self.d.back,'/data/base.apk'))
 def _disconnect_from(self,k):
  # Every mv/cp/rm from the k-th one fails until reconnect (in-process recovery fails too).
  original=self.d.shell;count=[0];self.d.down=True
  def shell(*a,**kw):
   if a[0] in ('mv','cp','rm') and self.d.down:
    count[0]+=1
    if count[0]>k:raise ConnectionError('unplugged')
   return original(*a,**kw)
  self.d.shell=shell
 def test_interruptions_leave_no_device_leftovers_after_rerun(self):
  for action in ('install','update','restore'):
   for k in range(5):
    self.tearDown();self.setUp()
    v1=self._release(b'PATCH-V1',{});v2=self._release(b'PATCH-V2',{sha(b'PATCH-V1'):'0.1.0'})
    if action!='install':e.install(self.d,v1[0],self.w,v1[1])
    if action=='restore':e.install(self.d,v2[0],self.w,v2[1])
    m,b=v1 if action=='install' else v2
    run=(lambda:e.restore(self.d,m,self.w)) if action=='restore' else (lambda:e.install(self.d,m,self.w,b))
    self._disconnect_from(k)
    try:run()
    except Exception:pass
    self.d.down=False
    run()
    with self.subTest(action=action,k=k):
     self.assertEqual(self._extra(),[])
     self.assertEqual(self.d.files[self.d.back],b'ORIGINAL')
     self.assertEqual(self.d.files[self.d.main],b'ORIGINAL' if action=='restore' else (b'PATCH-V1' if action=='install' else b'PATCH-V2'))
 def test_sweep_never_touches_unowned_files(self):
  alien=[self.d.main+'.zecole-pending-aaaaaaaaaaaa',self.d.main+'.zecole-retired-bbbbbbbbbbbb']
  for p in alien:self.d.files[p]=b'ALIEN'
  self.install();e.restore(self.d,self.m,self.w);self.install();self.assertEqual(self._extra(),alien)
 def test_pc_keeps_only_current_generated_output(self):
  v1=self._release(b'PATCH-V1',{});v2=self._release(b'PATCH-V2',{sha(b'PATCH-V1'):'0.1.0'})
  e.install(self.d,v1[0],self.w,v1[1]);self.assertTrue((self.w/'generated'/v1[0]['target_sha256']).is_dir())
  (self.w/'generated'/'not-ours').mkdir()
  e.install(self.d,v2[0],self.w,v2[1])
  self.assertEqual(sorted(p.name for p in (self.w/'generated').iterdir()),sorted([v2[0]['target_sha256'],'not-ours']))
if __name__=='__main__':unittest.main(verbosity=2)
