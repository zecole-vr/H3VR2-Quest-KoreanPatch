# 재현 및 유지보수

- 공통 UI: 로컬 `zecole-common-quest-launcher-20261106.10`, PAYDAY Quest 0.1.3 검증본.
- 원래 계보: ITR2 Quest v1.2.5, commit `9245d8022655eaa1eba420cfd16facdc7a89e419`.
- 로컬 템플릿 자체를 위 Git 커밋과 동일하다고 간주하지 않습니다. 정확한 경로/파일 SHA256은 template-provenance.json 참조.
- H3VR2 게임 대상: Quest standalone. 설치 도구 호스트: Windows x64.
- 번역 버전 0.2.0 / 설치기 0.2.0 / 빌드 20261114.1 / 원천 통합 시험본 onboard-npc-captions-v44 (final-dialog-v43 + 포어미트 구출·허브 상층 자막).
- 0.1.0: 빌드 20261113.4 / final-dialog-v43. 0.1.0 릴리스 파일과 해시는 그대로 보존합니다.

## EXE 빌드

Windows Python 3.10.11 x64에서 `requirements-build.txt`의 고정 버전을 설치합니다.
이 저장소에는 원본 게임과 84MB 차분 바이너리를 넣지 않습니다.
동일 릴리스의 `H3VR2_Quest_Windows_Source_v0.2.0.zip`에는 빌드에 필요한 `bundle/data`가 포함됩니다.
압축을 푼 뒤 다음 명령으로 빌드합니다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-build.txt
.venv/Scripts/python.exe -m unittest test_h3vr2.H3VR2Tests test_launcher
.venv/Scripts/python.exe -m PyInstaller --noconfirm H3VR2.spec
```

EXE 경로: `dist/H3VR2_Quest_Windows_v0.2.0.exe`.
`--self-check`는 실제 WebView/도움말/차분 모듈/현재 기기 상태를 검사하되 게임 파일을 쓰지 않습니다.
로컬 개발 환경이 없는 새 Windows 설치에서의 시험과 PATH에서 Python을 제외한 실행 시험은 구분합니다.

## 데이터

`bundle/manifest.json`의 원본/결과/원본 APK/recipe/payload SHA256이 모두 고정됩니다.
HDOG 2,561개 섹션을 비교하여 같은 섹션은 원본 복사, 달라진 섹션은 최대 8MiB 단위 BSDIFF40 차분으로 구성했습니다.
오디오 섹션은 모두 원본 복사입니다. 원본에서 결과를 재생성하여 최종 v44 전체 SHA256과 비교했습니다.
자세한 결과는 delta-audit.json 참조. 게임 원본을 재배포하지 않고 사용자가 보유한 정확한 원본을 요구합니다.

## 설치 안전성

게임 버전명/코드/원본 APK와 데이터 해시, 게임 종료 여부, 공간을 확인합니다.
PC·기기 원본 백업, 전송 임시 파일, 단계별 JSON 기록을 보존하고 교체 직전 다시 확인합니다.
UI 중복 요청 제한과 설치 엔진 프로세스 잠금을 별도로 둡니다.
0.1.0(v43) 설치본은 `compatible_previous`로 등록되어 기존 원본 백업을 그대로 쓰며 업데이트합니다.
기존 v42 시험본은 알려진 원본 경로의 해시까지 확인한 뒤 백업을 이전합니다.
불명확한 파일/이전 기록은 자동 정리하지 않습니다.

## 공개 전후

태그·EXE/Source 파일명·내부 버전·체크섬·최신 자산 정규식을 함께 검사합니다.
릴리스는 게시 상태(draft=false)이며 저장소는 비공개입니다. 정식 공개 시 안내 문구와 검증 상태를 갱신하고
인증 없는 경로에서 다운로드/해시/실행/최신 버전 인식을 확인해야 합니다.

실기 시험은 빌드 20261113.2의 런처 작업 경로로 수행했습니다. 최종 .4은 설치 로직/차분이 같으며 검증 문서, 설정 정보, 시험본 호환 목록을 정리한 빌드입니다.

최종 .4에서 원본 백업을 이전하는 시험본의 이름을 고정 문자열 대신 해당 해시의 등록된 빌드명으로 표시하도록 수정했습니다. 설치/복구 엔진과 차분은 실기 시험 때와 동일합니다.
