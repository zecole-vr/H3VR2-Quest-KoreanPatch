import hashlib,json,unittest
from pathlib import Path
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
 def _shipped_models(self):
  shipped=json.loads((Path(e.__file__).parent/'bundle/manifest.json').read_text(encoding='utf8'))
  self.m.update(supported_models=shipped['supported_models'],supported_model_regex=shipped['supported_model_regex'])
 def test_quest3s_installs_when_files_match(self):
  self._shipped_models()
  for model in ('Quest 3S','Quest 3S Xbox Edition','Quest 3'):
   self.tearDown();self.setUp();self._shipped_models();self.d.model=model
   self.install()
   with self.subTest(model=model):self.assertEqual(self.d.files[self.d.main],b'PATCHED!')
 def test_other_models_refused_with_model_name(self):
  for model in ('Quest 2','Quest Pro','Quest 30','','Pico 4'):
   self.tearDown();self.setUp();self._shipped_models();self.d.model=model
   with self.subTest(model=model):
    with self.assertRaises(e.PatchError) as ctx:self.install()
    self.assertIn(model or '모델명 확인 불가',str(ctx.exception));self.assertFalse(self.d.mutations)
 def test_quest3s_with_different_apk_untouched(self):
  self._shipped_models();self.d.model='Quest 3S';self.d.files['/data/base.apk']=b'OTHER-APK'
  with self.assertRaises(e.PatchError):self.install()
  self.assertFalse(self.d.mutations)
 # ---- PC-only original (device original copy removed, e.g. by a pc-only cleanup policy) ----
 def _pc_only_state(self):
  e.install(self.d,self.m,self.w,self.b);del self.d.files[self.d.back];self.d.mutations.clear()
 def test_pc_only_restore_pushes_verified_pc_original(self):
  self._pc_only_state();e.restore(self.d,self.m,self.w)
  self.assertEqual(self.d.files[self.d.main],b'ORIGINAL');self.assertNotIn(self.d.back,self.d.files);self.assertEqual(self._extra(),[])
  r=json.loads((self.w/'installation.json').read_text());self.assertEqual((r['state'],r['device_original_backup'],r['backup_policy']),('restored',None,'pc-only'))
 def test_pc_only_update_and_same_version_check(self):
  v1=self._release(b'PATCH-V1',{});v2=self._release(b'PATCH-V2',{sha(b'PATCH-V1'):'0.1.0'})
  e.install(self.d,v1[0],self.w,v1[1]);del self.d.files[self.d.back]
  e.install(self.d,v2[0],self.w,v2[1]);self.assertEqual(self.d.files[self.d.main],b'PATCH-V2');self.assertNotIn(self.d.back,self.d.files);self.assertEqual(self._extra(),[])
  self.d.mutations.clear();e.install(self.d,v2[0],self.w,v2[1]);self.assertFalse(self.d.mutations)
  self.assertEqual(json.loads((self.w/'installation.json').read_text())['backup_policy'],'pc-only')
 def test_pc_only_without_or_with_wrong_pc_original_untouched(self):
  for content in (None,b'CORRUPT!',b'SHORT'):
   self.tearDown();self.setUp();self._pc_only_state()
   if content is None:(self.w/'original.hdog').unlink()
   else:(self.w/'original.hdog').write_bytes(content)
   with self.subTest(content=content):
    with self.assertRaises(e.PatchError):e.restore(self.d,self.m,self.w)
    self.assertFalse(self.d.mutations);self.assertEqual(self.d.files[self.d.main],b'PATCHED!');self.assertNotIn(self.d.back,self.d.files)
 def test_pc_only_stale_verification_record_rehashed(self):
  self._pc_only_state();e.pc_original(self.w,self.m)
  p=self.w/'original.hdog';st=p.stat();p.write_bytes(b'CORRUPT!');__import__('os').utime(p,ns=(st.st_atime_ns,st.st_mtime_ns))
  self.assertIsNotNone(e.pc_original(self.w,self.m));self.assertIsNone(e.pc_original(self.w,self.m,full=True))
  with self.assertRaises(e.PatchError):e.restore(self.d,self.m,self.w)
  self.assertFalse(self.d.mutations)
 def test_pc_only_interruptions_recover_on_rerun(self):
  for action in ('update','restore'):
   for k in range(4):
    self.tearDown();self.setUp()
    v1=self._release(b'PATCH-V1',{});v2=self._release(b'PATCH-V2',{sha(b'PATCH-V1'):'0.1.0'})
    e.install(self.d,v1[0],self.w,v1[1]);del self.d.files[self.d.back]
    m,b=v2 if action=='update' else v1
    run=(lambda:e.restore(self.d,m,self.w)) if action=='restore' else (lambda:e.install(self.d,m,self.w,b))
    self._disconnect_from(k)
    try:run()
    except Exception:pass
    self.d.down=False
    run()
    with self.subTest(action=action,k=k):
     self.assertEqual(self._extra(),[]);self.assertNotIn(self.d.back,self.d.files)
     self.assertEqual(self.d.files[self.d.main],b'ORIGINAL' if action=='restore' else b'PATCH-V2')
 def test_pc_only_recovery_keeps_device_original_when_pc_original_lost(self):
  # Interrupted pc-only restore (k=0: before first mv, k=1: after first mv); PC original then lost -> recover only.
  for k in (0,1):
   self.tearDown();self.setUp();self._pc_only_state();self._disconnect_from(k)
   with self.assertRaises(Exception):e.restore(self.d,self.m,self.w)
   self.d.down=False;(self.w/'original.hdog').unlink();e.recover(self.d,self.m,self.w)
   with self.subTest(k=k):
    self.assertEqual(self.d.files[self.d.main],b'PATCHED!');self.assertEqual(self.d.files[self.d.back],b'ORIGINAL');self.assertEqual(self._extra(),[])
    self.assertIn(json.loads((self.w/'transaction.json').read_text())['phase'],('abandoned','rolled_back'))
 def test_install_from_original_never_deletes_device_original(self):
  # After a pc-only restore the device holds only the original in main: a new install keeps it as the device backup.
  self._pc_only_state();e.restore(self.d,self.m,self.w)
  r=json.loads((self.w/'installation.json').read_text());self.assertEqual((r['device_original_backup'],r['backup_policy']),(None,'pc-only'))
  self.install();self.assertEqual(self.d.files[self.d.main],b'PATCHED!');self.assertEqual(self.d.files[self.d.back],b'ORIGINAL');self.assertEqual(self._extra(),[])
  r=json.loads((self.w/'installation.json').read_text());self.assertEqual((r['device_original_backup'],r['backup_policy']),(self.d.back,'device'))
 def test_preserve_never_overwrites_backup_path(self):
  self._pc_only_state();self._disconnect_from(0)
  with self.assertRaises(Exception):e.restore(self.d,self.m,self.w)
  self.d.down=False;(self.w/'original.hdog').unlink();self.d.files[self.d.back]=b'ALIEN!!!'
  with self.assertRaises(e.PatchError):e.recover(self.d,self.m,self.w)
  pend=[p for p in self.d.files if '.zecole-pending-' in p]
  self.assertEqual(self.d.files[self.d.back],b'ALIEN!!!');self.assertEqual([self.d.files[p] for p in pend],[b'ORIGINAL']);self.assertEqual(self.d.files[self.d.main],b'PATCHED!')
 def test_completion_preserves_original_before_recording(self):
  # pc-only restore whose second mv finished; a preserved-copy failure must leave the journal open (no loss on rerun).
  self._pc_only_state();real=e.save_receipt;calls=[0]
  def failing(*a,**kw):
   calls[0]+=1
   if calls[0]==1:raise ConnectionError('crash before receipt')
   return real(*a,**kw)
  with patch.object(e,'save_receipt',failing):
   with self.assertRaises(ConnectionError):e.restore(self.d,self.m,self.w)
  (self.w/'original.hdog').unlink();e.recover(self.d,self.m,self.w);e.recover(self.d,self.m,self.w)
  self.assertEqual(self.d.files[self.d.main],b'ORIGINAL');self.assertEqual(self._extra(),[])
 def test_sweep_keeps_last_original_copy_from_old_journal(self):
  # Device-mode install from the original with a device backup: the retired original copy is left behind (rm fails),
  # then the backup and the PC original disappear. Sweeping the finished journal must keep that copy.
  self.install();e.restore(self.d,self.m,self.w);original=self.d.shell
  def no_rm(*a,**kw):
   if a[0]=='rm' and '.zecole-retired-' in a[1]:raise ConnectionError('rm failed')
   return original(*a,**kw)
  self.d.shell=no_rm;self.install();self.d.shell=original
  left=[p for p in self.d.files if '.zecole-retired-' in p];self.assertEqual([self.d.files[p] for p in left],[b'ORIGINAL'])
  del self.d.files[self.d.back];(self.w/'original.hdog').unlink();e.recover(self.d,self.m,self.w)
  self.assertEqual(self.d.files[self.d.back],b'ORIGINAL');self.assertEqual(self.d.files[self.d.main],b'PATCHED!');self.assertEqual(self._extra(),[])
 def test_device_mode_journal_completes_with_pc_original_after_backup_removed(self):
  v1=self._release(b'PATCH-V1',{});v2=self._release(b'PATCH-V2',{sha(b'PATCH-V1'):'0.1.0'})
  e.install(self.d,v1[0],self.w,v1[1]);real=e.save_receipt;calls=[0]
  def failing(*a,**kw):
   calls[0]+=1
   if calls[0]==1:raise ConnectionError('crash before receipt')
   return real(*a,**kw)
  with patch.object(e,'save_receipt',failing):
   with self.assertRaises(ConnectionError):e.install(self.d,v2[0],self.w,v2[1])
  del self.d.files[self.d.back];e.recover(self.d,v2[0],self.w)
  self.assertEqual(self.d.files[self.d.main],b'PATCH-V2');self.assertEqual(json.loads((self.w/'transaction.json').read_text())['phase'],'complete');self.assertEqual(self._extra(),[])
 def test_receipt_labels_previous_patch_as_installed(self):
  m=dict(self.m,compatible_previous={sha(b'OLDPATCH'):'0.1.0'});e.save_receipt(self.w,m,sha(b'OLDPATCH'),None)
  r=json.loads((self.w/'installation.json').read_text());self.assertEqual((r['state'],r['release']),('installed','0.1.0'))
 def test_adb_exists_requires_explicit_answer(self):
  a=e.Adb('adb','X')
  for out,code,want in (('ZECOLE_EXISTS',0,True),('ZECOLE_ABSENT',0,False),('error: device offline',1,None),('',255,None)):
   with patch.object(a,'run',return_value=(out,code)),self.subTest(out=out):
    if want is None:
     with self.assertRaises(e.PatchError):a.exists('/sdcard/x')
    else:self.assertEqual(a.exists('/sdcard/x'),want)
if __name__=='__main__':unittest.main(verbosity=2)
