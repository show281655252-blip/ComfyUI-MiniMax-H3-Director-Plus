# ComfyUI MiniMax H3 Director Plus

MiniMax H3 Director에 장면 타임라인, 장면별 승인, Motion Context 연결, HyperFlow 스케줄 및 `.ext` 프로젝트 저장을 추가하는 비공식 프로젝트입니다.

**현재 버전: 0.1.0-rc1 — 버전 고정 패치 배포 후보.** 독립 커스텀 노드가 아니며, 원본 업데이트와 무관하게 동작하는 완성 배포판이 아닙니다.

## Git clone으로 설치

먼저 아래 의존성 버전과 모델을 준비하고 ComfyUI를 종료하세요. **Portable 폴더 안에서** 다음 명령을 실행합니다. 이 폴더는 `ComfyUI`와 `python_embeded`가 함께 있는 위치입니다.

```powershell
git clone https://github.com/show281655252-blip/ComfyUI-MiniMax-H3-Director-Plus.git
cd ComfyUI-MiniMax-H3-Director-Plus
.\install_windows.bat
```

ZIP은 자동으로 검증·해제되며, 설치가 성공하면 저장소의 `workflows/Director_Long_Video_HyperFlow.json`이 준비됩니다. Windows 실행 파일을 더블클릭해도 됩니다.

일반 Python/venv 설치에서는 ComfyUI용 Python을 활성화한 뒤 아래처럼 실행합니다. 경로는 자신의 환경에 맞게 바꾸세요.

```powershell
python install.py check --comfy "D:\ComfyUI_windows_portable\ComfyUI"
python install.py install --comfy "D:\ComfyUI_windows_portable\ComfyUI"
```

`git clone`만으로 모델이나 원본 커스텀 노드가 자동 설치되지는 않습니다. 이 저장소는 `custom_nodes`에 넣어 자동 로드하는 독립 노드가 아닙니다. `git pull`은 배포 파일만 업데이트하며 패치는 다시 검사·설치해야 합니다.

## 필요한 원본 버전

각 원본 저장소의 설치 안내에 따라 Python 의존성을 설치하고 아래 커밋을 사용하세요. 모델 파일도 별도로 필요합니다.

| 저장소 | 커밋 |
| --- | --- |
| ComfyUI-DaSiWa-Nodes 0.4.49 | `f864613b687192b2000fdc5164402dd8e3fc60bc` |
| ComfyUI_MiniMax_H3_Extender | `939f773d55006f2200063696cd6e221cd82b4771` |
| ComfyUI-Hyperflow | `b4bd9cf7ea3625ad4ffdc994608a2d736b10e890` |

기존에 수정한 커스텀 노드가 있으면 먼저 백업하세요. 설치 도구는 일치하지 않는 버전을 덮어쓰지 않습니다.

## 수동 다운로드

- [배포 패키지 ZIP](MiniMax-Director-Distribution-0.1.0-rc1.zip)
- [SHA-256 체크섬](MiniMax-Director-Distribution-0.1.0-rc1.zip.sha256)
- [검증 범위와 남은 작업](VALIDATION.md)

ZIP에는 수정 소스, 설치·복구 도구, 의존성 커밋과 파일 해시, 원본 라이선스, 공유용 예제 워크플로우와 설치 설명서가 포함되어 있습니다. 모델·개인 이미지·생성 영상·개인 프로젝트 캐시는 포함하지 않습니다.

## 설치 개요

1. ZIP을 다운로드하고 압축을 풉니다. 이 GitHub 저장소 자체를 `custom_nodes`에 설치하는 방식이 아닙니다.
2. 압축 안의 `README.md`와 `manifest.json`을 확인하고 DaSiWa, Extender, HyperFlow를 지정된 커밋으로 준비합니다.
3. ComfyUI를 종료한 후 압축을 푼 폴더에서 실행합니다. `python`은 ComfyUI에 사용하는 Python입니다.

```powershell
python manage.py --comfy "D:\ComfyUI_windows_portable\ComfyUI" check
python manage.py --comfy "D:\ComfyUI_windows_portable\ComfyUI" install
```

설치 도구는 DaSiWa와 Extender의 지정 파일 9개를 추가·교체합니다. 알려진 버전만 허용하며, 다른 수정본은 덮어쓰지 않습니다. 설치 시 백업 및 복구 명령을 제공합니다. 원본을 업데이트하면 새 버전에 맞춘 패치가 필요합니다.

재시작 후 ZIP 안의 `workflows/Director_Long_Video_HyperFlow.json`을 열고 자신의 Ref2VA 모델·텍스트 인코더·video/audio VAE·HyperFlow 파일을 선택하세요. 예제는 긴 영상 전용 9개 노드로 구성되어 있으며 개인 워크플로우의 Ollama 자동화는 포함하지 않습니다.

## 사용 흐름

장면 프롬프트·시드·길이 설정 → 생성 → 미리보기 → 승인 → 다음 장면 설정 → 생성 순서입니다. 승인 자체는 다음 생성을 실행하지 않습니다. `.ext`에는 Director 설정과 참조 미디어, 존재하는 장면 캐시를 저장하며 모델은 포함하지 않습니다.

설치·복구 테스트, 별도 CPU 서버의 노드 등록, 실제 `.ext` 저장·불러오기는 확인했습니다. 이 축소 예제로 실제 GPU 영상 생성·2장면 연결·재생 성능을 검증하는 작업과 독립 확장으로 완전히 분리하는 작업은 남아 있습니다.

## 원본과 라이선스

- [ComfyUI-DaSiWa-Nodes](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes): GPL-3.0
- [ComfyUI MiniMax H3 Extender](https://github.com/tritant/ComfyUI_MiniMax_H3_Extender): Apache-2.0
- [ComfyUI-Hyperflow](https://github.com/Saganaki22/ComfyUI-Hyperflow): 외부 의존성, 코드·가중치 미포함

새 통합 코드와 도구는 [GPL-3.0](LICENSE)으로 제공합니다. 원본 Extender 부분의 Apache-2.0 고지와 조건은 유지됩니다. 수정 내역과 각 원본의 전체 라이선스는 ZIP 안의 `NOTICE.md` 및 `licenses/`에 포함되어 있습니다. 원본 개발자의 공식 배포판이 아닙니다.
