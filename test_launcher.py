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
 def test_targets_new_game_without_old_update_sources(self):
  m=self.api.manifest;self.assertEqual((m['version_name'],m['version_code']),('20261119E',200534));self.assertEqual(m['compatible_previous'],{'e423a00c25479e923ea575d76d1c2ed6777b69a9d7afd08002242e7184391408':'0.5.1'})
  old={self.V43,'85b8f8eae4b5ca39de212720bbb53037223915825a8c83d5983f05dce4880520','b58836fe1d2a9125b73bf5d6d914428d2f56b3e916627f3989c6ffaca75c836d','2a43704a757e23933a6ca34ebc076e730ed94de7d5eba6b87d875b7f8f03ddc3','01ba10560f43e03a6f8f05e2ffd65c8d1ea956261fb893ef42eb4c03deb42731'}
  self.assertFalse(old&launcher.engine.known_hashes(m));self.assertEqual(self.api.config['version_code'],m['version_code'])
 def test_new_game_original_shows_install(self):
  from unittest.mock import Mock
  a=self.api;m=a.manifest;a.serial='TEST';fake=Mock()
  fake.run.return_value=('List of devices attached\nTEST device',0)
  fake.shell.side_effect=lambda *args,**kw:('TEST' if args[0]=='getprop' else '',0)
  fake.hash.side_effect=lambda path,**kw:m['source_sha256']
  with patch.object(a,'_find_adb',return_value='adb'),patch.object(launcher.engine,'Adb',return_value=fake),patch.object(launcher.engine,'version_check'):
   a._scan()
  s=a.get_state();self.assertEqual(s['current'],'미설치');self.assertEqual(s['install_label'],'한글패치 설치')
 def test_v051_install_shows_update(self):
  from unittest.mock import Mock
  a=self.api;m=a.manifest;a.serial='TEST';fake=Mock();v53='e423a00c25479e923ea575d76d1c2ed6777b69a9d7afd08002242e7184391408'
  fake.run.return_value=('List of devices attached\nTEST device',0)
  fake.shell.side_effect=lambda *args,**kw:('TEST' if args[0]=='getprop' else '',0)
  fake.hash.side_effect=lambda path,**kw:m['source_sha256'] if path.endswith(m['backup_suffix']) else v53
  with patch.object(a,'_find_adb',return_value='adb'),patch.object(launcher.engine,'Adb',return_value=fake),patch.object(launcher.engine,'version_check'):
   a._scan()
  s=a.get_state();self.assertEqual(s['current'],'v0.5.1');self.assertEqual(s['install_label'],'한글패치 업데이트');self.assertTrue(s['can_install'])
 def test_public_label(self):self.assertEqual(self.api.config['publication'],'Windows 설치기')
class HttpsFallbackTests(unittest.TestCase):
 def setUp(self):self.tmp=__import__('tempfile').TemporaryDirectory();self.old=launcher.STORAGE;launcher.STORAGE=Path(self.tmp.name);self.api=launcher.Api();self.repo=self.api.config['repository']
 def tearDown(self):launcher.STORAGE=self.old;self.tmp.cleanup()
 def test_cert_failure_retries_through_windows(self):
  import ssl
  name='H3VR2_Quest_Setup_v0.2.2.exe';data=[{'tag_name':'v0.2.2','prerelease':False,'draft':False,'html_url':self.repo+'/releases/tag/v0.2.2','assets':[{'name':name,'browser_download_url':self.repo+'/releases/download/v0.2.2/'+name}]}]
  err=urllib.error.URLError(ssl.SSLCertVerificationError(1,'unable to get issuer certificate'))
  with patch.object(launcher.urllib.request,'urlopen',side_effect=err),patch.object(launcher.engine.os,'name','nt'),patch.object(launcher.engine,'windows_https_get',return_value=('u',json.dumps(data).encode())) as w:
   self.api._latest()
  w.assert_called_once();self.assertEqual(self.api.get_state()['latest'],'v0.2.2')
 def test_other_network_errors_do_not_use_fallback(self):
  with patch.object(launcher.urllib.request,'urlopen',side_effect=urllib.error.URLError('offline')),patch.object(launcher.engine,'windows_https_get') as w:
   self.api._latest()
  w.assert_not_called();self.assertEqual(self.api.get_state()['latest'],'버전 확인 실패')
 def test_fallback_failure_reports_original_error(self):
  import ssl
  err=urllib.error.URLError(ssl.SSLCertVerificationError(1,'x'))
  with patch.object(launcher.urllib.request,'urlopen',side_effect=err),patch.object(launcher.engine.os,'name','nt'),patch.object(launcher.engine,'windows_https_get',side_effect=OSError('no clr')):
   with self.assertRaises(urllib.error.URLError):launcher.engine.https_get('https://api.github.com/x',{},5,10)
if __name__=='__main__':unittest.main(verbosity=2)
