# MiniMax H3 Director Plus — 0.2.0a2 (alpha)

ComfyUI용 MiniMax H3 장면 타임라인·긴 영상(Ref2VA + Motion Context) 커스텀 노드입니다. 원본 DaSiWa·Extender 파일을 수정하지 않는 독립 노드이며, 필요한 원본 코드 일부를 라이선스 고지와 함께 내부에 포함합니다.

> 비공식 알파 버전입니다. 2장면 연속 생성(승인 → Motion Context → 합치기)과 `.ext` 저장·복원을 GPU에서 확인했습니다. 검증 범위는 아래 [검증 현황](#검증-현황)을 참고하세요.
> 이전 0.1.0-rc1(버전 고정 패치 설치 방식)은 [`v0.1.0-rc1` 태그](../../tree/v0.1.0-rc1)에서 받을 수 있습니다 (`git checkout v0.1.0-rc1`).

## 설치 (git clone)

ComfyUI를 종료한 뒤 `ComfyUI/custom_nodes` 폴더에서:

```powershell
git clone https://github.com/show281655252-blip/ComfyUI-MiniMax-H3-Director-Plus.git
```

Portable 환경은 ComfyUI용 Python으로 의존성을 설치합니다 (`ComfyUI_windows_portable` 폴더에서):

```powershell
.\python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\ComfyUI-MiniMax-H3-Director-Plus\requirements.txt
```

PyTorch/torchaudio를 다른 버전으로 교체하지 말고 ComfyUI 배포본과 맞는 조합을 유지하세요. 설치 후 ComfyUI를 재시작하고 브라우저에서 Ctrl+F5를 누릅니다.

업데이트: `custom_nodes/ComfyUI-MiniMax-H3-Director-Plus`에서 `git pull`

## 필요한 것

- MiniMax H3를 지원하는 ComfyUI
- **ComfyUI-Hyperflow** 노드와 가중치 (예제 워크플로우용)
- Ref2VA 모델, MiniMax용 텍스트 인코더, video/audio VAE — 모델은 자동 다운로드하지 않습니다.

## 노드

- **MiniMax H3 Director Plus**: 레퍼런스·장면 타임라인·프롬프트(단일 편집기 + Prompt Forge)·시드 관리
- **Director Plus · Generate**: Motion Context와 HyperFlow SIGMAS로 장면 생성
- **Director Plus · Video Output**: 영상 저장 및 미리보기

## 사용법

1. `workflows/Director_Plus_HyperFlow.json`(또는 템플릿 목록의 이 노드 항목)을 불러와 모델 파일을 선택합니다.
2. 장면 카드에 프롬프트를 입력하고 **생성 / 실행** → 결과를 확인합니다.
3. 마음에 들면 장면 카드의 **승인** 체크박스를 클릭합니다. 다음 장면이 자동으로 선택되며, 편집한 뒤 다시 **생성 / 실행**합니다. (승인만으로는 생성되지 않습니다. 마지막 장면 뒤에 이어 가려면 **+ 장면 추가**)
   - 승인은 앞 장면부터 순서대로만 가능하며, 체크를 풀면 그 뒤 장면의 승인도 함께 풀립니다. 생성된 캐시는 남으므로 다시 체크하면 재생성 없이 승인됩니다.
   - 승인을 푼 장면의 프롬프트·시드·길이를 고치면 그 장면부터 다시 생성합니다.
   - 장면 타임라인의 **Clear**는 모든 장면을 지우고 빈 장면 1개로 새로 시작합니다(확인 창 표시). 긴 영상 설정은 유지되며, 저장한 .ext와 만든 영상 파일은 지워지지 않습니다.
4. **프로젝트 저장 (.ext)**로 장면 설정·레퍼런스·생성 캐시를 함께 보관하고, **프로젝트 불러오기**로 복원합니다. 모델과 전체 워크플로우 JSON은 별도로 보관하세요.

기존 영상 파일 뒤에 이어 붙이는 기능은 제공하지 않습니다(처음부터 생성한 장면끼리 이어갑니다).

캐시 위치: `ComfyUI/user/director_plus/cache` (원본 Extender 캐시와 분리)

### Prompt Forge (선택)

프롬프트 도구 모음의 **Prompt Forge**로 아이디어 한두 문장에서 H3 프롬프트 초안을 LLM으로 작성할 수 있습니다. 초안을 확인한 뒤 **Apply to node**를 눌러야 프롬프트에 들어가며, 최근 3개 초안은 노드와 함께 워크플로우에 저장됩니다.

- 모델: `ComfyUI/models/llm`의 로컬 모델, Ollama(기본 `127.0.0.1:11434`), 또는 OpenAI 호환 서버. 서버 주소는 **Settings → Director Plus → H3 Forge**에서 지정합니다.
- 생성이 끝나면 LLM을 메모리에서 내린 뒤 영상 생성을 시작하므로 LLM과 영상 모델이 VRAM에 함께 올라가지 않습니다.
- 원본 DaSiWa의 Prompt Forge와는 API 경로·설정·저장 키가 분리되어 함께 설치해도 서로 간섭하지 않습니다.

## 기존 워크플로우 변환

0.1 패치의 Director 노드를 쓰던 워크플로우는 복사본으로 변환할 수 있습니다.

```powershell
python migrate_workflow.py "기존.json" "DirectorPlus_변환본.json"
```

원본은 덮어쓰지 않으며, Director 관련 노드 3종만 새 이름으로 바꿉니다. 프롬프트와 시드는 유지하고 장면 승인은 초기화합니다(캐시가 분리되므로 다시 생성 필요). 워크플로우의 다른 노드(Ollama, `MiniMaxH3DirectorGuide` 등 DaSiWa 노드)는 해당 커스텀 노드가 계속 필요합니다.

0.1 패치가 설치된 환경과도 다른 노드 이름·API 경로로 공존합니다. 0.1 패치가 원본에 적용한 변경은 당시 백업으로 별도 복구해야 합니다.

## 검증 현황

`v0.2.0a1` 기준, Windows ComfyUI Portable + 실제 GPU에서 확인한 내용입니다 (2026-09-26).

- 설치: `custom_nodes`에 git clone 후 ComfyUI 재시작 → 노드 3종 등록, 다른 커스텀 노드와 import 충돌 없음
- 기존 워크플로우 변환본: 누락 노드 0, 링크 오류 0, 브라우저에서 오류 없이 로드
- 2장면 긴 영상 (256×256, 장면당 1초, HyperFlow 8스텝, int8 모델):
  - 1장면 생성 39프레임(오디오 포함) → 승인 → 2장면 Motion Context 생성 → 합본 73프레임 · 24fps · AAC, 장면 경계 끊김 없음
  - `.ext` 저장 → 불러오기: 새 프로젝트 ID로 복원, 장면 설정·승인 상태·생성 캐시 유지
  - 복원한 프로젝트 재실행: 승인된 장면은 다시 샘플링하지 않고 캐시로 같은 영상 출력

아직 확인하지 않은 것: 고해상도·긴 장면(5초 이상), 3장면 이상, Full Batch 모드, Linux/macOS.

## 라이선스

원본 코드와 변경 내역은 [NOTICE.md](NOTICE.md), 고정한 원본 리비전은 [UPSTREAM.json](UPSTREAM.json)을 참고하세요. GPL-3.0 및 해당 원본의 Apache-2.0 고지를 유지합니다.
