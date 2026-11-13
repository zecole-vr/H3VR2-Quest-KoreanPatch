# 출처 및 라이선스

제작자: 제콜 (ZECOLE) · https://www.youtube.com/@zecole
Hot Dogs, Horseshoes & Hand Grenades 2 / RUST LTD.의 비공식 한국어 패치입니다.
원본 게임 자산과 상표의 권리는 RUST LLC. 및 각 권리자에게 있습니다.
원본 APK·게임 전체·게임 음성을 배포하지 않습니다. 사용자 보유 원본과 차분으로 결과를 재생성합니다.
별도의 게임 자산 재배포 허락을 확보했다고 주장하지 않습니다.

번역은 게임 영어 문구를 바탕으로 제콜의 요청과 검수를 통해 작성했습니다.
초안·텍스처 작업에 Codex/Claude와 이미지 생성 도구가 사용되었습니다.
포어미트 대화는 원음 대사의 정확한 자막이 아닌 응답 종류의 상황 요약입니다.
외부 커뮤니티 한글패치 번역문을 차용한 것으로 표시하지 않습니다.

## 글꼴
NanumGothic Regular — Version 3.020;PS 1;hotconv 1.0.57;makeotf.lib2.0.21895
Copyright (c) 2010, NHN Corporation. SIL Open Font License 1.1.
공식 공개 소스: https://github.com/google/fonts/tree/main/ofl/nanumgothic
사용한 TTF SHA256: 76f45ef4a6bcff344c837c95a7dcc26e017e38b5846d5ae0cdcb5b86be2e2d31
기존에 받은 TTF의 정확한 소스 커밋은 기록되지 않았으며 위 해시로 파일을 식별합니다.
게임의 한글 글리프·SDF 아틀라스·번역 텍스처 제작에 사용했습니다.
독립적인 수정 TTF는 배포하지 않습니다. 전문: licenses/NanumGothic-OFL.txt.
런처는 Windows Segoe UI / 맑은 고딕을 사용하며 해당 시스템 글꼴 파일은 배포하지 않습니다.

## 설치기
공통 HTML/WebView 런처 20261106.10, PAYDAY Quest 0.1.3에서 사용된 로컬 템플릿.
ITR2 Quest 1.2.5 기반이며 정확한 파일 해시와 차이는 maintenance/template-provenance.json에 기록합니다.
MIT는 설치기 코드에만 적용합니다. 번역문·게임 자산·폰트·차분 전체에 일괄 적용하지 않습니다.
Python 3.10.11, PyInstaller 6.22.3, pywebview 6.1, pythonnet 3.1.0,
clr_loader, cffi, pycparser, bottle, proxy_tools, typing_extensions, packaging,
setuptools 및 포함 vendor 라이선스 전문은 licenses/ 아래에 있습니다.
차분 복원: bsdiff4 1.4.0 — https://pypi.org/project/bsdiff4/1.4.0/
Copyright (c) 2011-2026, Ilan Schnell 및 원본 bsdiff 저작권 고지 포함.
수정하지 않은 라이브러리를 포함합니다. 전문: licenses/bsdiff4/LICENSE.
This product includes software developed by the OpenSSL Project for use in the OpenSSL Toolkit.
This product includes cryptographic software written by Eric Young and software written by Tim Hudson.

WebView2 SDK 고지: licenses/WebView2-LICENSE.txt 및 WebView2-NOTICE.txt.
WebView2 Runtime과 .NET Framework는 사용자 Windows에 설치된 것을 사용합니다.
해당 런타임은 이 EXE에 포함하지 않습니다.

## 첫 실행 연결 도구
Google Android SDK Platform Tools 37.0.0 (ADB)
https://dl.google.com/android/repository/platform-tools_r37.0.0-win.zip
SHA256: 4fe305812db074cea32903a489d061eb4454cbc90a49e8fea677f4b7af764918
약관: https://developer.android.com/studio/terms
기존 ADB가 없을 때 동의 후 공식 파일을 내려받아 체크섬을 검증합니다.
다운로드한 NOTICE.txt를 지속 저장소에 함께 보관합니다. EXE에 ADB 바이너리는 포함하지 않습니다.

## 배너
RUST LTD. 공식 H3VR2 프레스킷: https://rustltd.com/presskit/h3vr2/
이미지: https://rustltd.com/games/h3vr2/keyart/keyart_fg.png
© 2026 RUST LLC. 게임 식별용 비공식 설치기 배너입니다.
별도 권리 양도나 공식 승인을 주장하지 않습니다.
제목·플랫폼·상태·버튼·링크는 실제 UI 요소입니다.
