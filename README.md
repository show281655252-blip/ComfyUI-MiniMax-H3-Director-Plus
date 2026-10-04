# MiniMax H3 Director Plus

ComfyUI용 MiniMax H3 **장면 타임라인 + 긴 영상(Ref2VA + Motion Context)** 커스텀 노드입니다.
장면 카드마다 프롬프트·시드·길이를 정해 한 장면씩 만들고, 마음에 드는 장면을 승인하며 이어 붙입니다.

원본 DaSiWa·Extender 파일을 수정하지 않는 독립 노드이며, 필요한 원본 코드 일부를 라이선스 고지와 함께 내부에 포함합니다.

> 최신 변경은 `main` 브랜치 기준입니다(태그 `v0.2.0a2` 이후 기능이 많이 추가됨). 아직 확인하지 않은 범위는 [검증 현황](#검증-현황)을 보세요.

## 주요 기능

- **장면 타임라인**: 장면 카드(미리보기·프롬프트·시드·길이), 앞 장면부터 연속 승인, 생성 캐시 재사용, 장면 접기·묶기
- **긴 영상 엔진**: Motion Context로 장면을 이어 만들고 합칩니다. Full Batch / 한 장면씩(clip by clip)
- **프로젝트 저장 (.ext)**: 장면 설정·레퍼런스·생성 캐시를 함께 보관/복원
- **프롬프트 작성 창**: PromptDirector + Ollama 기반 작성·수정·대화 다듬기, 영상 레퍼런스 분석
- **장면별 선택 기능** (Settings 스위치 + 장면 카드 ON/OFF): 오디오 재생성 · 얼굴 다듬기 · Motion Lab(de-rope)
- **LBH 업스케일**: 낮은 해상도로 만든 뒤 확대하고 마지막 스텝을 고해상도에서 보정
- **레퍼런스 영상 해상도 선택**: Orig / 0.83 / 0.65 / 0.52MP

## 설치

ComfyUI를 종료한 뒤 `ComfyUI/custom_nodes` 폴더에서:

```powershell
git clone https://github.com/show281655252-blip/ComfyUI-MiniMax-H3-Director-Plus.git
```

Portable 환경은 ComfyUI용 Python으로 의존성을 설치합니다 (`ComfyUI_windows_portable` 폴더에서):

```powershell
.\python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\ComfyUI-MiniMax-H3-Director-Plus\requirements.txt
```

PyTorch/torchaudio를 다른 버전으로 바꾸지 말고 ComfyUI 배포본과 맞는 조합을 유지하세요. 설치 후 ComfyUI를 재시작하고 브라우저에서 Ctrl+F5를 누릅니다. 업데이트는 `git pull`입니다.

## 필요한 것

필수:
- MiniMax H3를 지원하는 ComfyUI
- Ref2VA 모델, MiniMax용 텍스트 인코더, video/audio VAE (자동 다운로드 없음)
- DaSiWa 커스텀 노드 (`MiniMaxH3DirectorGuide`를 씁니다)

선택 기능별로 필요한 것:

| 기능 | 필요한 것 |
|---|---|
| LBH 업스케일 | `Comfyui_Minimax_h3_latent_Upscaler` + `models/latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors` |
| Motion Lab | [ComfyUI-MAINodes](https://github.com/matlowai/ComfyUI-MAINodes) |
| 얼굴 다듬기 | [ComfyUI-H3-FaceRefine](https://github.com/Carasibana/ComfyUI-H3-FaceRefine) + `models/ultralytics/bbox/face_yolov8m.pt` |
| 프롬프트 작성 창 | [ComfyUI-MinimaxH3-PromptDirector](https://github.com/Bokuwako/ComfyUI-MinimaxH3-PromptDirector) + Ollama |

선택 기능의 팩은 노드를 직접 호출하며 코드를 복사하지 않습니다. 없으면 해당 기능을 켰을 때 한국어 오류로 안내합니다.

## 노드

- **MiniMax H3 Director Plus**: 레퍼런스·장면 타임라인·프롬프트(단일 편집기 + 프롬프트 작성 창)·시드 관리
- **Director Plus · Generate**: Motion Context로 장면을 이어서 생성
- **Director Plus · Video Output**: 영상 저장 및 미리보기
- **Director Plus · Conditioning Match Latent**: 단일 영상 LBH에서 조건을 실제 출력 격자에 맞춤
- **Director Plus · Motion Lab (단일 영상)** / **Director Plus · 얼굴 다듬기 (단일 영상)**: 단일 영상(FL2VA·Ref2VA)의 최종 잠재값에 두 기능을 적용 (아래 「단일 영상에서 쓰기」)

## 사용법

1. `workflows/Director_Plus_Example.json`을 불러옵니다. 워크플로우 안의 메모 노드에 설치할 커스텀 노드와 첫 실행 순서가 적혀 있습니다. Settings에서 모델 파일을 실제 파일로 고르세요(터보 LoRA는 LoraManager 로더에서 선택).
2. 장면 카드에 프롬프트를 쓰고 **생성 / 실행**합니다.
3. 마음에 들면 카드의 **승인** 체크박스를 누릅니다. 다음 장면이 자동 선택되며, 다시 **생성 / 실행**합니다. 마지막 장면 뒤에 이어 가려면 **+ 장면 추가**를 누릅니다.

### 승인과 캐시

- 승인은 앞 장면부터 순서대로만 가능하고, 체크를 풀면 그 뒤 장면의 승인도 함께 풀립니다.
- 캐시는 남으므로 다시 체크하면 재생성 없이 승인됩니다.
- 승인을 푼 장면의 프롬프트·시드·길이를 고치면 그 장면부터 다시 생성합니다.
- **전체 승인** / **전체 해제**: 생성된 장면을 앞에서부터 한 번에 승인하거나(아직 생성 안 된 장면에서 멈춤) 모두 해제합니다.
- **캐시 확인**: 디스크 캐시 상태를 다시 확인합니다. 워크플로우를 열 때도 한 번 자동 확인합니다.
- **초기화**: 모든 장면을 지우고 빈 장면 1개로 새로 시작합니다(확인 창). 설정은 유지되고 저장한 .ext와 만든 영상은 지워지지 않습니다.
- 캐시 위치: `ComfyUI/user/director_plus/cache` (원본 Extender 캐시와 분리)

### 프롬프트

긴 영상에서는 **장면 카드의 프롬프트**가 생성에 쓰입니다(노드 아래쪽 Prompt는 단일 영상용). 카드에 직접 쓰거나 **✍ 프롬프트 작성**으로 넣으세요. 새 장면(「+ 장면 추가」·「초기화」)은 외부 프롬프트가 연결돼 있으면 ON, 아니면 OFF로 만들어집니다.

### 장면이 많을 때

- **승인 장면 접기**: 앞에서부터 승인된 장면 2개 이상을 카드 한 장으로 접습니다(기본 ON).
- **구간 묶기**: `8-11`처럼 범위를 입력해 묶고, 묶음에 메모를 남길 수 있습니다. 묶음 카드는 구간 전체를 미리 봅니다.
- 승인 묶음은 승인할 때마다 늘어나므로 **여기서 고정**으로 끝을 고정할 수 있습니다.
- 장면 번호 줄을 누르면 그 장면으로 이동합니다. 접기·묶기는 화면만 바꾸며 생성·캐시·Motion Context에는 영향이 없습니다.

### 프로젝트 저장 (.ext)

**프로젝트 저장 (.ext)** 으로 장면 설정·레퍼런스·생성 캐시를 함께 보관하고 **프로젝트 불러오기**로 복원합니다. 모델과 워크플로우 JSON은 별도로 보관하세요. `.ext`는 만들 때의 LBH 설정을 기억해 불러올 때 워크플로우의 LBH 설정을 자동으로 맞춥니다.

## 장면별 선택 기능

세 기능 모두 같은 방식입니다. **Settings 스위치가 ON이고 장면 카드도 ON인 장면에만** 적용합니다. Settings가 꺼져 있으면 카드 토글은 흐리게 「Settings에서 꺼짐」으로 표시되고 바꿀 수 없습니다. 새 장면은 모두 OFF로 시작하니 필요한 장면만 켜세요(필드가 없는 이전 장면은 ON으로 취급). 카드 값을 바꾸면 그 장면부터 다시 생성합니다.

세 기능은 **캐시 이름에 들어가지 않습니다.** Settings 값을 바꿔도 승인된 장면은 그대로 유지됩니다. 단, 이미 만든 장면은 만들 때의 설정 그대로이므로 새 설정을 적용하려면 승인을 해제하고 다시 생성하세요. Settings를 바꾸면 승인하지 않고 생성만 된 장면은 자동으로 초기화됩니다.

### 단일 영상에서 쓰기

위 두 기능은 긴 영상의 장면 루프 안에서 돌아가지만, 단일 영상(FL2VA·I2VA·Ref2VA)에서도 같은 Settings 스위치(🙂 얼굴 다듬기, 🌀 Motion Lab)로 켤 수 있습니다. Settings 서브그래프의 최종 잠재값 뒤에 `Director Plus · Motion Lab (단일 영상)` → `Director Plus · 얼굴 다듬기 (단일 영상)` 노드가 연결돼 있고, 스위치가 꺼져 있으면 잠재값을 그대로 통과시킵니다. 장면 카드가 없으므로 장면별 ON/OFF는 없습니다. LBH를 켜면 고해상도 결과에 적용되어(긴 영상은 LBH 전에 Motion Lab) 더 오래 걸립니다. 소리는 바뀌지 않으며, 오디오 재생성은 두 처리 뒤의 영상으로 합니다. 이 노드들을 직접 연결해 쓰려면 모델·조건(LBH를 썼다면 고해상도에 맞춘 조건)·최종 잠재값·VAE를 넣으세요. Motion Lab에는 전체 스케줄 `sigmas`와 영상 프레임 수가 더 필요합니다.

### 🔊 오디오 재생성

`audio_regen_enabled`를 켜고 `audio_regen_model`에 **터보 LoRA를 적용하기 전의 기본 모델**(같은 Sigma Shift)을 연결합니다. 장면마다 영상 잠재값을 0.5배로 줄여 오디오와 합친 뒤 30스텝·denoise 0.5로 재샘플링하고 **오디오만** 교체합니다. 화면과 대사 타이밍은 바뀌지 않습니다. 몇 스텝짜리 터보 모델이 만든 오디오의 잡음(험 등)을 줄이는 용도이며 장면당 시간이 추가로 듭니다. 끈 장면은 1차 생성 소리를 그대로 씁니다.

### 🙂 얼굴 다듬기

완성된 장면(모션랩·LBH·오디오 재생성 뒤, 캐시 저장 전)에서 얼굴을 프레임마다 찾아 크게 잘라(캔버스 512~768 자동) 장면 프롬프트·레퍼런스 이미지로 denoise 0.4 정도로 다시 그리고, 색을 맞춰 얼굴 부분만 되붙입니다. 장면 소리는 고정한 채 그리므로 입 모양이 그 소리를 따르고 소리는 바뀌지 않습니다. 얼굴이 안 보이는 프레임은 원본 그대로, 얼굴이 없는 장면은 건너뜁니다. 얼굴이 작거나 흐트러진 장면에 효과가 크고, 이미 깔끔한 얼굴은 조금 부드러워질 수 있습니다. 장면 생성 한 번 정도의 시간이 더 듭니다.

### 🌀 Motion Lab (de-rope)

빠른 동작의 뭉개짐을 줄입니다. 1차 생성 latent에서 동작이 너무 빠른 구간을 찾고(H3 Jerk Oracle, balanced 프리셋), 그 구간을 늘린 영상을 일정의 뒤 70%로 다시 생성한 뒤(H3 Time Smear → H3 V2V Init) 늘렸던 프레임을 빼서 원래 길이로 되돌립니다(H3 Exact Recover). LBH·오디오 재생성보다 먼저, 기본 해상도에서 실행됩니다. 앞 장면에서 이어받은 Motion Context 프레임은 늘리지 않고, 소리는 1차 생성의 것을 그대로 둡니다. **장면당 시간과 GPU 메모리가 크게 늘어나므로**(켠 장면이 약 3배 느림) 동작이 빠른 장면에만 켜세요.

## LBH 업스케일

`DirectorPlusGenerate`의 `lbh_enabled` / `lbh_scale`을 Settings의 LBH ON/OFF·배율에 연결하면 긴 영상에도 적용됩니다(입력이 없으면 OFF). 기본 해상도로 전체 스텝 중 마지막 4스텝을 뺀 만큼 샘플링한 뒤 denoised 잠재값을 LBH로 확대하고, 마지막 4스텝을 고해상도에서 보정합니다(최소 5스텝). BF16·시간 청크·32px 정렬을 사용하므로 실제 출력 크기가 배율 계산값과 조금 다를 수 있습니다.

- 참조 이미지·키프레임은 **픽셀 공간에서 크기를 바꾼 뒤 Video VAE로 다시 인코딩**합니다. 잠재값을 bilinear로 직접 늘리면 격자 무늬와 잔상이 생길 수 있습니다. 원본 픽셀이 없는 RefMod/영상 문맥은 디코딩 후 재인코딩합니다.
- 다음 장면은 저해상도 단계에서 이전 장면의 Motion Context를 축소해 쓰고, 고해상도 보정 단계에서는 원래 고해상도 문맥을 씁니다.
- 선택 입력 `lbh_full_first_pass`(8+4)는 1차에서 스케줄을 끝까지 샘플링한 뒤 같은 스케줄의 마지막 4스텝으로 보정합니다. 같은 시드 비교에서 시간이 약 8~15% 늘었고 눈에 띄는 이득은 없었습니다.
- LBH ON/OFF·배율·모델명이 바뀌면 캐시를 분리하고 승인을 초기화합니다. 승인된 장면이 있는데 LBH 설정이 달라진 채 생성하면 오류로 멈춥니다. 기존 디스크 캐시는 삭제하지 않습니다.
- **단일 영상**: 기존 `MiniMaxH3ConditioningUpscale`을 `Director Plus · Conditioning Match Latent`로 교체하고 `conditioning`, 확대 전 `base_latent`, 실제 LBH 출력 `target_latent`, `vae`, Director `guide`를 연결하세요. 실제 출력 격자에 맞추므로 반올림 차이로 인한 토큰 불일치를 막습니다.
- 다른 호환 모델은 `lbh_model_name`에 지정합니다.

## 레퍼런스 영상 해상도

영상 항목의 V/A/V+A 옆에서 Orig 또는 0.83/0.65/0.52MP를 고릅니다. 비율을 유지하며 32픽셀 격자로 줄이고 작은 영상은 키우지 않습니다. 오디오·프레임 수·출력 해상도는 바뀌지 않지만 세부 표현은 달라질 수 있습니다. A(소리만)에서는 숨겨집니다. 설정은 워크플로우와 `.ext`에 저장되며, 긴 영상에서 바꾸려면 기존 장면 승인을 해제해야 합니다(캐시는 삭제하지 않음).

## 프롬프트 작성 창 (PromptDirector)

Director 노드의 프롬프트 도구 모음, 또는 긴 영상 타임라인의 **✍ 프롬프트 작성** 버튼으로 엽니다. Writer·Freeze·Shot Builder 노드를 연결하지 않아도 됩니다.

- **구성**: 장면 설정(스타일·장르·렌즈·심도·조명·대사·환경음·음악·금지/필수), Director 이미지별 레퍼런스 역할, 샷 카드(카메라·샷 전환·몸 방향·시선·행위·대사), Ollama 모델·고급 설정, 브리프 확인, 프롬프트 작성, Prompt Freeze 부분 수정, 이전 프롬프트. 구성은 MMH3 Studio의 디렉터 탭을 따릅니다.
- **💬 LLM과 대화하며 다듬기**: 이상한 점을 적으면 원인 설명과 고친 프롬프트를 제안합니다. 자동 적용되지 않고 「결과 칸에 넣기」·「바로 적용」을 눌러야 반영되며 이전 프롬프트로 되돌릴 수 있습니다. 창을 닫으면 Ollama 모델을 내립니다.
- Director의 모드·길이·레퍼런스를 그대로 읽습니다. 처음 열 때 워크플로우의 Shot Settings·Shot Builder·Writer 노드 값을 가져오며, 창의 내용은 노드에 저장됩니다.
- 작성은 ComfyUI 대기열 밖에서 실행되고, 시작할 때 ComfyUI 모델을, 끝나면 Ollama 모델을 내립니다. 영상 생성 중에는 쓸 수 없습니다.
- **적용**을 누르면 단일 영상은 Director 프롬프트에, 긴 영상은 고른 장면 카드(기본: NEXT, 외부 프롬프트 OFF)에 들어갑니다.

### PromptDirector 연동

[ComfyUI-MinimaxH3-PromptDirector](https://github.com/Bokuwako/ComfyUI-MinimaxH3-PromptDirector)의 Prompt Writer `FOLLOW_DIRECTOR` 모드가 Director Plus 노드도 Director로 인식합니다. PromptDirector 파일은 수정하지 않고 실행 시 Director 탐색만 넓힙니다. 연동이 안 되면 콘솔에 경고가 나오니 Writer의 mode를 직접 지정하세요.

- **영상 분석**: REF2VA 타임라인에 영상 레퍼런스가 있으면 Writer가 쓰기 전에 그 영상(자르기 구간)에서 프레임을 뽑아(7.5초 이하 0.25초, 더 길면 0.5초 간격, 최대 30장) Ollama 모델에 한 번 보여 주고 카메라·시작 자세·시간순 동작·손 모양·표정·효과를 적은 분석을 받아 Writer에 넘깁니다. 영상 1개당 약 20~30초가 더 걸리고 같은 영상·구간·모델이면 서버가 켜져 있는 동안 재사용합니다. 로컬 모델이라 실행마다 정확도 편차가 있으니 결과를 확인하세요.
- **V+A 소리 규칙**: 영상의 소리를 쓰는 V+A 레퍼런스가 있으면 소리 칸이 `<Audio n>`을 따르도록 안내합니다. 소리 없는 영상을 V+A로 두면 V로 처리합니다.

## 검증 현황

Windows ComfyUI Portable + RTX 4090에서 확인한 것입니다.

- 설치·import: git clone 후 재시작, 노드 등록, 다른 커스텀 노드와 충돌 없음
- 긴 영상: 2장면 승인 → Motion Context → 합치기 → `.ext` 저장·복원 → 캐시 재실행, 6장면(5~7초, 640×864 → LBH 960×1280) 연속 생성, Full Batch 합치기(재디코딩 없이 이어 붙임)
- LBH: 단일 영상(I2VA·Ref2VA)·긴 영상에서 배경 격자·잔상 제거 확인
- 오디오 재생성·Motion Lab·얼굴 다듬기: 장면 카드별 ON/OFF와 실제 해상도 1~2장면 생성 확인
- 레퍼런스 영상 해상도: 800×1088 → 608×832, `.ext` 값 유지와 승인 상태 경고 확인

아직 확인하지 않은 것: LBH와 얼굴 다듬기를 함께 켠 경우, 대사 장면의 입 모양, 7장면 이상, Linux/macOS. 소리와 화질의 우열은 주관적이라 청취·시청 평가는 하지 않았습니다.

## 라이선스

원본 코드와 변경 내역은 [NOTICE.md](NOTICE.md), 고정한 원본 리비전은 [UPSTREAM.json](UPSTREAM.json)을 참고하세요. GPL-3.0 및 해당 원본의 Apache-2.0 고지를 유지합니다.
