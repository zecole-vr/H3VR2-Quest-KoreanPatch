#!/usr/bin/env python3
"""H3VR2 Quest Korean patch shared core. Derived from ITR2 Quest release 1.2.5.

Installer code: MIT (licenses/INSTALLER-MIT.txt).
Game-specific translation provenance: THIRD_PARTY_NOTICES.md.
No APK installation, account access, or save restoration.
"""
from __future__ import annotations
import argparse
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import uuid
import zlib
import time
import tempfile
import urllib.request
import zipfile
import webbrowser
sys.path.insert(0,str(Path(__file__).resolve().parent/"vendor"))
import bsdiff4

ROOT = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
CHUNK = 8 * 1024 * 1024
ADB_URL = 'https://dl.google.com/android/repository/platform-tools_r37.0.0-win.zip'
ADB_ZIP_HASH = '4fe305812db074cea32903a489d061eb4454cbc90a49e8fea677f4b7af764918'
ADB_TERMS = 'https://developer.android.com/studio/terms'

class PatchError(Exception):
    pass

def unpack_adb(archive, destination):
    """Only extract the pinned official archive inside a new private staging directory."""
    if sha256(archive) != ADB_ZIP_HASH:
        raise PatchError('ADB 다운로드 체크섬이 다릅니다. 실행하지 않고 중단합니다.')
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            parts = member.filename.split('/')
            if parts[0] != 'platform-tools' or any(x in ('.', '..') or ':' in x or '\\' in x for x in parts):
                raise PatchError('ADB 압축 파일에 잘못된 경로가 있습니다.')
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination):
                raise PatchError('ADB 압축 해제 경로 오류')
        z.extractall(destination)
    tool = destination / 'platform-tools'
    for name in ('adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'NOTICE.txt'):
        if not (tool / name).is_file():
            raise PatchError('ADB 필수 파일이 빠졌습니다: ' + name)
    return tool

def _is_cert_error(exc):
    import ssl
    return isinstance(exc, ssl.SSLCertVerificationError) or isinstance(getattr(exc, 'reason', None), ssl.SSLCertVerificationError)

def windows_https_get(url, headers, timeout, limit):
    """Same GET through Windows' own HTTPS stack (.NET/SChannel).

    Python's ssl only trusts roots already present in the Windows store; Windows itself
    downloads a missing trusted root on demand, so this succeeds where urllib fails on a
    PC that has not yet needed that root. Certificate validation stays fully enabled.
    """
    import clr  # pythonnet, bundled for the WebView UI
    clr.AddReference('System.Net.Http')
    from System import TimeSpan
    from System.Net import ServicePointManager, SecurityProtocolType
    from System.Net.Http import HttpClient
    ServicePointManager.SecurityProtocol = ServicePointManager.SecurityProtocol | SecurityProtocolType.Tls12
    client = HttpClient()
    try:
        client.Timeout = TimeSpan.FromSeconds(timeout)
        client.MaxResponseContentBufferSize = limit + 1
        for key, value in headers.items():
            client.DefaultRequestHeaders.TryAddWithoutValidation(key, value)
        response = client.GetAsync(url).Result
        response.EnsureSuccessStatusCode()
        final = str(response.RequestMessage.RequestUri)
        temp = Path(tempfile.mkdtemp(prefix='zecole-https-'))
        try:
            from System.IO import File
            File.WriteAllBytes(str(temp / 'body'), response.Content.ReadAsByteArrayAsync().Result)
            data = (temp / 'body').read_bytes()
        finally:
            shutil.rmtree(temp, ignore_errors=True)
    finally:
        client.Dispose()
    if len(data) > limit:
        raise PatchError('다운로드 크기가 예상 범위를 벗어났습니다.')
    return final, data

def https_get(url, headers, timeout, limit):
    """Return (final_url, body). Falls back to Windows HTTPS only for certificate-chain failures."""
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(limit + 1)
            final = getattr(response, 'geturl', lambda: url)()
    except Exception as exc:
        if not _is_cert_error(exc) or os.name != 'nt':
            raise
        try:
            return windows_https_get(url, headers, timeout, limit)
        except Exception:
            raise exc
    if len(data) > limit:
        raise PatchError('다운로드 크기가 예상 범위를 벗어났습니다.')
    return final, data

def prepare_adb(root=ROOT, accept_terms=False):
    home = Path(root) / '.tools'
    installed = home / 'platform-tools-37.0.0'
    receipt = installed / 'download-receipt.json'
    if receipt.is_file():
        record = json.loads(receipt.read_text(encoding='utf-8'))
        if record.get('archive_sha256') == ADB_ZIP_HASH and record.get('license_accepted') is True:
            hashes = record.get('files', {})
            required = {'adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'NOTICE.txt'}
            if required.issubset(hashes) and all(
                    Path(name).name == name and (installed / name).is_file()
                    and sha256(installed / name) == expected for name, expected in hashes.items()):
                return str(installed / 'adb.exe')
        raise PatchError('자동 준비한 ADB가 손상되었습니다. .tools 폴더를 별도 보관한 뒤 다시 실행하세요.')
    say('연결 도구 ADB를 처음 한 번 Google 공식 서버에서 다운로드합니다.')
    say('별도 설치나 관리자 권한은 필요하지 않으며 인터넷 연결이 필요합니다.')
    say('Google Android SDK 약관: ' + ADB_TERMS)
    say('Y: 약관에 동의하고 다운로드 / V: 약관을 브라우저에서 보기 / N: 취소')
    while not accept_terms:
        try:
            answer = input('선택 [Y/V/N]: ').strip().lower()
        except EOFError:
            raise PatchError('ADB 약관 확인이 필요합니다. 설치.bat에서 직접 실행하세요.')
        if answer == 'v':
            webbrowser.open(ADB_TERMS)
        elif answer == 'y':
            break
        else:
            raise PatchError('ADB 다운로드를 취소했습니다. 기기는 변경하지 않았습니다.')
    home.mkdir(parents=True, exist_ok=True)
    with operation_lock(home):
        if installed.exists():
            raise PatchError('.tools에 기존 ADB 폴더가 있습니다. 덮어쓰지 않습니다.')
        staging = Path(tempfile.mkdtemp(prefix='download-', dir=home)).resolve()
        try:
            archive = staging / 'platform-tools.zip'
            say('ADB 다운로드 중...')
            final, data = https_get(ADB_URL, {'User-Agent': 'ZECOLE-H3VR2-Quest'}, 60, 64 * 1024 * 1024)
            if not final.startswith('https://dl.google.com/'):
                raise PatchError('공식 서버가 아닌 다운로드 주소로 연결되었습니다.')
            with archive.open('xb') as f:
                f.write(data)
            say(f'ADB 다운로드: {len(data) // 1024} KB')
            tool = unpack_adb(archive, staging)
            record = {'url': ADB_URL, 'archive_sha256': ADB_ZIP_HASH, 'license_accepted': True,
                      'terms_url': ADB_TERMS, 'accepted_at': datetime.datetime.now().isoformat(),
                      'files': {f.name: sha256(f) for f in tool.iterdir() if f.is_file()}}
            (tool / 'download-receipt.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
            tool.rename(installed)
            say('ADB 준비 완료. 다음 실행부터 다시 다운로드하지 않습니다.')
        finally:
            if staging.is_relative_to(home.resolve()) and staging.name.startswith('download-'):
                shutil.rmtree(staging)
    return str(installed / 'adb.exe')

def say(message):
    print(message, flush=True)

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()

def load_release(root=ROOT):
    root=Path(root)
    m=json.loads((root/'manifest.json').read_text(encoding='utf8'))
    if m.get('format')!=2:raise PatchError('지원하지 않는 배포 형식입니다.')
    for name,key in [('recipe.json','recipe_sha256'),('payload.bin','payload_sha256')]:
        if sha256(root/'data'/name)!=m[key]:raise PatchError('패치 데이터 무결성 오류: '+name)
    recipe=json.loads((root/'data/recipe.json').read_text(encoding='utf8'))
    if recipe.get('format')!=2:raise PatchError('지원하지 않는 변환 형식입니다.')
    total=0;size=(root/'data/payload.bin').stat().st_size
    for op in recipe['operations']:
        if not isinstance(op,list) or len(op) not in (3,7):raise PatchError('잘못된 변환 정보입니다.')
        kind,offset,length=op[:3]
        if any(type(n) is not int or n<0 for n in (offset,length)) or length==0:raise PatchError('잘못된 변환 범위입니다.')
        if kind=='copy' and len(op)==3:
            if offset+length>m['source_bytes']:raise PatchError('원본 범위를 벗어났습니다.')
        elif kind=='data' and len(op)==3:
            if offset+length>size:raise PatchError('패치 범위를 벗어났습니다.')
        elif kind=='bsdiff' and len(op)==7:
            oldoff,oldlen,patchlen,digest=op[3:]
            if any(type(n) is not int or n<0 for n in (oldoff,oldlen,patchlen)) or oldlen>CHUNK or length>CHUNK or patchlen>CHUNK*2 or oldoff+oldlen>m['source_bytes'] or offset+patchlen>size or not re.fullmatch('[a-f0-9]{64}',str(digest)):
                raise PatchError('잘못된 차분 범위입니다.')
        else:raise PatchError('지원하지 않는 변환 명령입니다.')
        total+=length
    if total!=m['target_bytes']:raise PatchError('예상 결과 크기가 다릅니다.')
    return m,recipe


def build(source, output, root=ROOT):
    """Reconstruct the exact verified HDOG. Wrong originals fail before any output is created."""
    m, recipe = load_release(root)
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output:
        raise PatchError('원본과 결과 경로는 달라야 합니다.')
    say('원본 게임 데이터 체크섬 확인 중...')
    if source.stat().st_size != m['source_bytes'] or sha256(source) != m['source_sha256']:
        raise PatchError(f'지원하는 H3VR2 Quest {m["version_name"]} / 빌드 {m["version_code"]} 원본이 아닙니다. 수정하거나 설치하지 않았습니다.')
    if output.exists():
        if sha256(output) == m['target_sha256']:
            say('이미 검증된 결과 파일이 있습니다.')
            return output
        raise PatchError('결과 경로에 다른 파일이 있습니다. 덮어쓰지 않습니다.')
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < m['target_bytes'] + 512 * 1024 * 1024:
        raise PatchError('결과 파일을 만들 PC 여유 공간이 부족합니다.')
    temp = output.with_name(output.name + '.building-' + uuid.uuid4().hex[:8])
    digest, written, last_notice = hashlib.sha256(), 0, 0
    try:
        with source.open('rb') as src, (Path(root) / 'data/payload.bin').open('rb') as payload, temp.open('xb') as dst:
            def write(block):
                nonlocal written, last_notice
                dst.write(block)
                digest.update(block)
                written += len(block)
                if written - last_notice >= 512 * 1024 * 1024:
                    say(f'패치 생성 {written * 100 // m["target_bytes"]}%')
                    last_notice = written
            for op in recipe['operations']:
                kind, offset, count = op[:3]
                if kind == 'bsdiff':
                    src.seek(op[3]);old=src.read(op[4]);payload.seek(offset);patch=payload.read(op[5])
                    if len(old)!=op[4] or len(patch)!=op[5]:raise PatchError('차분 입력 파일이 불완전합니다.')
                    if patch[:8]!=b'BSDIFF40' or int.from_bytes(patch[24:32],'little')!=count:raise PatchError('차분 출력 크기가 다릅니다.')
                    block=bsdiff4.patch(old,patch)
                    if len(block)!=count or hashlib.sha256(block).hexdigest()!=op[6]:raise PatchError('차분 복원 결과가 다릅니다.')
                    write(block)
                elif kind == 'zero':
                    while count:
                        size = min(count, CHUNK)
                        write(bytes(size))
                        count -= size
                else:
                    f = src if kind == 'copy' else payload
                    f.seek(offset)
                    while count:
                        block = f.read(min(count, CHUNK))
                        if not block:
                            raise PatchError('입력 파일이 중간에 끝났습니다.')
                        write(block)
                        count -= len(block)
            dst.flush()
            os.fsync(dst.fileno())
        if written != m['target_bytes'] or digest.hexdigest() != m['target_sha256']:
            raise PatchError('생성 결과가 검증된 H3VR2 한글패치와 다릅니다. 설치를 중단했습니다.')
        # A concurrent process must not replace an existing user file.
        if output.exists():
            raise PatchError('결과 경로에 파일이 생겨 덮어쓰기를 중단했습니다.')
        temp.rename(output)
        say('완료: 결과 SHA-256이 새 버전 PC 검증본과 일치합니다.')
        return output
    finally:
        if temp.exists():
            temp.unlink()

class Adb:
    def __init__(self, executable, serial=None):
        self.executable = str(executable)
        self.serial = serial

    def run(self, *args, timeout=180, check=True):
        cmd = [self.executable] + (['-s', self.serial] if self.serial else []) + list(args)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        started = time.monotonic()
        try:
            while True:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(cmd, timeout)
                try:
                    output, _ = p.communicate(timeout=min(15, remaining))
                    break
                except subprocess.TimeoutExpired:
                    say(f'파일 검사/전송 진행 중... {int(time.monotonic() - started)}초')
        except BaseException:
            p.kill()
            p.communicate()
            raise
        if check and p.returncode:
            raise PatchError('ADB 작업 실패: ' + output.strip())
        return output.strip(), p.returncode

    def shell(self, *args, **kwargs):
        return self.run('shell', ' '.join(shlex.quote(str(x)) for x in args), **kwargs)

    def exists(self, path):
        return self.shell('test', '-e', path, check=False)[1] == 0

    def hash(self, path, missing_ok=False):
        if missing_ok and not self.exists(path):
            return None
        out, _ = self.shell('sha256sum', path, timeout=180)
        if not re.match(r'^[0-9a-fA-F]{64}\s', out):
            raise PatchError('기기 파일의 체크섬을 읽지 못했습니다: ' + path)
        return out.split()[0].lower()

# H3VR2-specific persistent, journalled installation engine.
import msvcrt
STORAGE=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'ZECOLE/H3VR2/Quest'

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.new')
    with temp.open('w',encoding='utf8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    temp.replace(path)

@contextlib.contextmanager
def operation_lock(work):
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    with (work/'operation.lock').open('a+b') as f:
        f.seek(0,2)
        if f.tell()==0:f.write(b'0');f.flush()
        f.seek(0)
        try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise PatchError('다른 설치 또는 복구 작업이 진행 중입니다.')
        try:yield
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def paths(m):
    main='/sdcard/Android/obb/'+m['package']+'/'+m['main_name']
    return main,main+m['backup_suffix']

def known_hashes(m):return {m['source_sha256'],m['target_sha256'],*m.get('compatible_previous',{})}

def model_supported(m,model):
    # Model gate only narrows the device family; the game version, APK and data hashes below decide installability.
    pattern=m.get('supported_model_regex')
    return model in m['supported_models'] or bool(pattern and re.fullmatch(pattern,model))

def version_check(adb,m):
    model=adb.shell('getprop','ro.product.model')[0].strip()
    if not model_supported(m,model):raise PatchError(f'지원하지 않는 기기입니다: {model or "모델명 확인 불가"}. 이번 배포판은 Quest 3 / Quest 3S용입니다.')
    text=adb.shell('dumpsys','package',m['package'])[0]
    match=re.search(r'\bversionCode=(\d+)',text)
    name=re.search(r'\bversionName=([^\s]+)',text)
    if not name or name.group(1)!=m['version_name'] or not match or int(match.group(1))!=m['version_code']:raise PatchError(f'지원 게임은 H3VR2 Quest {m["version_name"]} / 빌드 {m["version_code"]}입니다. 게임을 최신 버전으로 업데이트했는지 확인해 주세요. 다른 버전은 변경하지 않습니다.')
    locations=adb.shell('pm','path',m['package'])[0].splitlines()
    if len(locations)!=1 or not locations[0].startswith('package:'):raise PatchError('게임 APK 구성이 달라 중단합니다.')
    if adb.hash(locations[0][8:])!=m['source_apk_sha256']:raise PatchError('게임 APK가 검증된 버전과 다릅니다. 변경하지 않습니다.')

def stopped(adb,m):
    if adb.shell('pidof',m['package'],check=False)[0].strip():raise PatchError('게임이 실행 중입니다. 게임을 종료하고 다시 확인해 주세요.')

def save_receipt(work,m,current,backup):
    old=Path(work)/'installation.json'
    if old.exists():
        raw=old.read_bytes();history=Path(work)/'history';history.mkdir(exist_ok=True)
        saved=history/('receipt-'+hashlib.sha256(raw).hexdigest()[:16]+'.json')
        if not saved.exists():saved.write_bytes(raw)
    atomic_json(old,{'game':m['game'],'release':m['release'] if current==m['target_sha256'] else None,'patch_version':m['release'] if current==m['target_sha256'] else None,'tool_build':m['tool_build'],'platform':m['platform'],'version_code':m['version_code'],'state':'installed' if current==m['target_sha256'] else 'restored','installed_sha256':current,'original_sha256':m['source_sha256'],'device_original_backup':backup,'pc_original_backup':str(Path(work)/'original.hdog'),'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    atomic_json(Path(work)/'distribution-manifest.json',m)

def phase(work,j,value):
    j['phase']=value;j['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    atomic_json(Path(work)/'transaction.json',j);say(value_labels.get(value,value))
value_labels={'prepared':'설치 작업을 기록합니다.','transferring':'Quest로 파일을 전송합니다…','staged_verified':'전송 파일 검증 완료','swapping':'게임 파일을 교체합니다…','complete':'작업 결과 검증 완료','rolled_back':'직전 상태로 복구했습니다.','abandoned':'중단된 전송을 정리했습니다.'}

def _recover(adb,m,work):
    file=Path(work)/'transaction.json'
    if not file.exists():return
    j=json.loads(file.read_text(encoding='utf8'))
    if j.get('phase') in ('complete','rolled_back','abandoned'):return
    main,backup=paths(m);token=j.get('id','')
    if not re.fullmatch('[a-f0-9]{12}',token) or j.get('main')!=main or j.get('backup')!=backup or j.get('pending')!=main+'.zecole-pending-'+token or j.get('before_sha256') not in known_hashes(m) or j.get('after_sha256') not in known_hashes(m) or j.get('source_sha256')!=m['source_sha256']:
        raise PatchError('이전 작업 기록을 안전하게 해석할 수 없습니다. 기록과 파일을 보존했습니다.')
    version_check(adb,m);stopped(adb,m)
    current=adb.hash(main,missing_ok=True);original=adb.hash(backup,missing_ok=True)
    if original not in (None,m['source_sha256']):raise PatchError('원본 백업이 달라 자동 복구를 중단합니다.')
    if current==j['after_sha256'] and original==m['source_sha256']:
        save_receipt(work,m,current,backup);phase(work,j,'complete');cleanup_owned(adb,m,j);return
    if current==j['before_sha256']:
        # Recorded pending path was checked absent before the operation and is owned by it.
        if adb.exists(j['pending']):adb.shell('rm',j['pending'])
        phase(work,j,'abandoned');return
    retired=j.get('retired')
    if current is None and retired in (backup,main+'.zecole-retired-'+token) and adb.hash(retired,missing_ok=True)==j['before_sha256']:
        if retired==backup:adb.shell('cp',backup,main,timeout=900)
        else:adb.shell('mv',retired,main)
        if adb.hash(main)!=j['before_sha256']:raise PatchError('자동 복구 결과가 일치하지 않습니다.')
        # The pending path was checked absent before this operation, so whatever is there now is ours.
        if adb.exists(j['pending']):adb.shell('rm',j['pending'])
        phase(work,j,'rolled_back');say('중단된 파일 교체를 직전 상태로 복구했습니다.');return
    raise PatchError('이전 작업의 파일 상태가 불명확합니다. 자동 변경하지 않고 백업·로그를 보존했습니다.')

def cleanup_owned(adb,m,j):
    main,backup=paths(m)
    retired=j.get('retired')
    if retired==main+'.zecole-retired-'+j['id'] and adb.hash(retired,missing_ok=True)==j['before_sha256']:
        adb.shell('rm',retired)
    if adb.hash(j['pending'],missing_ok=True)==j['after_sha256']:adb.shell('rm',j['pending'])

def _owned_records(m,work):
    """Finished transaction records (current and history) whose paths are exactly this engine's own names."""
    main,backup=paths(m);work=Path(work);files=[work/'transaction.json',*sorted((work/'history').glob('transaction-*.json'))]
    for file in files:
        try:j=json.loads(file.read_text(encoding='utf8'))
        except (OSError,ValueError):continue
        token=j.get('id','') if isinstance(j,dict) else ''
        if not isinstance(token,str) or not re.fullmatch('[a-f0-9]{12}',token):continue
        if j.get('main')!=main or j.get('backup')!=backup or j.get('pending')!=main+'.zecole-pending-'+token:continue
        if j.get('phase') not in ('complete','rolled_back','abandoned'):continue
        yield j

def sweep_owned(adb,m,work):
    """Remove leftover pending/retired copies from earlier interrupted runs. Never touches the game file or the original backup."""
    main,backup=paths(m);freed=0
    for j in _owned_records(m,work):
        pending=j['pending'];retired=main+'.zecole-retired-'+j['id']
        if adb.exists(pending):
            # complete: the verified copy was renamed into place, so a leftover must still match it.
            # rolled_back/abandoned: the path was checked absent before the operation; any file there is ours.
            if j['phase']!='complete' or adb.hash(pending)==j['after_sha256']:adb.shell('rm',pending);freed+=1
        if j.get('retired')==retired and adb.exists(retired) and adb.hash(retired)==j['before_sha256']:
            adb.shell('rm',retired);freed+=1
    if freed:say(f'이전에 중단된 작업이 남긴 임시 파일 {freed}개를 정리했습니다.')

def prune_generated(m,work):
    """Keep only the current version's generated output on the PC."""
    root=Path(work)/'generated'
    if not root.is_dir():return
    for child in root.iterdir():
        if child.is_dir() and re.fullmatch('[a-f0-9]{64}',child.name) and child.name!=m['target_sha256']:
            shutil.rmtree(child,ignore_errors=True)

def space_check(adb,m,work,install):
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    # PC: one original plus one generated output, optional pull staging, with 1 GiB margin.
    original=work/'original.hdog';generated=work/'generated'/m['target_sha256']/m['main_name']
    required=(0 if original.is_file() else m['source_bytes'])+(m['target_bytes'] if install and not generated.is_file() else 0)+1024**3
    if shutil.disk_usage(work).free<required:raise PatchError(f'PC에 최소 {required/1024**3:.1f} GiB 여유 공간이 필요합니다.')
    text=adb.shell('df','-k','/sdcard')[0]
    try:free=int(text.splitlines()[-1].split()[3])*1024
    except (ValueError,IndexError):raise PatchError('Quest 여유 공간을 확인하지 못했습니다.')
    device_required=max(m['source_bytes'],m['target_bytes'])+512*1024**2
    if free<device_required:raise PatchError(f'Quest에 최소 {device_required/1024**3:.1f} GiB 여유 공간이 필요합니다.')
    say(f'작업 공간 확인 완료 · PC 추가 필요 {required/1024**3:.1f} GiB / Quest {device_required/1024**3:.1f} GiB')

def pull_verified(adb,remote,local,expected):
    local=Path(local)
    if local.exists():
        if sha256(local)!=expected:raise PatchError('기존 PC 원본 백업이 다릅니다. 덮어쓰지 않습니다.')
        return
    temp=local.with_name(local.name+'.pull-'+uuid.uuid4().hex[:12])
    try:
        adb.run('pull',remote,str(temp),timeout=900)
        if sha256(temp)!=expected:raise PatchError('내려받은 원본 백업의 체크섬이 다릅니다.')
        temp.rename(local)
    finally:temp.unlink(missing_ok=True)

def legacy_original(adb,m,current):
    if current not in m.get('legacy_builds',{}):return None
    for path in m.get('legacy_original_paths',[]):
        if adb.hash(path,missing_ok=True)==m['source_sha256']:return path
    return None

def migrate_legacy_backup(adb,m,work,current):
    main,backup=paths(m)
    if adb.exists(backup):return
    original=legacy_original(adb,m,current)
    if not original:raise PatchError('유효한 원본 백업을 확인하지 못했습니다. 기존 파일과 기록을 보존합니다.')
    version_check(adb,m);stopped(adb,m);space_check(adb,m,work,False)
    work=Path(work);record=work/'migration.json';pending=backup+'.migration-pending'
    expected={'source':original,'destination':backup,'pending':pending,'original_sha256':m['source_sha256'],'current_sha256':current}
    if record.exists():
        saved=json.loads(record.read_text(encoding='utf8'))
        if any(saved.get(k)!=v for k,v in expected.items()):raise PatchError('이전 백업 이전 기록이 달라 중단합니다.')
    elif adb.exists(pending):raise PatchError('소유를 확인할 수 없는 백업 임시 파일이 있습니다.')
    else:atomic_json(record,dict(expected,status='prepared'))
    pull_verified(adb,original,work/'original.hdog',m['source_sha256'])
    if adb.exists(pending):
        if adb.hash(pending)!=m['source_sha256']:raise PatchError('중단된 백업 파일이 불완전합니다. 자동 삭제하지 않고 보존했습니다.')
    else:adb.shell('cp',original,pending,timeout=900)
    if adb.hash(pending)!=m['source_sha256']:raise PatchError('백업 이전 체크섬 오류')
    version_check(adb,m);stopped(adb,m)
    if adb.hash(main)!=current or adb.exists(backup):raise PatchError('백업 이전 중 파일 상태가 변경되었습니다.')
    adb.shell('mv',pending,backup)
    if adb.hash(backup)!=m['source_sha256']:raise PatchError('이전한 원본 백업 검증 실패')
    atomic_json(record,dict(expected,status='complete'))
    say('검증된 시험본 원본 백업과 설치 기록을 새 저장 형식으로 이전했습니다.')

def transact(adb,m,work,action,root):
    work=Path(work);_recover(adb,m,work);version_check(adb,m);stopped(adb,m)
    sweep_owned(adb,m,work);prune_generated(m,work)
    main,backup=paths(m);current=adb.hash(main,missing_ok=True);saved=adb.hash(backup,missing_ok=True)
    desired=m['target_sha256'] if action=='install' else m['source_sha256']
    if current not in known_hashes(m):raise PatchError('알 수 없거나 업데이트된 파일입니다. 변경하지 않습니다.')
    if saved not in (None,m['source_sha256']):raise PatchError('기기 원본 백업이 달라 중단합니다.')
    if current!=m['source_sha256'] and saved is None:
        migrate_legacy_backup(adb,m,work,current);saved=adb.hash(backup)
    if current==desired:
        if current!=m['source_sha256'] and not (work/'original.hdog').exists():
            space_check(adb,m,work,False);pull_verified(adb,backup,work/'original.hdog',m['source_sha256'])
        if current!=m['source_sha256'] and (work/'original.hdog').exists() and sha256(work/'original.hdog')!=m['source_sha256']:raise PatchError('PC 원본 백업 검증 실패')
        save_receipt(work,m,current,backup);say('동일한 파일 검증 완료 · 설치 기록을 확인했습니다.');return
    space_check(adb,m,work,action=='install')
    pull_verified(adb,main if current==m['source_sha256'] else backup,work/'original.hdog',m['source_sha256'])
    if action=='install':output=build(work/'original.hdog',work/'generated'/m['target_sha256']/m['main_name'],root)
    token=uuid.uuid4().hex[:12];pending=main+'.zecole-pending-'+token;retired=backup if saved is None else main+'.zecole-retired-'+token
    if adb.exists(pending) or (retired!=backup and adb.exists(retired)):raise PatchError('작업 파일 이름이 충돌하여 중단했습니다.')
    j={'id':token,'action':action,'main':main,'backup':backup,'pending':pending,'retired':retired,'before_sha256':current,'after_sha256':desired,'source_sha256':m['source_sha256'],'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    old=work/'transaction.json'
    if old.exists():
        history=work/'history';history.mkdir(exist_ok=True)
        (history/('transaction-'+uuid.uuid4().hex+'.json')).write_bytes(old.read_bytes())
    phase(work,j,'prepared');phase(work,j,'transferring')
    if action=='install':adb.run('push',str(output),pending,timeout=900)
    else:adb.shell('cp',backup,pending,timeout=900)
    adb.shell('chmod','0666',pending)
    if adb.shell('stat','-c','%a',pending)[0].strip()!='666':raise PatchError('기기 파일 권한을 확인하지 못했습니다.')
    if adb.hash(pending)!=desired:raise PatchError('전송 파일 검증 실패. 다음 실행에서 기록에 따라 복구합니다.')
    phase(work,j,'staged_verified')
    version_check(adb,m);stopped(adb,m)
    if adb.hash(main,missing_ok=True)!=current or adb.hash(backup,missing_ok=True)!=saved:raise PatchError('교체 직전 게임 파일이 변경되어 중단했습니다.')
    stopped(adb,m);phase(work,j,'swapping')
    try:
        adb.shell('mv',main,retired);adb.shell('mv',pending,main)
        if adb.hash(main)!=desired:raise PatchError('교체 후 검증 실패')
    except BaseException:
        try:_recover(adb,m,work)
        except Exception as recovery:say('자동 복구 보류: '+str(recovery))
        raise
    save_receipt(work,m,desired,backup);phase(work,j,'complete')
    try:cleanup_owned(adb,m,j)
    except Exception:say('임시 파일 정리를 마치지 못했습니다. 다음 실행 때 기록을 확인해 정리합니다.')
    say('설치 완료' if action=='install' else '원본 복구 완료')

def recover(adb,m,work):
    with operation_lock(STORAGE/'engine'),operation_lock(Path(work)/'engine'):
        _recover(adb,m,work);sweep_owned(adb,m,work)

def install(adb,m,work,root=ROOT):
    verified,_=load_release(root)
    if any(verified[k]!=m[k] for k in ('source_sha256','target_sha256','source_bytes','target_bytes','package','version_code','version_name')):raise PatchError('메모리와 배포 파일의 검증 정보가 다릅니다.')
    with operation_lock(STORAGE/'engine'),operation_lock(Path(work)/'engine'):
        transact(adb,m,work,'install',root)

def restore(adb,m,work):
    with operation_lock(STORAGE/'engine'),operation_lock(Path(work)/'engine'):
        transact(adb,m,work,'restore',ROOT)


def main():
    parser=argparse.ArgumentParser(description='H3VR2 Quest 배포판 검증/유지보수')
    parser.add_argument('command',choices=['build','verify','status','install','restore'])
    parser.add_argument('--root',type=Path,default=Path(__file__).parent/'bundle');parser.add_argument('--adb');parser.add_argument('--serial');parser.add_argument('--source',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args();m,_=load_release(args.root)
    if args.command=='verify':say('배포 데이터 무결성 정상');return
    if args.command=='build':build(args.source,args.output,args.root);return
    if not args.adb or not args.serial:parser.error('--adb와 --serial이 필요합니다.')
    adb=Adb(args.adb,args.serial);work=STORAGE/re.sub('[^A-Za-z0-9_.-]','_',args.serial)/str(m['version_code'])
    with operation_lock(STORAGE),operation_lock(work):
        version_check(adb,m)
        if args.command=='status':say(json.dumps({'main_sha256':adb.hash(paths(m)[0],missing_ok=True),'backup_sha256':adb.hash(paths(m)[1],missing_ok=True)},indent=2));return
        if args.command=='install':install(adb,m,work,args.root)
        else:restore(adb,m,work)
if __name__=='__main__':main()
