# MiniMax H3 Director Plus — 0.2.0a2 (alpha)

ComfyUI용 MiniMax H3 장면 타임라인·긴 영상(Ref2VA + Motion Context) 커스텀 노드입니다. 원본 DaSiWa·Extender 파일을 수정하지 않는 독립 노드이며, 필요한 원본 코드 일부를 라이선스 고지와 함께 내부에 포함합니다.

### 레퍼런스 영상 해상도

영상 항목의 V/A/V+A 옆에서 Orig(기존 엔진 처리) 또는 0.83/0.65/0.52MP를 선택합니다. 비율을 유지하며 32픽셀 격자로 축소하고, 작은 영상은 키우지 않습니다. 오디오·프레임 수·출력 해상도는 바꾸지 않으며 결과의 세부 표현은 달라질 수 있습니다. A(소리만)에서는 숨겨집니다. 설정은 워크플로우와 `.ext`에 저장되며, 긴 영상에서 해상도를 바꾸려면 기존 장면 승인을 해제해야 합니다(기존 캐시는 삭제하지 않음).

### 긴 영상 LBH 업스케일

LBH 고해상도 보정의 참조 이미지·키프레임은 **픽셀 공간에서 크기를 변경한 후 Video VAE로 다시 인코딩**합니다. H3 잠재값을 bilinear로 직접 확대하면 격자 무늬와 잔상이 생길 수 있습니다. 원본 픽셀이 없는 RefMod/영상 문맥은 디코딩 후 재인코딩하며, 오디오와 프레임 위치는 유지합니다. 이 처리 변경 전의 LBH 캐시는 별도로 보존되며 새로 생성해야 합니다.

단일 영상의 기존 `MiniMaxH3ConditioningUpscale`은 `DirectorPlusConditioningMatchLatent`로 교체하고 `conditioning`, 확대 전 `base_latent`, 실제 LBH 출력 `target_latent`, Video `vae`, Director `guide`를 연결하세요. 이 노드는 실제 출력 격자에 맞추므로 LBH와 조건 확대의 반올림 차이도 방지합니다. Python 변경 적용에는 ComfyUI 재시작이 필요합니다.

`DirectorPlusGenerate`의 선택 입력 `lbh_enabled` / `lbh_scale`을 Settings의 LBH ON/OFF / 배율에 연결하면 긴 영상에도 LBH를 적용합니다. 기존 워크플로우는 입력이 없으면 OFF로 동작합니다. 기본 해상도로 전체 스텝 중 마지막 4스텝을 제외하고 샘플링한 뒤, denoised 잠재값을 LBH로 확대하고 마지막 4스텝을 고해상도에서 보정합니다(최소 5스텝 필요).

선택 입력 `lbh_full_first_pass`를 켜면 **8+4** 방식으로 동작합니다: 기본 해상도에서 스케줄을 끝까지 샘플링한 뒤 확대하고, 같은 스케줄의 마지막 4스텝으로 고해상도 보정을 합니다(기존 방식은 마지막 4스텝을 빼고 샘플링). 켜면 캐시가 분리됩니다.

### 긴 영상 오디오 재생성

`audio_regen_enabled`를 켜고 `audio_regen_model`에 **터보/HyperFlow를 적용하기 전의 기본 모델**(같은 Sigma Shift)을 연결하면, 장면마다 영상 잠재값을 0.5배로 줄여 오디오와 다시 합친 뒤 30스텝·denoise 0.5로 재샘플링하고 **오디오만** 교체합니다. 화면은 바뀌지 않고 대사 타이밍도 유지됩니다. 몇 스텝짜리 터보 모델로 만든 오디오의 잡음(험 등)을 줄이는 용도이며, 장면당 시간이 추가로 듭니다. 켜면 캐시가 분리됩니다.

`Comfyui_Minimax_h3_latent_Upscaler`와 `models/latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors`가 필요합니다. 다른 호환 모델은 `lbh_model_name`에 지정하세요. BF16, 시간 청크, 32px 정렬을 사용하며 실제 출력 크기는 정렬에 따라 배율 계산값과 조금 다를 수 있습니다. 오디오의 공간 크기는 변경하지 않습니다.

다음 장면은 저해상도 단계에서 이전 장면의 Motion Context를 축소해 사용하고, 고해상도 보정 단계에서는 이전 장면의 원래 고해상도 문맥을 사용합니다. LBH ON/OFF·배율·모델명이 바뀌면 캐시를 분리하고 승인을 초기화합니다. 기존 디스크 캐시는 삭제하지 않습니다. `.ext`에는 LBH 캐시 식별 정보가 저장되지만 실행 설정은 워크플로우에도 함께 저장해야 합니다. 고해상도 보정은 GPU 메모리와 생성 시간이 추가로 필요합니다.

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
- **ComfyUI-Hyperflow** 노드와 가중치 (예제 워크플로우용) — 원래 저장소(Saganaki22)가 사라져 호환 포크 [jalberty2018/ComfyUI-Hyperflow](https://github.com/jalberty2018/ComfyUI-Hyperflow)로 확인했습니다. 가중치: [drbaph/Hyperflow-Comfyui](https://huggingface.co/drbaph/Hyperflow-Comfyui) → `models/hyperflow/`
- Ref2VA 모델, MiniMax용 텍스트 인코더, video/audio VAE — 모델은 자동 다운로드하지 않습니다.

## 노드

- **MiniMax H3 Director Plus**: 레퍼런스·장면 타임라인·프롬프트(단일 편집기 + 프롬프트 작성 창)·시드 관리
- **Director Plus · Generate**: Motion Context와 HyperFlow SIGMAS로 장면 생성
- **Director Plus · Video Output**: 영상 저장 및 미리보기

## 사용법

1. `workflows/Director_Plus_HyperFlow.json`(또는 템플릿 목록의 이 노드 항목)을 불러와 모델 파일을 선택합니다.
2. 장면 카드에 프롬프트를 입력하고 **생성 / 실행** → 결과를 확인합니다.
3. 마음에 들면 장면 카드의 **승인** 체크박스를 클릭합니다. 다음 장면이 자동으로 선택되며, 편집한 뒤 다시 **생성 / 실행**합니다. (승인만으로는 생성되지 않습니다. 마지막 장면 뒤에 이어 가려면 **+ 장면 추가**)
   - 승인은 앞 장면부터 순서대로만 가능하며, 체크를 풀면 그 뒤 장면의 승인도 함께 풀립니다. 생성된 캐시는 남으므로 다시 체크하면 재생성 없이 승인됩니다.
   - 승인을 푼 장면의 프롬프트·시드·길이를 고치면 그 장면부터 다시 생성합니다.
   - 긴 영상에서는 장면 카드의 프롬프트가 생성에 쓰입니다(노드 아래쪽 Prompt는 단일 영상용). 카드에 직접 쓰거나 **✍ 프롬프트 작성**으로 넣으세요. 새로 추가하는 장면(「+ 장면 추가」·「초기화」)은 외부 프롬프트가 연결돼 있으면 ON, 아니면 OFF로 만들어집니다.
   - **전체 승인** / **전체 승인 해제**: 생성된 장면을 앞에서부터 한 번에 승인하거나(아직 생성되지 않은 장면에서 멈춤) 모든 승인을 한 번에 풉니다. 캐시는 유지됩니다.
   - 장면 타임라인의 **초기화**는 모든 장면을 지우고 빈 장면 1개로 새로 시작합니다(확인 창 표시). 긴 영상 설정은 유지되며, 저장한 .ext와 만든 영상 파일은 지워지지 않습니다.
4. **프로젝트 저장 (.ext)**로 장면 설정·레퍼런스·생성 캐시를 함께 보관하고, **프로젝트 불러오기**로 복원합니다. 모델과 전체 워크플로우 JSON은 별도로 보관하세요. `.ext`는 만들 때의 LBH·오디오 재생성 설정도 기억해서, 불러오면 워크플로우의 해당 설정을 자동으로 맞춥니다(캐시를 그대로 쓰기 위해). 승인된 장면이 있는데 설정이 달라진 채 생성하면, 모든 장면을 다시 만들지 않도록 오류로 멈추고 안내합니다.

기존 영상 파일 뒤에 이어 붙이는 기능은 제공하지 않습니다(처음부터 생성한 장면끼리 이어갑니다).

캐시 위치: `ComfyUI/user/director_plus/cache` (원본 Extender 캐시와 분리)

### 프롬프트 작성 창 (PromptDirector)

Director 노드 프롬프트 도구 모음과 긴 영상 장면 타임라인의 **✍ 프롬프트 작성** 버튼으로 엽니다. [ComfyUI-MinimaxH3-PromptDirector](https://github.com/Bokuwako/ComfyUI-MinimaxH3-PromptDirector)와 Ollama가 필요합니다. Writer·Freeze·Shot Builder 노드를 연결하지 않아도 됩니다.

- 구성은 MMH3 Studio의 디렉터 탭과 같습니다: 장면 설정(스타일·장르·렌즈·심도·조명·대사·환경음·음악·금지/필수 사항), Director 이미지별 레퍼런스 역할, 샷 카드(카메라·샷 전환, 몸 방향·시선, 행위, 대사), Ollama 모델·고급 설정, 브리프 확인, 프롬프트 작성, Prompt Freeze 부분 수정·이전 프롬프트. **💬 LLM과 대화하며 다듬기**: 결과 칸의 프롬프트를 두고 Ollama와 대화하면(무엇이 이상한지 적으면 원인 설명 + 고친 프롬프트 제안) 「결과 칸에 넣기」·「바로 적용」으로 반영합니다. 제안은 자동 적용되지 않고, 이전 프롬프트로 되돌릴 수 있으며, 창을 닫으면 Ollama 모델을 내립니다. 구성은 MMH3 Studio의 대화 편집(MIT)을 따릅니다.
- Director의 모드·길이·레퍼런스를 그대로 읽습니다. 영상 레퍼런스 분석과 V+A 소리 규칙(위 PromptDirector 연동)도 적용됩니다.
- 작성은 ComfyUI 대기열 밖에서 실행되며, 시작할 때 ComfyUI 모델을 내리고 끝나면 Ollama 모델도 내립니다. 영상 생성 중에는 작성할 수 없습니다.
- 결과를 확인한 뒤 **적용**을 누르면 단일 영상은 Director 프롬프트에, 긴 영상은 고른 장면 카드(기본: NEXT, 외부 프롬프트 OFF)에 들어갑니다.
- 처음 열 때 워크플로우의 Shot Settings·Shot Builder·Writer 노드 값을 가져옵니다. 창의 내용은 노드에 저장됩니다.

### ComfyUI-MinimaxH3-PromptDirector 연동

[ComfyUI-MinimaxH3-PromptDirector](https://github.com/Bokuwako/ComfyUI-MinimaxH3-PromptDirector)가 설치돼 있으면, 그 Prompt Writer의 `FOLLOW_DIRECTOR` 모드가 Director Plus 노드도 Director로 인식합니다. Writer가 Director Plus의 mode(REF2VA 등)·길이·레퍼런스 이미지를 읽어 그 모드 형식으로 프롬프트를 씁니다. PromptDirector 파일은 수정하지 않으며(실행 시 Director 탐색만 넓힘), 연동이 안 되면 콘솔에 경고가 나옵니다. 이 경우 Writer의 mode를 직접 지정하세요.

REF2VA에서 Director 타임라인에 영상 레퍼런스가 있으면, Writer가 쓰기 전에 그 영상(타임라인의 자르기 구간)을 0.5초 간격으로 최대 30장 뽑아 Writer의 Ollama 모델(`vision_model`을 고르면 그 모델)에 한 번 보여 주고, 카메라·시작 자세·시간순 동작·손 모양·표정·효과를 적은 동작 분석을 받습니다. Writer에는 원래 영상 이름만 넘어가던 자리에 이 분석과 「카메라·배경·조명·소품·동작은 영상에서, 외모·의상은 그림에서」라는 역할 설명이 들어갑니다. 영상 1개당 약 20~30초가 더 걸리며, 같은 영상·구간·모델이면 서버를 켜 둔 동안 결과를 재사용합니다. 분석이 실패하면 기존처럼 이름만 넘어가고 Writer 리포트에 이유가 남습니다.

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

- 긴 영상 LBH (2026-09-26, RTX 4090, HyperFlow 8스텝): 256×256 → 384×384, 2장면 생성/승인/Motion Context/합치기/`.ext` 복원/캐시 재실행 통과. Full Batch 2장면 256×288 → 384×448 및 LBH OFF 전환 시 256×288 복귀·캐시 분리 통과. 화질 개선 정도를 비교 평가한 테스트는 아닙니다.

아직 확인하지 않은 것: 고해상도·긴 장면(5초 이상), 3장면 이상, Linux/macOS.

## 라이선스

원본 코드와 변경 내역은 [NOTICE.md](NOTICE.md), 고정한 원본 리비전은 [UPSTREAM.json](UPSTREAM.json)을 참고하세요. GPL-3.0 및 해당 원본의 Apache-2.0 고지를 유지합니다.
