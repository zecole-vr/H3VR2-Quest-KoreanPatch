import json,unittest,urllib.error,copy
from pathlib import Path
from unittest.mock import patch
import launcher
class Response:
 def __init__(self,d):self.d=d
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self,n):return json.dumps(self.d).encode()
class LatestTests(unittest.TestCase):
 def setUp(self):self.tmp=__import__('tempfile').TemporaryDirectory();self.old=launcher.STORAGE;launcher.STORAGE=Path(self.tmp.name);self.api=launcher.Api();self.repo=self.api.config['repository']
 def tearDown(self):launcher.STORAGE=self.old;self.tmp.cleanup()
 def rel(self,v,platform='Quest_Setup',pre=False,checksum=True):
  name=f'H3VR2_{platform}_v{v}.exe';return {'tag_name':'v'+v,'prerelease':pre,'draft':False,'html_url':self.repo+'/releases/tag/v'+v,'assets':[{'name':name,'browser_download_url':self.repo+'/releases/download/v'+v+'/'+name}]+([{'name':name+'.sha256'}] if checksum else [])}
 def check(self,data):
  with patch.object(launcher.urllib.request,'urlopen',return_value=Response(data)):self.api._latest()
  return self.api.get_state()
 def test_semantic_latest(self):
  s=self.check([self.rel('0.9.0'),self.rel('0.10.0')]);self.assertEqual(s['latest'],'v0.10.0');self.assertTrue(s['newer_release'])
 def test_exclude_prerelease_wrong_platform_missing_checksum(self):
  s=self.check([self.rel('0.1.3'),self.rel('9.0.0',pre=True),self.rel('8.0.0',platform='Steam_Setup'),self.rel('7.0.0',platform='Quest_Windows')]);self.assertEqual(s['latest'],'v0.1.3')
 def test_exe_only_release_detected(self):self.assertEqual(self.check([self.rel('0.2.1',checksum=False)])['latest'],'v0.2.1')
 def test_empty_not_error(self):self.assertEqual(self.check([])['latest'],'공개 배포본 없음')
 def test_failed_then_retry(self):
  with patch.object(launcher.urllib.request,'urlopen',side_effect=urllib.error.URLError('offline')):self.api._latest()
  s=self.api.get_state();self.assertEqual(s['latest'],'버전 확인 실패');self.assertFalse(s['newer_release']);self.assertEqual(self.check([self.rel('0.1.3')])['latest'],'v0.1.3')
 def test_no_downgrade(self):self.assertFalse(self.check([self.rel('0.0.9')])['newer_release'])
 def test_foreign_url_rejected(self):
  r=self.rel('99.0.0');r['assets'][0]['browser_download_url']='https://example.com/a.exe';self.assertEqual(self.check([r])['latest'],'공개 배포본 없음')
 def test_duplicate_ui_request(self):
  with self.api.guard:self.api.state['busy']=True
  with patch.object(launcher.threading,'Thread') as t:self.api.refresh();t.assert_not_called()
 def test_legacy_label_uses_actual_registered_build(self):
  from unittest.mock import Mock
  a=self.api;m=a.manifest;a.serial='TEST';m['legacy_builds'][m['target_sha256']]='v43-local';fake=Mock()
  fake.run.return_value=('List of devices attached\nTEST device',0)
  fake.shell.side_effect=lambda *args,**kw:('TEST' if args[0]=='getprop' else '',0)
  fake.hash.side_effect=lambda path,**kw:m['target_sha256'] if path.endswith(m['main_name']) else None
  with patch.object(a,'_find_adb',return_value='adb'),patch.object(launcher.engine,'Adb',return_value=fake),patch.object(launcher.engine,'version_check'),patch.object(launcher.engine,'legacy_original',return_value='/verified-original'):
   a._scan()
  self.assertEqual(a.get_state()['current'],'v43 로컬 시험본')
class ShippedManifestTests(unittest.TestCase):
 V43='856c96bef800cd3a3fa54dc4083d244c094a065e5df56be4d51267066120a3c0'
 def setUp(self):self.tmp=__import__('tempfile').TemporaryDirectory();self.old=launcher.STORAGE;launcher.STORAGE=Path(self.tmp.name);self.api=launcher.Api()
 def tearDown(self):launcher.STORAGE=self.old;self.tmp.cleanup()
 def test_previous_public_release_is_update_source(self):
  m=self.api.manifest;self.assertEqual(m['compatible_previous'].get(self.V43),'0.1.0');self.assertNotEqual(m['target_sha256'],self.V43)
  self.assertIn(self.V43,launcher.engine.known_hashes(m))
 def test_previous_public_release_shows_update(self):
  from unittest.mock import Mock
  a=self.api;m=a.manifest;a.serial='TEST';fake=Mock()
  fake.run.return_value=('List of devices attached\nTEST device',0)
  fake.shell.side_effect=lambda *args,**kw:('TEST' if args[0]=='getprop' else '',0)
  fake.hash.side_effect=lambda path,**kw:self.V43 if path.endswith(m['main_name']) else m['source_sha256']
  with patch.object(a,'_find_adb',return_value='adb'),patch.object(launcher.engine,'Adb',return_value=fake),patch.object(launcher.engine,'version_check'):
   a._scan()
  s=a.get_state();self.assertEqual(s['current'],'v0.1.0');self.assertEqual(s['tag'],'업데이트 필요');self.assertEqual(s['install_label'],'한글패치 업데이트')
if __name__=='__main__':unittest.main(verbosity=2)
