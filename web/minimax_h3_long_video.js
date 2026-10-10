// Modified for Director Plus isolation, 2026-09-26. See NOTICE.md for upstream attribution.
import { app } from "../../scripts/app.js";

import { api } from "../../scripts/api.js";

function element(tag, text, parent) {

  const el = document.createElement(tag);

  if (text) el.textContent = text;

  parent?.append(el);

  return el;

}

// New scenes use the external prompt only when one is actually linked to the node;
// otherwise they start with it OFF and keep their own (or the synced main) prompt.
// Motion Lab, audio regen and face refine start OFF on new scenes and are switched on per card; older scenes
// without the fields still count as ON.
function newClip(useExternal = true) {

  return { id: crypto.randomUUID(), name: "", prompt: "", use_external_prompt: useExternal, duration: 5, seed: Math.floor(Math.random() * 1e12), seed_mode: "fixed", validated: false, loras: [], derope: false, audio_regen: false, face_refine: false };

}

async function request(path, data) {

  const response = await api.fetchApi(path, data ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) } : {});

  const result = await response.json();

  if (!response.ok || result.ok === false) throw new Error(result.error || response.statusText);

  return result;

}

function reconcileSceneCache(settings, result) {
  const cached = result.found === false ? [] : (result.cached_clip_ids || []);
  const approved = new Set(result.validated_clip_ids || []);
  const reusable = [], missing = [];
  // A scene's cache is reusable while the cached chain matches scene by scene from the start;
  // approval is a separate, contiguous prefix of those. (Tying reuse to approval marked every
  // cached scene after the first unapproved one as "needs regeneration".)
  let chainIntact = true, approvedPrefix = true;
  settings.clips.forEach((clip, index) => {
    const exists = chainIntact && cached[index] === clip.id;
    if (exists) reusable.push(clip.id); else missing.push(clip.id);
    clip.validated = Boolean(exists && approvedPrefix && clip.validated && approved.has(clip.id));
    chainIntact = exists;
    approvedPrefix = clip.validated;
  });
  return { cached: reusable, missing };
}

function viewURL(item) {

  return api.apiURL(`/view?${new URLSearchParams({ filename: item.filename, subfolder: item.subfolder || "", type: item.type || "output", ...(item.preview_revision ? { v: item.preview_revision } : {}) })}`);

}

function installStyle() {
  if (document.getElementById("director-plus-long-style")) return;
  const style = element("style"); style.id = "director-plus-long-style";
  style.textContent = `
  .dp-h3 .dl-panel{background:#304650;border:1px solid #526571;border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:10px;color:#e8f2fa;margin:8px 0;font:14px system-ui,sans-serif;box-sizing:border-box;flex-shrink:0}
  .dp-h3 .dl-panel *{box-sizing:border-box}
  .dp-h3 .dl-panel .dl-section{background:linear-gradient(110deg,#101c24,#142731);border:1px solid #263e4b;border-radius:10px;padding:16px;display:flex;flex-direction:column;gap:12px}
  .dp-h3 .dl-panel button,.dp-h3 .dl-panel a.dl-button{background:linear-gradient(#203542,#152530)!important;border:1px solid #4c6c80!important;color:#e8f2fa!important;border-radius:8px!important;padding:10px 16px!important;font:600 14px system-ui!important;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:8px}
  .dp-h3 .dl-panel button:disabled{opacity:.4;cursor:default}
  .dp-h3 .dl-panel button:hover:not(:disabled){border-color:#59d4ff!important}
  .dp-h3 .dl-panel button.dl-blue,.dp-h3 .dl-panel a.dl-blue{background:linear-gradient(#17446b,#165888)!important;border-color:#299eed!important}
  .dp-h3 .dl-panel button.dl-red{background:linear-gradient(#5a2226,#6e2227)!important;border-color:#e0575f!important}
  .dp-h3 .dl-panel button.dl-green{background:linear-gradient(#185e3c,#167844)!important;border-color:#42c976!important}
  .dp-h3 .dl-panel button.dl-toggle{border-radius:99px!important;padding:7px 12px!important;min-width:74px}
  .dp-h3 .dl-panel button.dl-toggle[aria-pressed=true]{background:#136936!important;border-color:#79efa4!important;box-shadow:0 0 10px #36ce6650}
  .dp-h3 .dl-panel button.dl-toggle:after{content:"";width:18px;height:18px;background:#abbac4;border-radius:50%}
  .dp-h3 .dl-panel button.dl-toggle[aria-pressed=true]:after{background:#bbffd2;box-shadow:0 0 7px #61f994}
  .dp-h3 .dl-panel input,.dp-h3 .dl-panel select,.dp-h3 .dl-panel textarea{background:#142630!important;color:#edf6fc!important;border:1px solid #425e70!important;border-radius:7px!important;padding:9px!important;font:14px system-ui!important}
  .dp-h3 .dl-panel input:disabled,.dp-h3 .dl-panel textarea:disabled{opacity:.65}
  .dp-h3 .dl-panel textarea{width:100%;min-height:100px;resize:vertical}
  .dp-h3 .dl-panel .dl-strip{position:relative}
  .dp-h3 .dl-panel .dl-card.dl-group{flex:0 0 340px;width:340px;border-style:dashed;border-color:#5b7d93;background:#101c24}.dp-h3 .dl-panel .dl-group-line{font-size:13px;color:#d6e4ee}.dp-h3 .dl-panel .dl-group-list{display:flex;flex-direction:column;gap:4px;max-height:360px;overflow-y:auto}.dp-h3 .dl-panel button.dl-group-row{display:flex;gap:8px;align-items:center;text-align:left;padding:5px 8px!important;font-size:12px!important;background:#172833!important;border:1px solid #2c4252!important}.dp-h3 .dl-panel .dl-group-num{white-space:nowrap;font-weight:600}.dp-h3 .dl-panel .dl-group-text{flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;color:#9fb3c2}.dp-h3 .dl-panel button.dl-group-bar{flex:0 0 40px;width:40px;scroll-snap-align:start;min-height:900px;padding:0!important;writing-mode:vertical-rl;font-size:12px!important;border:1px dashed #5b7d93!important;background:#101c24!important;border-radius:9px!important}.dp-h3 .dl-panel .dl-scenebar{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin:2px 0 6px}.dp-h3 .dl-panel button.dl-scene-num{min-width:28px;padding:3px 6px!important;font-size:12px!important;background:#1a2a35!important}.dp-h3 .dl-panel button.dl-scene-num.made{border-color:#c9a64a!important}.dp-h3 .dl-panel button.dl-scene-num.ok{border-color:#5fbf7a!important;color:#bff3d0}.dp-h3 .dl-panel button.dl-scene-num.sel{background:#2f5874!important}
  .dp-h3 .dl-panel .dl-cards{display:flex;gap:12px;overflow-x:auto;overflow-y:hidden;padding:3px 3px 12px;scroll-snap-type:x proximity;scrollbar-gutter:stable}
  .dp-h3 .dl-panel .dl-card{flex:0 0 480px;width:480px;min-height:900px;border:1px solid #466071;border-radius:9px;background:#14222b;padding:9px;display:flex;flex-direction:column;gap:8px;scroll-snap-align:start;cursor:pointer}
  .dp-h3 .dl-panel .dl-card-title{font-size:15px}
  .dp-h3 .dl-panel .dl-next{color:#f7c35f;font-size:11px;font-weight:700;white-space:nowrap}
  .dp-h3 .dl-panel .dl-card-row{display:flex;align-items:center;gap:6px}
  .dp-h3 .dl-panel .dl-label{color:#9fb6c5;font-size:12px;font-weight:600}
  .dp-h3 .dl-panel textarea.dl-group-note{min-height:64px;max-height:160px;resize:vertical;font-size:12px!important;line-height:1.45;cursor:text}
  .dp-h3 .dl-panel textarea.dl-card-prompt{flex:1 1 auto;min-height:420px;font-size:12px!important;line-height:1.45;cursor:text}
  .dp-h3 .dl-panel textarea.dl-card-prompt.locked{opacity:.65;cursor:default}
  .dp-h3 .dl-panel .dl-card-grid{display:grid;grid-template-columns:1fr 38px 84px;gap:6px;align-items:end}
  .dp-h3 .dl-panel .dl-field{display:flex;flex-direction:column;gap:3px;min-width:0}
  .dp-h3 .dl-panel .dl-field input{width:100%!important;padding:6px 8px!important;font-size:13px!important}
  .dp-h3 .dl-panel button.dl-dice{padding:6px 0!important;height:33px}
  .dp-h3 .dl-panel button.dl-small{padding:6px 10px!important;font-size:12px!important}
  .dp-h3 .dl-panel .dl-card .dl-toggle{padding:4px 9px!important;min-width:60px;font-size:12px!important}
  .dp-h3 .dl-panel .dl-card .dl-master-off .dl-label,.dp-h3 .dl-panel .dl-card .dl-master-off .dl-toggle{opacity:.4}
  .dp-h3 .dl-panel .dl-card .dl-master-note{font-size:11px;margin-right:6px}
  .dp-h3 .dl-panel .dl-card .dl-toggle:after{width:14px;height:14px}
  .dp-h3 .dl-panel button.dl-nav{position:absolute;top:calc(50% - 26px);z-index:3;width:34px;height:52px;padding:0!important;border-radius:8px!important;background:rgba(16,32,42,.92)!important;font-size:16px!important;box-shadow:0 2px 10px #0008}
  .dp-h3 .dl-panel button.dl-nav.prev{left:-6px}
  .dp-h3 .dl-panel button.dl-nav.next{right:-6px}
  .dp-h3 .dl-panel button.dl-nav:disabled{opacity:0;pointer-events:none}
  .dp-h3 .dl-panel .dl-card.selected{border:2px solid #14c3f4;padding:8px;box-shadow:0 0 8px #12b9eb35}
  .dp-h3 .dl-panel .dl-card-head{display:flex;align-items:center;justify-content:space-between;gap:7px}
  .dp-h3 .dl-panel .dl-card-head button{background:transparent!important;border:0!important;padding:3px!important;text-align:left}
  .dp-h3 .dl-panel .dl-status{border:1px solid #526a7b;border-radius:99px;padding:5px 10px;color:#bacbd7;white-space:nowrap;font-size:12px}
  .dp-h3 .dl-panel .dl-status{display:inline-flex;align-items:center;gap:9px}
  .dp-h3 .dl-panel .dl-pause-icon{display:inline-block;width:12px;height:14px;border-left:4px solid currentColor;border-right:4px solid currentColor;flex-shrink:0}
  .dp-h3 .dl-panel .dl-status.approved{border-color:#327547;background:#103722;color:#82f595}
  .dp-h3 .dl-panel .dl-status.review{border-color:#16bedf;background:#123b4b;color:#7feeff}
  .dp-h3 .dl-panel .dl-validate{display:inline-flex;align-items:center;gap:7px;border:1px solid #16bedf;background:#123b4b;color:#7feeff;border-radius:99px;padding:4px 11px 4px 8px;font-size:12px;font-weight:600;white-space:nowrap;cursor:pointer;user-select:none}
  .dp-h3 .dl-panel .dl-validate.on{border-color:#327547;background:#103722;color:#82f595}
  .dp-h3 .dl-panel .dl-validate input{width:16px!important;height:16px!important;margin:0;padding:0!important;accent-color:#42c976;cursor:pointer}
  .dp-h3 .dl-panel .dl-validate:has(input:disabled){opacity:.5;cursor:default}
  .dp-h3 .dl-panel .dl-preview{width:100%;height:380px;flex:0 0 380px;object-fit:contain;background:#0b151c;border-radius:6px;border:1px solid #293e48}
  .dp-h3 .dl-panel .dl-empty{display:flex;align-items:center;justify-content:center;color:#80919d;font-size:14px}
  .dp-h3 .dl-panel .dl-muted{color:#adc0ce;font-size:12px}
  .dp-h3 .dl-panel strong{font-size:17px}
  .dp-h3 .dl-panel .dl-spacer{flex:1}
  .dp-h3 .dl-panel .dl-tools{display:flex;flex-wrap:wrap;align-items:center;gap:8px 0;margin:2px 0 4px}
  .dp-h3 .dl-panel .dl-tgroup{display:flex;align-items:center;gap:6px;flex-wrap:nowrap;padding:0 14px;border-left:1px solid #2f4350}
  .dp-h3 .dl-panel .dl-tgroup:first-child{padding-left:0;border-left:0}
  .dp-h3 .dl-panel .dl-tlabel{font-size:11px;color:#8fa3b2;margin-right:2px}
  .dp-h3 .dl-panel button.dl-accent{background:rgba(126,235,167,.16)!important;border-color:rgba(126,235,167,.75)!important;color:#d7ffe3!important}
  .dp-h3 .dl-panel button.dl-switch.on{background:rgba(70,140,190,.32)!important;border-color:#6aaad6!important;color:#e6f4ff!important}
  .dp-h3 .dl-panel button.dl-switch.on:before{content:"✓ "}
  `;
  document.head.append(style);
}

export function renderLongVideo(node, state, emit) {
  installStyle();
  const hasExternal = () => Boolean(node.__directorPlusH3HasExternalPrompt?.());

  if (!state.long_video) state.long_video = { version: 1, project_id: crypto.randomUUID(), enabled: false, start_mode: "new", source_video: "", run_mode: "clip_by_clip", context_length: "22", clips: [newClip(hasExternal())] };

  const rt = node.__directorLong || (node.__directorLong = { selected: 0, cached: [], busy: false, message: "" });

  rt.state = state;

  rt.emit = emit;

  const s = state.long_video;
  s.source_mode_enabled = false; s.start_mode = "new"; delete s.source_video;

  const panel = element("section");

  panel.className = "dl-panel";

  const row = (parent = panel) => { const r = element("div", null, parent); r.style.cssText = "display:flex;align-items:center;flex-wrap:wrap;gap:8px"; return r; };

  const section = () => { const el = element("div", null, panel); el.className = "dl-section"; return el; };
  const refresh = () => node.__directorPlusH3Render?.();

  const save = () => { emit(); node.graph?.setDirtyCanvas(true, true); };
  // H3 makes 17k+5 frames at 24 fps: a scene length is rounded up to that grid, a reference
  // video (its trim range, at most 362 frames) is rounded down. A scene of exactly the rounded-down
  // reference length lines the two up frame for frame.
  const referenceFit = () => {
    const videos = (state.items || [])
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => item.enabled !== false && item.type === "video" && item.media_mode !== "audio")
      .sort((a, b) => (a.item.slot ?? a.index) - (b.item.slot ?? b.index) || a.index - b.index);
    if (!videos.length) throw new Error("타임라인에 영상 레퍼런스가 없습니다.");
    const item = videos[0].item;
    const start = Number(item.trim_start) || 0;
    const end = Number(item.trim_end ?? item.source_duration);
    const source = end - start;
    if (!Number.isFinite(source) || source <= 0) throw new Error("영상 레퍼런스의 길이를 알 수 없습니다. 영상을 다시 넣어 보세요.");
    const sourceFrames = Math.round(source * 24);
    let frames = Math.min(sourceFrames, 362);
    while (frames >= 5 && frames % 17 !== 5) frames -= 1;
    if (frames < 5) throw new Error("영상 레퍼런스가 너무 짧습니다.");
    const name = String(item.value || "").split(/[\\/]/).pop();
    return { seconds: Math.round(frames / 24 * 1000) / 1000, frames, source, sourceFrames, label: `<Video 1> ${name}` };
  };

  const button = (parent, text, action) => {

    const b = element("button", text, parent);

    b.disabled = rt.busy || rt.running;

    b.onclick = async () => {

      if (rt.busy || rt.running) return;

      rt.busy = true;

      try { await action(); rt.message = ""; } catch (e) { rt.message = e.message; }

      finally { rt.busy = false; save(); refresh(); }

    };

    return b;

  };

  const select = (parent, values, value, change) => {

    const el = element("select", null, parent);

    for (const [v, label] of values) { const opt = element("option", label, el); opt.value = v; }

    el.value = value;

    el.disabled = rt.busy || rt.running;

    el.onchange = async () => { try { await change(el.value); save(); refresh(); } catch (e) { rt.message = e.message; refresh(); } };

    return el;

  };

  const invalidate = async (index) => {

    if (s.cache_owner) await request("/director_plus/extender/local_ref_invalidate", { owner_id: s.cache_owner, generation_mode: "ref2va", motion_context: true, clip_index: index, validated: false });

    for (let i = index; i < s.clips.length; i++) s.clips[i].validated = false;

    rt.cacheChecked = true;
    rt.cached = rt.cached.filter(id => s.clips.findIndex(c => c.id === id) < index);

  };

  // A Settings switch (audio regen / Motion Lab / face refine) changed: generated scenes that are not approved were
  // made with the old value, so reset them. Approved scenes are kept.
  rt.invalidateUnapproved = async () => {
    const long = rt.state?.long_video;
    const first = (long?.clips || []).findIndex(c => !c.validated);
    if (first < 0 || !long.cache_owner) return false;
    const generated = (rt.cached || []).some(id => long.clips.findIndex(c => c.id === id) >= first);
    if (!generated) return false;
    await invalidate(first);
    rt.message = "Settings가 바뀌어 아직 승인하지 않은 생성 장면을 다시 만들도록 초기화했습니다(승인된 장면은 그대로).";
    save(); refresh();
    return true;
  };

  // Prompt Studio writes a scene's prompt straight into its card: the card then keeps its own prompt
  // (external prompt OFF) and a generated scene is invalidated like a typed edit.
  rt.setScenePrompt = async (index, text) => {
    const long = rt.state?.long_video;
    const clip = long?.clips?.[index];
    if (!clip) throw new Error("장면을 찾을 수 없습니다.");
    if (clip.validated) throw new Error(`장면 ${index + 1}은 승인돼 있어 바꿀 수 없습니다. 먼저 승인을 해제하세요.`);
    if (long.cache_owner && (rt.cached || []).includes(clip.id)) await invalidate(index);
    clip.prompt = String(text || "");
    clip.use_external_prompt = false;
    rt.selected = index; rt.scrollTo = index;
    save(); refresh();
  };

  // Tick/untick approval without touching the cache (Extender "Validated" behaviour).
  const setValidated = async (index, validated) => {
    if (!s.cache_owner) throw new Error("먼저 이 장면을 생성하세요.");
    const result = await request("/director_plus/extender/local_ref_invalidate", { owner_id: s.cache_owner, generation_mode: "ref2va", motion_context: true, clip_index: index, validated });
    if (validated && !result.found) throw new Error("먼저 이 장면을 생성하세요.");
    if (validated) s.clips[index].validated = true;
    else for (let i = index; i < s.clips.length; i++) s.clips[i].validated = false;
  };

  const top = row(section());

  element("strong", "긴 영상 만들기", top);

  const mainToggle = button(top, s.enabled ? "ON" : "OFF", () => {

    s.enabled = !s.enabled;

    if (s.enabled) {

      const mode = node.widgets.find(w => w.name === "mode"); mode.value = "REF2VA";

      const fps = node.widgets.find(w => w.name === "frame_rate"); fps.value = 24;

    }

  });

  mainToggle.className = "dl-toggle"; mainToggle.setAttribute("aria-pressed", String(s.enabled));
  element("span", "Ref2VA + Motion Context", top);
  if (!s.enabled) return panel;

  for (const [value, label] of [["clip_by_clip", "장면별 생성"], ["full_batch", "전체 생성"]]) {
    const modeButton = button(top, label, () => { s.run_mode = value; });
    if (s.run_mode === value) modeButton.className = "dl-blue";
    modeButton.setAttribute("aria-pressed", String(s.run_mode === value));
  }

  element("span", "Motion Context", top);

  select(top, ["5", "22", "39", "56"].map(v => [v, v]), s.context_length, async v => { await invalidate(0); s.context_length = v; });

  element("small", "샘플러 / HyperFlow / LBH: Settings 설정 사용 · 24 fps", top);
  element("small", "LBH ON: 기본 해상도 생성 → 확대 → 마지막 4스텝 보정 · 설정 변경 시 재생성", top);

  if (s.source_mode_enabled !== false) {
  const source = row();

  select(source, [["new", "새 영상부터 시작"], ["video", "기존 영상 이어 만들기"]], s.start_mode, async v => { await invalidate(0); s.start_mode = v; });

  if (s.start_mode === "video") {

    const upload = element("input", null, source); upload.type = "file"; upload.accept = "video/*"; upload.style.display = "none";

    const uploadFile = async file => {

      if (!file || rt.busy || rt.running) return;

      rt.busy = true;

      try {

        const body = new FormData(); body.append("image", file); body.append("type", "input"); body.append("subfolder", "director_sources");

        const response = await api.fetchApi("/upload/image", { method: "POST", body });

        if (!response.ok) throw new Error("원본 영상 업로드에 실패했습니다.");

        const data = await response.json();

        await invalidate(0);

        s.source_video = data.subfolder ? `${data.subfolder}/${data.name}` : data.name;

        rt.preview = null;

        rt.message = "";

      } catch (e) { rt.message = e.message; }

      finally { rt.busy = false; save(); refresh(); }

    };

    upload.onchange = () => uploadFile(upload.files[0]);

    const choose = element("button", "원본 영상 불러오기 / 여기에 드롭", source);

    choose.disabled = rt.busy || rt.running;

    choose.onclick = () => upload.click();

    choose.ondragover = e => { e.preventDefault(); e.stopPropagation(); };

    choose.ondrop = e => { e.preventDefault(); e.stopPropagation(); void uploadFile(e.dataTransfer.files[0]); };

    if (s.source_video) {

      const filename = s.source_video.replaceAll("\\", "/");

      const split = filename.lastIndexOf("/");

      const media = { filename: filename.slice(split + 1), subfolder: filename.slice(0, Math.max(0, split)), type: "input" };

      const card = element("div", null, panel);

      card.style.cssText = "border:1px dashed #7dd5ac;border-radius:8px;padding:10px;background:#14252a;display:flex;flex-direction:column;gap:8px";

      const header = element("div", null, card);

      header.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap";

      const name = element("strong", media.filename, header);

      name.style.cssText = "overflow-wrap:anywhere;min-width:0";

      button(header, "원본 영상 삭제", async () => {

        await invalidate(0);

        s.source_video = "";

        delete s.cache_owner;

        rt.preview = null;

      });

      const video = element("video", null, card);

      video.src = viewURL(media);

      video.controls = true;

      video.playsInline = true;

      video.preload = "metadata";

      video.style.cssText = "display:block;width:100%;max-height:320px;object-fit:contain;background:#080c10;border-radius:5px";

      for (const event of ["pointerdown", "mousedown", "touchstart"]) {

        video.addEventListener(event, e => e.stopPropagation());

      }

      const info = element("small", "원본 영상 미리보기 · 재생 버튼으로 확인하세요.", card);

      video.addEventListener("loadedmetadata", () => {

        const seconds = Number.isFinite(video.duration) ? video.duration.toFixed(1) : "?";

        info.textContent = `${video.videoWidth} × ${video.videoHeight} · ${seconds}초`;

      });

      video.addEventListener("error", () => {

        info.textContent = "브라우저에서 재생할 수 없는 형식입니다. 원본 열기로 확인하세요.";

      });

      const open = element("a", "원본 열기", card);

      open.href = viewURL(media);

      open.target = "_blank";

      open.rel = "noopener";

      open.style.color = "#73d8ff";

    } else {

      element("span", "원본 영상을 선택하세요", source);

    }

    const colorRow = row();

    element("span", "원본 색감 맞추기 · 강도", colorRow);

    const colorStrength = element("input", null, colorRow);

    colorStrength.type = "number"; colorStrength.min = 0; colorStrength.max = 1; colorStrength.step = 0.1;

    colorStrength.value = s.source_color_strength ?? 0.5;

    colorStrength.style.width = "65px"; colorStrength.disabled = rt.busy || rt.running;

    colorStrength.onchange = () => { s.source_color_strength = Number(colorStrength.value); save(); };

    element("small", "0=끄기 · 0.5=기본 · 1=강하게. 추가 영상에만 적용됩니다.", colorRow);

    element("small", "마지막 구간의 움직임·오디오를 이어받고 원본 뒤에 저장합니다. 원본은 선택한 해상도·24fps로 변환됩니다.", panel);

  }

  }
  const timeline = section();
  const title = row(timeline);

  element("strong", "장면 타임라인", title);

  element("span", null, title).className = "dl-spacer";
  // Grouped toolbar: 만들기 | 승인 | 보기. Each group wraps as a unit, never a lone button.
  const tools = element("div", null, timeline); tools.className = "dl-tools";
  const toolGroup = label => {
    const g = element("div", null, tools); g.className = "dl-tgroup";
    if (label) element("span", label, g).className = "dl-tlabel";
    return g;
  };
  const makeGroup = toolGroup(""), approveGroup = toolGroup("승인"), viewGroup = toolGroup("보기"), labGroup = toolGroup("실험");
  button(makeGroup, "+ 장면 추가", () => { s.clips.push(newClip(hasExternal())); rt.selected = s.clips.length - 1; });
  if (window.DirectorPlusPromptStudio) {
    const studio = element("button", "✍ 프롬프트 작성", makeGroup);
    studio.className = "dl-accent";
    studio.title = "선택한 장면의 프롬프트를 PromptDirector로 작성합니다";
    studio.disabled = rt.busy || rt.running;
    studio.onclick = () => window.DirectorPlusPromptStudio.open(node, { scene: rt.selected });
  }

  // A reopened workflow only knows its last preview; check the disk cache once so scene
  // status and approvals match what can really be reused (runs and .ext loads already sync).
  if (s.cache_owner && !rt.cacheChecked && !rt.cacheChecking && !rt.cacheCheckFailed) {
    rt.cacheChecking = true;
    const owner = s.cache_owner;
    request(`/director_plus/extender/cache_state?${new URLSearchParams({ owner_id: owner, mode: "ref2va", motion_context: "true" })}`)
      .then(result => {
        // The node state is re-parsed while a workflow opens; reconcile whatever is current now.
        const current = rt.state?.long_video;
        if (!current || current.cache_owner !== owner) return;
        const checked = reconcileSceneCache(current, result);
        rt.cacheChecked = true; rt.cached = checked.cached; rt.needsRegeneration = checked.missing;
        save(); refresh();
      })
      .catch(() => { rt.cacheCheckFailed = true; })
      .finally(() => { rt.cacheChecking = false; });
  }

  // Start the timeline over as a fresh project. Settings (ON/OFF, run mode, Motion Context)
  // are kept; the disk cache is left alone because other workflows may still use it.
  const clearButton = button(title, "초기화", async () => {
    const approved = s.clips.filter(c => c.validated).length;
    if (!window.confirm(`장면 타임라인을 모두 지울까요?\n\n장면 ${s.clips.length}개(승인 ${approved}개)의 프롬프트·시드·길이·승인과 미리보기가 초기화되고 빈 장면 1개만 남습니다.\n저장한 .ext 프로젝트와 이미 만든 영상 파일은 그대로 남습니다.`)) return;
    s.project_id = crypto.randomUUID();
    delete s.cache_owner;
    delete s.last_preview;
    s.clips = [newClip(hasExternal())];
    Object.assign(rt, { selected: 0, cached: [], needsRegeneration: [], cacheChecked: true, preview: null, spans: null, scrollLeft: 0, scrollTo: null });
  });
  clearButton.className = "dl-red";
  clearButton.title = "모든 장면을 지우고 빈 장면 1개로 새로 시작합니다.";

  // Bulk approval, same rules as the per-card checkbox: approval is a contiguous prefix of
  // generated scenes, and un-approving keeps every cached scene so it can be re-approved.
  const bulkButton = (text, tip, action, parent = approveGroup) => {
    const b = element("button", text, parent);
    b.title = tip;
    b.disabled = rt.busy || rt.running;
    b.onclick = async () => {
      if (rt.busy || rt.running) return;
      rt.busy = true;
      try { rt.message = await action(); } catch (e) { rt.message = e.message; }
      finally { rt.busy = false; save(); refresh(); }
    };
    return b;
  };
  bulkButton("전체 승인", "생성된 장면을 앞에서부터 모두 승인합니다. 아직 생성되지 않은 장면에서 멈춥니다.", async () => {
    const start = s.clips.findIndex(c => !c.validated);
    if (start < 0) return "이미 모든 장면이 승인되어 있습니다.";
    let index = start;
    while (index < s.clips.length && rt.cached.includes(s.clips[index].id)) {
      await setValidated(index, true);
      index += 1;
    }
    const approved = index - start;
    rt.selected = Math.min(index, s.clips.length - 1); rt.scrollTo = rt.selected;
    if (!approved) return `장면 ${start + 1}이 아직 생성되지 않아 승인할 장면이 없습니다.`;
    return index < s.clips.length
      ? `장면 ${approved}개 승인 · 장면 ${index + 1}부터는 아직 생성되지 않았습니다.`
      : `장면 ${approved}개 승인 · 모든 장면 승인 완료`;
  });
  bulkButton("전체 해제", "모든 장면의 승인을 해제합니다. 생성된 캐시는 남으므로 다시 승인하면 재생성 없이 승인됩니다.", async () => {
    const approved = s.clips.filter(c => c.validated).length;
    if (!approved) return "승인된 장면이 없습니다.";
    await setValidated(0, false);
    rt.selected = 0; rt.scrollTo = 0;
    return `장면 ${approved}개의 승인을 해제했습니다. (캐시는 유지)`;
  });
  bulkButton("캐시 확인", "디스크에 저장된 장면 캐시를 다시 확인해 승인할 수 있는 장면과 재생성이 필요한 장면을 맞춥니다.", async () => {
    if (!s.cache_owner) return "아직 이 프로젝트로 생성한 기록이 없어 확인할 캐시가 없습니다.";
    const result = await request(`/director_plus/extender/cache_state?${new URLSearchParams({ owner_id: s.cache_owner, mode: "ref2va", motion_context: "true" })}`);
    const checked = reconcileSceneCache(s, result);
    rt.cacheChecked = true; rt.cacheCheckFailed = false; rt.cached = checked.cached; rt.needsRegeneration = checked.missing;
    const approvedN = s.clips.filter(c => c.validated).length;
    if (result.found === false) return "이 프로젝트의 캐시를 찾지 못했습니다. 생성 설정(LBH·오디오 재생성 등)이 바뀌었으면 그 설정의 캐시는 따로 저장됩니다.";
    return `캐시 확인: 장면 ${s.clips.length}개 중 ${checked.cached.length}개 사용 가능 · 승인 ${approvedN}개` +
      (checked.missing.length ? ` · 재생성 필요: 장면 ${checked.missing.map(id => s.clips.findIndex(c => c.id === id) + 1).join(", ")}` : "");
  });
  bulkButton("구간 묶기","장면 범위를 카드 한 장으로 묶어 짧게 보여 줍니다. 생성·캐시·승인은 그대로입니다.", async () => {
    const n = s.clips.length;
    if (n < 2) return "장면이 2개 이상일 때 묶을 수 있습니다.";
    const text = window.prompt(`묶을 장면 범위를 적으세요. 예: 3-8 (장면 1~${n})`, "");
    if (!text) return "";
    const m = String(text).match(/^\s*(\d+)\s*[-~–]\s*(\d+)\s*$/);
    if (!m) throw new Error("범위는 3-8처럼 적어 주세요.");
    let a = Number(m[1]) - 1, b = Number(m[2]) - 1;
    if (a > b) [a, b] = [b, a];
    if (a < 0 || b >= n || b - a < 1) throw new Error(`장면 1~${n} 안에서 2개 이상을 지정하세요.`);
    const index = id => s.clips.findIndex(c => c.id === id);
    if ((s.groups || []).some(g => !(index(g.to) < a || index(g.from) > b))) throw new Error("이미 묶인 구간과 겹칩니다. 먼저 그 묶음을 풀어 주세요.");
    (s.groups ||= []).push({ id: crypto.randomUUID(), from: s.clips[a].id, to: s.clips[b].id });
    rt.scrollTo = a;
    return `장면 ${a + 1}–${b + 1}을 카드 한 장으로 묶었습니다.`;
  }, viewGroup);
  const foldOn = s.fold_validated !== false;
  const foldButton = bulkButton("승인 장면 접기", `${foldOn ? "켜짐" : "꺼짐"} — 켜면 앞에서부터 승인된 장면(2개 이상)을 카드 한 장으로 접습니다. 누르면 ${foldOn ? "끕니다" : "켭니다"}.`, async () => {
    s.fold_validated = !foldOn;
    rt.openGroups?.delete("auto");
    return "";
  }, viewGroup);
  foldButton.setAttribute("aria-pressed", String(foldOn));
  foldButton.className = "dl-switch" + (foldOn ? " on" : "");
  // Experimental (xyzDist/H3-LongTakeNoCuts idea): resample each continued scene at a low denoise
  // so the next scene inherits a refreshed tail. Changing it resets generated, unapproved scenes.
  const refineOn = !!s.refine?.enabled;
  const refineButton = bulkButton("이어받기 보정", `${refineOn ? "켜짐" : "꺼짐"} — 장면 2부터, 생성한 장면을 한 번 더 짧게 샘플링(${s.refine?.steps ?? 5}스텝 · denoise ${s.refine?.denoise ?? 0.55})해서 장면을 이어 갈수록 인물이 뭉개지는 것을 줄입니다. 앞 장면에서 이어받은 구간은 그대로 두고 그 뒤로 서서히 보정본으로 바뀌며, 소리는 원래 것을 씁니다. 장면마다 샘플링이 그만큼 늘어나고 배경이 조금 바뀔 수 있습니다. 바꾸면 승인하지 않은 생성 장면은 다시 만듭니다. 누르면 ${refineOn ? "끕니다" : "켭니다"}.`, async () => {
    s.refine = { ...(s.refine || {}), enabled: !refineOn, steps: s.refine?.steps ?? 5, denoise: s.refine?.denoise ?? 0.55 };
    const reset = await rt.invalidateUnapproved?.();
    return (s.refine.enabled ? "이어받기 보정 켬" : "이어받기 보정 끔") + (reset ? " · 승인하지 않은 생성 장면을 다시 만들도록 초기화했습니다." : "");
  }, labGroup);
  refineButton.setAttribute("aria-pressed", String(refineOn));
  refineButton.className = "dl-switch" + (refineOn ? " on" : "");
  title.append(clearButton); // destructive action last, at the far right

  const preview = rt.preview || s.last_preview?.video;
  const spans = rt.spans || s.last_preview?.scenes || [];
  rt.selected = Math.max(0, Math.min(rt.selected, s.clips.length - 1));

  // ---- scene groups (resolved before the strip so the number bar can open them)
  if (!Array.isArray(s.groups)) s.groups = [];
  const clipIndex = id => s.clips.findIndex(c => c.id === id);
  s.groups = s.groups.filter(g => g && clipIndex(g.from) >= 0 && clipIndex(g.to) > clipIndex(g.from));
  let approvedEnd = -1;
  while (approvedEnd + 1 < s.clips.length && s.clips[approvedEnd + 1].validated) approvedEnd += 1;
  // A sealed range ("여기서 고정") keeps its own card; the auto fold only gathers approvals after it.
  if (!s.group_notes || typeof s.group_notes !== "object") s.group_notes = {};
  for (const id of Object.keys(s.group_notes)) if (clipIndex(id) < 0 || !String(s.group_notes[id] || "").trim()) delete s.group_notes[id];
  const sealedAt = s.fold_after ? clipIndex(s.fold_after) : -1;
  if (s.fold_after && sealedAt < 0) delete s.fold_after;
  const auto = s.fold_validated !== false && approvedEnd - (sealedAt + 1) >= 1 ? { kind: "auto", a: sealedAt + 1, b: approvedEnd } : null;
  const groups = [];
  let groupFloor = 0;
  for (const g of [...s.groups].sort((x, y) => clipIndex(x.from) - clipIndex(y.from))) {
    let a = Math.max(clipIndex(g.from), groupFloor), b = clipIndex(g.to);
    if (auto && !(b < auto.a || a > auto.b)) { if (a < auto.a) b = auto.a - 1; else a = auto.b + 1; } // the auto fold wins an overlap
    if (b - a >= 1) { groups.push({ kind: "manual", a, b, g }); groupFloor = b + 1; }
  }
  if (auto) groups.push(auto);
  groups.sort((x, y) => x.a - y.a);
  if (s.clips.length >= 3) {
    const bar = element("div", null, timeline); bar.className = "dl-scenebar";
    element("span", "장면", bar).className = "dl-label";
    s.clips.forEach((c, i) => {
      const b = element("button", String(i + 1), bar); b.type = "button";
      b.className = "dl-scene-num" + (c.validated ? " ok" : rt.cached.includes(c.id) ? " made" : "") + (i === rt.selected ? " sel" : "");
      b.title = `장면 ${i + 1} · ${c.duration}초 · ${c.validated ? "승인" : rt.cached.includes(c.id) ? "생성됨" : "대기"}`;
      b.onclick = e => {
        e.stopPropagation();
        const g = groups.find(x => i >= x.a && i <= x.b);
        if (g) (rt.openGroups ||= new Set()).add(g.kind === "auto" ? "auto" : g.g.id);
        rt.selected = i; rt.scrollTo = i; save(); refresh();
      };
    });
  }

  // Extender-style strip: fixed-width tall cards side by side, each with its own editor.
  const strip = element("div", null, timeline); strip.className = "dl-strip";
  const cards = element("div", null, strip); cards.className = "dl-cards";
  const cardOf = []; // clip index -> its card, or the folded group card that holds it
  const barOf = []; // first clip index of an open group -> its fold bar
  const CARD_STEP = 492;
  let syncNav = () => {};
  const settle = () => { rt.scrollLeft = cards.scrollLeft; syncNav(); };
  // Own easing instead of native smooth scrolling, which stalls in some embedded views.
  const glide = left => {
    const from = cards.scrollLeft, to = Math.max(0, Math.min(left, cards.scrollWidth - cards.clientWidth));
    const t0 = performance.now();
    cards.style.scrollSnapType = "none";
    const step = now => {
      const k = Math.min(1, (now - t0) / 260);
      cards.scrollLeft = from + (to - from) * (1 - Math.pow(1 - k, 3));
      if (k < 1) requestAnimationFrame(step); else { cards.style.scrollSnapType = ""; settle(); }
    };
    requestAnimationFrame(step);
  };
  if (s.clips.length >= 3) {
    const nav = (text, dir, cls) => {
      const b = element("button", text, strip); b.className = "dl-nav " + cls; b.type = "button";
      b.onclick = e => { e.stopPropagation(); glide(cards.scrollLeft + dir * CARD_STEP); };
      for (const name of ["pointerdown", "mousedown"]) b.addEventListener(name, e => e.stopPropagation());
      return b;
    };
    const prev = nav("◀", -1, "prev"), next = nav("▶", 1, "next");
    syncNav = () => {
      prev.disabled = cards.scrollLeft <= 16;
      next.disabled = cards.scrollLeft + cards.clientWidth >= cards.scrollWidth - 16;
    };
    cards.addEventListener("scroll", () => syncNav());
    // The panel can be built while the node is off-screen (zero width); re-check once it has a size.
    if (window.ResizeObserver) new ResizeObserver(() => syncNav()).observe(cards);
  }
  // The panel is rebuilt on every change; restore the strip position once it is mounted.
  // Scroll events are ignored until then so the fresh element (at 0) cannot overwrite it.
  const restoreLeft = rt.scrollLeft || 0;
  let restored = false;
  cards.addEventListener("scroll", () => { if (restored) rt.scrollLeft = cards.scrollLeft; });
  setTimeout(() => {
    restored = true;
    if (rt.scrollTo != null) {
      const target = (rt.scrollToBar && barOf[rt.scrollTo]) || cardOf[rt.scrollTo];
      rt.scrollToBar = false;
      rt.scrollTo = null;
      if (target) glide(target.offsetLeft - cards.offsetLeft - 4);
    } else if (restoreLeft) cards.scrollLeft = restoreLeft;
    settle();
  }, 0);

  rt.validateEls = [];
  const makePreview = (parent, span, available, needsRegeneration) => {
    if (preview && span && available) {
      const video = element("video", null, parent); video.className = "dl-preview";
      video.controls = true; video.preload = "none"; video.playsInline = true;
      const startTime = Number(span.start);
      const endTime = Number(span.end);
      const lastTime = Math.max(startTime, endTime - 1 / 24);
      video.addEventListener("loadedmetadata", () => { video.currentTime = startTime; });
      video.addEventListener("play", () => {
        panel.querySelectorAll("video").forEach(other => { if (other !== video) other.pause(); });
        if (!video.seeking && (video.currentTime < startTime - 0.02 || video.currentTime >= lastTime)) {
          video.currentTime = startTime;
        }
      });
      video.addEventListener("timeupdate", () => {
        if (!video.seeking && !video.paused && video.currentTime >= endTime - 0.02) video.pause();
      });
      // timeupdate fires only every ~250 ms, so a span could run into the next scene; poll while playing.
      let stopTimer = null;
      const stopWatch = () => { clearInterval(stopTimer); stopTimer = null; };
      video.addEventListener("play", () => {
        stopWatch();
        stopTimer = setInterval(() => {
          if (!video.seeking && !video.paused && video.currentTime >= endTime - 1 / 24) { video.pause(); video.currentTime = lastTime; }
        }, 40);
      });
      video.addEventListener("pause", stopWatch);
      video.addEventListener("ended", stopWatch);
      video.addEventListener("seeked", () => {
        if (video.currentTime < startTime - 0.02) video.currentTime = startTime;
        else if (video.currentTime >= endTime) video.currentTime = lastTime;
      });
      video.src = viewURL(preview);
      video.addEventListener("error", () => {
        video.replaceWith(Object.assign(document.createElement("div"), {className:"dl-preview dl-empty", textContent:"미리보기 파일을 찾을 수 없습니다"}));
      });
      for (const name of ["pointerdown", "mousedown", "touchstart"]) video.addEventListener(name, e => e.stopPropagation());
    } else {
      const empty = element("div", available ? "▶ 실행 완료 후 미리보기" : needsRegeneration ? "↻ 캐시 없음 · 재생성 필요" : "▶ 생성 대기", parent);
      empty.className = "dl-preview dl-empty";
    }
  };
  const renderClip = (c, i) => {
    const span = spans.find(x => x.id === c.id);
    const available = rt.cached.includes(c.id) || (!rt.cacheChecked && !!span);
    const needsRegeneration = (rt.needsRegeneration || []).includes(c.id);
    const label = c.validated ? "✓ 승인 완료" : available ? "◷ 검토 중" : needsRegeneration ? "↻ 재생성 필요" : "Ⅱ 대기";
    const locked = c.validated || rt.busy || rt.running;
    const card = element("div", null, cards); card.className = "dl-card" + (i === rt.selected ? " selected" : "");
    cardOf[i] = card;
    card.addEventListener("click", e => {
      if (rt.busy || rt.running || rt.selected === i) return;
      if (e.target.closest("button, input, select, textarea, a, video, label")) return;
      rt.selected = i;
      save();
      refresh();
    });

    const head = element("div", null, card); head.className = "dl-card-head";
    element("strong", `장면 ${i + 1}`, head).className = "dl-card-title";
    const isNextScene = !c.validated && s.clips.slice(0, i).every(x => x.validated);
    if (isNextScene) element("span", "● NEXT", head).className = "dl-next";
    element("span", null, head).className = "dl-spacer";
    // Validated checkbox, same rules as the Extender: approval is a contiguous
    // prefix, and unticking keeps the cached segment so it can be re-ticked.
    const canValidate = c.validated || (available && s.clips.slice(0, i).every(x => x.validated));
    if (canValidate || (available && !c.validated)) {
      const toggle = element("label", null, head); toggle.className = "dl-validate" + (c.validated ? " on" : "");
      rt.validateEls[i] = toggle;
      const box = element("input", null, toggle); box.type = "checkbox"; box.checked = !!c.validated;
      element("span", c.validated ? "승인 완료" : "승인", toggle);
      box.disabled = rt.busy || rt.running || !canValidate;
      toggle.title = canValidate ? (c.validated ? "클릭하면 승인을 해제합니다. 이후 장면의 승인도 함께 해제됩니다." : "클릭하면 이 장면을 승인합니다.") : "앞 장면을 먼저 승인하세요.";
      box.onchange = async () => {
        if (rt.busy || rt.running) return;
        rt.busy = true;
        try {
          await setValidated(i, box.checked);
          // Like the Extender, approving hands focus to the next clip.
          if (box.checked && i + 1 < s.clips.length) { rt.selected = i + 1; rt.scrollTo = i + 1; }
          rt.message = "";
        } catch (e) { rt.message = e.message; }
        finally { rt.busy = false; save(); refresh(); }
      };
    } else {
      const badge = element("span", label, head); badge.className = "dl-status";
      if (!needsRegeneration) {
        badge.textContent = "";
        const pause = element("span", null, badge); pause.className = "dl-pause-icon";
        pause.setAttribute("aria-hidden", "true");
        element("span", "대기", badge);
      }
    }

    makePreview(card, span, available, needsRegeneration);

    const useExternal = c.use_external_prompt ?? !String(c.prompt || "").trim();
    const promptHead = element("div", null, card); promptHead.className = "dl-card-row";
    element("span", "프롬프트", promptHead).className = "dl-label";
    element("span", null, promptHead).className = "dl-spacer";
    element("span", "외부 프롬프트", promptHead).className = "dl-label";
    const externalToggle = button(promptHead, useExternal ? "ON" : "OFF", async () => { c.use_external_prompt = !useExternal; });
    externalToggle.className = "dl-toggle"; externalToggle.setAttribute("aria-pressed", String(useExternal));
    externalToggle.disabled ||= c.validated;
    externalToggle.title = "ON: 실행할 때 Prompt Freeze의 출력을 이 장면에 저장합니다. OFF: 장면 프롬프트를 유지합니다.";

    const prompt = element("textarea", null, card); prompt.className = "dl-card-prompt"; prompt.value = c.prompt || "";
    prompt.placeholder = useExternal ? "ON: 실행 시 외부 프롬프트를 가져와 저장합니다." : "이 장면에 사용할 프롬프트";
    // Read-only rather than disabled, so an approved scene's long prompt can still be scrolled and read.
    prompt.readOnly = locked;
    if (locked) prompt.classList.add("locked");
    // Same as the Extender: the wheel scrolls a long prompt instead of zooming the graph.
    prompt.dataset.captureWheel = "true";
    prompt.addEventListener("mouseenter", () => {
      const nodes2 = typeof globalThis.LiteGraph?.vueNodesMode === "boolean" ? globalThis.LiteGraph.vueNodesMode : Boolean(prompt.closest?.(".lg-node-widget"));
      if (!nodes2 || document.activeElement === prompt) return;
      try { prompt.focus({ preventScroll: true }); } catch { prompt.focus(); }
    });
    prompt.onchange = async () => { if (prompt.readOnly) return; try { await invalidate(i); c.prompt = prompt.value; save(); } catch (e) { rt.message = e.message; } refresh(); };

    const numbers = element("div", null, card); numbers.className = "dl-card-grid";
    const number = (label, key, min, max, step = 1) => {
      const wrap = element("label", null, numbers); wrap.className = "dl-field";
      element("span", label, wrap).className = "dl-label";
      const input = element("input", null, wrap); input.type = "number"; input.min = min; input.max = max; input.step = step; input.value = c[key];
      input.disabled = locked;
      input.onchange = async () => { try { await invalidate(i); c[key] = Number(input.value); save(); refresh(); } catch (e) { rt.message = e.message; refresh(); } };
    };
    number("Seed", "seed", 0, Number.MAX_SAFE_INTEGER);
    const dice = button(numbers, "🎲", async () => { await invalidate(i); c.seed = Math.floor(Math.random() * 1e12); });
    dice.className = "dl-dice"; dice.title = "새 시드"; dice.disabled ||= c.validated;
    number("길이(초)", "duration", 1, 1000, "any");
    const fit = element("button", "레퍼런스 길이에 맞추기", numbers);
    fit.className = "dl-small"; fit.disabled = locked;
    fit.title = "타임라인의 첫 영상 레퍼런스(자르기 구간)와 생성 프레임 수가 같아지도록 길이를 맞춥니다";
    fit.onclick = async () => {
      if (locked) return;
      try {
        const fitted = referenceFit();
        if (Math.abs(Number(c.duration) - fitted.seconds) > 1e-6) { await invalidate(i); c.duration = fitted.seconds; }
        rt.message = `장면 ${i + 1}: ${fitted.label} ${fitted.source.toFixed(2)}초(${fitted.sourceFrames}프레임) → 길이 ${fitted.seconds}초(${fitted.frames}프레임, 레퍼런스와 같음)`;
      } catch (e) { rt.message = e.message; }
      save(); refresh();
    };

    // Per-scene switches for Settings features (Motion Lab, audio regen, face refine): they apply only while the
    // Settings toggle is on. A scene without the field counts as ON, so turning the Settings toggle
    // on keeps covering every scene; while it is off the row is dimmed.
    const sceneSwitch = (key, label, master, masterName, help) => {
      const on = c[key] !== false;
      const masterValue = settingValue(master);
      const row = element("div", null, card); row.className = "dl-card-row" + (masterValue === false ? " dl-master-off" : "");
      element("span", label, row).className = "dl-label";
      element("span", null, row).className = "dl-spacer";
      if (masterValue === false) element("span", "Settings에서 꺼짐", row).className = "dl-muted dl-master-note";
      const toggle = button(row, on ? "ON" : "OFF", async () => {
        if (c.validated || settingValue(master) === false) return;
        await invalidate(i);
        c[key] = !on;
      });
      toggle.className = "dl-toggle"; toggle.setAttribute("aria-pressed", String(on));
      toggle.disabled ||= c.validated || masterValue === false;
      toggle.title = (masterValue === false ? `지금은 Settings의 ${masterName}이 꺼져 있어 바꿀 수 없고 실행되지 않습니다(Settings를 켜면 바꿀 수 있음). ` : "")
        + `Settings의 「${masterName}」이 켜져 있을 때만 적용됩니다. ${help} 바꾸면 이 장면부터 다시 생성합니다.`;
    };
    sceneSwitch("audio_regen", "🔊 오디오 재생성", "audio_regen_enabled", "🔊 오디오 재생성",
      "ON: 이 장면의 소리를 30스텝으로 다시 만들어 잡음을 줄입니다(장면당 약 1~2분). OFF: 1차 생성 소리를 그대로 씁니다.");
    sceneSwitch("face_refine", "🙂 얼굴 다듬기", "face_refine_enabled", "🙂 얼굴 다듬기",
      "ON: 이 장면의 얼굴을 찾아 크게 잘라 다시 그린 뒤 붙입니다. 얼굴이 작거나 흐트러진 장면에 효과가 크고, 이미 깔끔한 얼굴은 조금 부드러워질 수 있습니다(장면당 샘플링 한 번 추가). 얼굴이 안 보이는 장면은 그대로 둡니다. OFF: 그대로 생성합니다.");
    sceneSwitch("derope", "🌀 모션랩 (빠른 동작 보정)", "derope_enabled", "🌀 Motion Lab (de-rope)",
      "ON: 이 장면의 빠른 동작 구간을 늘려 다시 생성해 뭉개짐을 줄입니다(시간 약 3배). OFF: 이 장면은 그대로 생성합니다.");

    const foot = element("div", null, card); foot.className = "dl-card-row";
    const openGroup = groups.find(g => i >= g.a && i <= g.b && isOpen(g));
    if (openGroup) {
      const fold = button(foot, `장면 ${openGroup.a + 1}–${openGroup.b + 1} 접기`, async () => { setOpen(openGroup, false); rt.selected = openGroup.a; rt.scrollTo = openGroup.a; });
      fold.className = "dl-small"; fold.title = "이 장면이 들어 있는 구간을 다시 카드 한 장으로 접습니다";
    }
    const again = button(foot, "다시 생성", async () => { rt.selected = i; await invalidate(i); save(); await app.queuePrompt(0, 1); });
    again.className = "dl-small";
    const remove = button(foot, "삭제", async () => { if (s.clips.length < 2) return; await invalidate(i); s.clips.splice(i, 1); rt.selected = Math.min(rt.selected, s.clips.length - 1); });
    remove.className = "dl-small"; remove.disabled ||= s.clips.length < 2;
    element("span", null, foot).className = "dl-spacer";
    element("span", `${c.duration}초`, foot).className = "dl-muted";
  };

  // Scene groups only change the view: clips, caches, approval and Motion Context stay per scene.
  // "auto" folds the approved prefix; manual groups are clip-id ranges the user picked.
  const groupKey = g => g.kind === "auto" ? "auto" : g.g.id;
  const isOpen = g => (rt.openGroups ||= new Set()).has(groupKey(g));
  const setOpen = (g, open) => { (rt.openGroups ||= new Set())[open ? "add" : "delete"](groupKey(g)); };
  const renderGroup = g => {
    const clips = s.clips.slice(g.a, g.b + 1);
    const box = element("div", null, cards);
    box.className = "dl-card dl-group" + (rt.selected >= g.a && rt.selected <= g.b ? " selected" : "");
    for (let k = g.a; k <= g.b; k += 1) cardOf[k] = box;
    const head = element("div", null, box); head.className = "dl-card-head";
    element("strong", `장면 ${g.a + 1}–${g.b + 1}`, head).className = "dl-card-title";
    element("span", null, head).className = "dl-spacer";
    element("span", g.kind === "auto" ? "승인된 장면" : g.g.sealed ? "고정 묶음" : "묶음", head).className = "dl-status";
    const seconds = Math.round(clips.reduce((t, c) => t + Number(c.duration || 0), 0) * 1000) / 1000;
    const approvedN = clips.filter(c => c.validated).length;
    const cachedN = clips.filter(c => rt.cached.includes(c.id)).length;
    const noteKey = clips[0].id;
    const note = element("textarea", null, box); note.className = "dl-group-note";
    note.value = s.group_notes[noteKey] || "";
    note.placeholder = "이 구간 설명 (예: 도입 — 무대 등장, 손 인사)";
    note.title = "이 묶음이 어떤 장면인지 적어 두는 메모입니다. 생성에는 쓰이지 않습니다.";
    note.dataset.captureWheel = "true";
    for (const name of ["pointerdown", "mousedown"]) note.addEventListener(name, e => e.stopPropagation());
    note.onchange = () => {
      const text = note.value.trim();
      if (text) s.group_notes[noteKey] = note.value; else delete s.group_notes[noteKey];
      save();
    };
    element("div", `${clips.length}개 장면 · 설정 길이 ${seconds}초`, box).className = "dl-group-line";
    element("div", `승인 ${approvedN}/${clips.length} · 생성됨 ${cachedN}/${clips.length}`, box).className = "dl-group-line dl-muted";
    // The chain preview is one video with a span per scene; the group plays from its first
    // previewed scene to its last, so the whole range runs as one clip.
    const groupSpans = clips.map(c => spans.find(x => x.id === c.id)).filter(x => x && (rt.cached.includes(x.id) || !rt.cacheChecked));
    const groupSpan = groupSpans.length ? { start: Math.min(...groupSpans.map(x => Number(x.start))), end: Math.max(...groupSpans.map(x => Number(x.end))) } : null;
    const partial = groupSpans.length && groupSpans.length < clips.length ? ` · 미리보기에 있는 장면 ${groupSpans.length}/${clips.length}개만` : "";
    element("div", `구간 전체 미리보기 (장면 ${g.a + 1}–${g.b + 1})${partial}`, box).className = "dl-label";
    makePreview(box, groupSpan, !!groupSpan, clips.some(c => (rt.needsRegeneration || []).includes(c.id)));
    element("div", `다음 장면은 장면 ${g.b + 1} 끝에서 이어집니다`, box).className = "dl-group-line dl-muted";
    const list = element("div", null, box); list.className = "dl-group-list";
    clips.forEach((c, k) => {
      const index = g.a + k;
      const rowEl = element("button", null, list); rowEl.type = "button"; rowEl.className = "dl-group-row";
      const mark = c.validated ? "✓" : rt.cached.includes(c.id) ? "◷" : "Ⅱ";
      element("span", `${mark} 장면 ${index + 1}`, rowEl).className = "dl-group-num";
      element("span", `${c.duration}초`, rowEl).className = "dl-muted";
      element("span", String(c.prompt || (c.use_external_prompt ? "(외부 프롬프트)" : "")).replace(/\s+/g, " ").slice(0, 70), rowEl).className = "dl-group-text";
      rowEl.title = `장면 ${index + 1}을 펼쳐서 봅니다`;
      rowEl.onclick = e => { e.stopPropagation(); setOpen(g, true); rt.selected = index; rt.scrollTo = index; save(); refresh(); };
    });
    const foot = element("div", null, box); foot.className = "dl-card-row";
    const open = button(foot, "펼치기", async () => { setOpen(g, true); rt.scrollTo = g.a; rt.scrollToBar = true; });
    open.className = "dl-small";
    if (g.kind === "manual") {
      const ungroup = button(foot, "묶음 풀기", async () => {
        s.groups = s.groups.filter(x => x !== g.g); setOpen(g, false); rt.scrollTo = g.a;
        if (g.g.sealed && s.fold_after === g.g.to) {
          // Hand the seal back to the previous sealed range, if any, so later approvals fold after it.
          const previous = s.groups.filter(x => x.sealed).sort((x, y) => clipIndex(y.to) - clipIndex(x.to))[0];
          if (previous) s.fold_after = previous.to; else delete s.fold_after;
        }
      });
      ungroup.className = "dl-small";
    } else {
      // Freeze the approved fold at its current end: it becomes a fixed card, and the next
      // approvals gather into a new fold that starts after it.
      const seal = element("button", "여기서 고정", foot); seal.type = "button"; seal.className = "dl-small";
      seal.title = "지금 승인된 장면 묶음을 고정합니다. 다음에 승인하는 장면은 이 묶음에 합쳐지지 않고 새 묶음으로 모입니다.";
      seal.disabled = rt.busy || rt.running;
      seal.onclick = e => {
        e.stopPropagation();
        (s.groups ||= []).push({ id: crypto.randomUUID(), from: s.clips[g.a].id, to: s.clips[g.b].id, sealed: true });
        s.fold_after = s.clips[g.b].id;
        setOpen(g, false);
        rt.message = `장면 ${g.a + 1}–${g.b + 1}을 고정했습니다. 다음에 승인하는 장면은 장면 ${g.b + 2}부터 새 묶음으로 모입니다.`;
        save(); refresh();
      };
    }
    element("span", null, foot).className = "dl-spacer";
    element("span", `${seconds}초`, foot).className = "dl-muted";
  };
  const renderGroupBar = g => {
    const bar = element("button", null, cards); bar.type = "button"; bar.className = "dl-group-bar";
    barOf[g.a] = bar;
    element("span", `◀ 장면 ${g.a + 1}–${g.b + 1} 접기`, bar);
    bar.title = (g.kind === "auto" ? "승인된 장면을 다시 접습니다" : "이 묶음을 다시 접습니다")
      + (s.group_notes[s.clips[g.a].id] ? `\n${s.group_notes[s.clips[g.a].id]}` : "");
    for (const name of ["pointerdown", "mousedown"]) bar.addEventListener(name, e => e.stopPropagation());
    bar.onclick = e => { e.stopPropagation(); setOpen(g, false); rt.scrollTo = g.a; refresh(); };
  };
  const renderCards = () => {
    for (let i = 0; i < s.clips.length;) {
      const g = groups.find(x => x.a === i);
      if (g && !isOpen(g)) { renderGroup(g); i = g.b + 1; continue; }
      if (g) renderGroupBar(g);
      renderClip(s.clips[i], i);
      i += 1;
    }
  };
  renderCards();

  const summary = row(timeline);
  button(summary, "▶ 생성 / 실행", async () => { save(); await app.queuePrompt(0, 1); }).className = "dl-blue";
  element("span", `설정 길이 ${s.clips.reduce((sum, c) => sum + Number(c.duration), 0)}초 · 승인 ${s.clips.filter(c => c.validated).length} / ${s.clips.length}`, summary);
  element("span", null, summary).className = "dl-spacer";
  element("small", "최종 길이는 겹치는 문맥 구간만큼 줄어듭니다.", summary).className = "dl-muted";

  const projects = row(section());

  button(projects, "프로젝트 저장 (.ext)", async () => {
    const widgets = Object.fromEntries(node.widgets.filter(w => ["width", "height", "duration", "ref_image_size", "frame_rate", "mode", "builder_state"].includes(w.name)).map(w => [w.name, w.value]));
    const studio = window.DirectorPlusPromptStudio?.exportState?.(node) || null;
    const result = await request("/director_plus/project/save", {state, widgets, ...(studio ? {studio} : {})});
    const link = element("a"); link.href = api.apiURL('/director_plus/extender/project/download?' + new URLSearchParams({token: result.token}));
    link.download = "Director_Project.ext"; link.click();
  });

  const load = element("input", null, projects); load.type = "file"; load.accept = ".ext,.json"; load.style.display = "none";

  load.onchange = async () => {
    if (!load.files?.[0] || rt.busy || rt.running) return;
    if (window.DirectorPlusPromptStudio?.isBusy?.(node)) {
      rt.message = "프롬프트 작성 창 작업이 끝난 뒤에 불러오세요."; load.value = ""; refresh(); return;
    }
    rt.busy = true;
    refresh();
    try {
      let incoming;
      let importedDirector = null;
      if (load.files[0].name.toLowerCase().endsWith(".ext")) {
        const body = new FormData(); body.append("project_file", load.files[0]);
        const response = await api.fetchApi("/director_plus/project/load", {method: "POST", body});
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "프로젝트 복원 실패");
        importedDirector = result.director;
        incoming = importedDirector.state.long_video;
      } else {
        incoming = JSON.parse(await load.files[0].text());
      }
      if (!Array.isArray(incoming.clips) || !incoming.clips.length || !incoming.project_id ||
          incoming.clips.some(c => !c || typeof c.id !== "string") ||
          new Set(incoming.clips.map(c => c.id)).size !== incoming.clips.length) throw new Error("장면 설정 파일이 아닙니다.");
      if (s.source_mode_enabled === false) {
        if (incoming.start_mode === "video") delete incoming.cache_owner;
        incoming.source_mode_enabled = false; incoming.start_mode = "new";
        delete incoming.source_video; delete incoming.source_color_strength;
      }
      const result = incoming.cache_owner
        ? await request('/director_plus/extender/cache_state?' + new URLSearchParams({owner_id: incoming.cache_owner, mode: "ref2va", motion_context: "true"}))
        : {found: false};
      const checked = reconcileSceneCache(incoming, result);
      if (importedDirector) {
        Object.assign(state, importedDirector.state);
        for (const [name, value] of Object.entries(importedDirector.widgets)) {
          const widget = node.widgets.find(w => w.name === name);
          if (widget) widget.value = value;
        }
      }
      state.long_video = incoming;
      const matched = applyProjectSettings(incoming);
      rt.cached = checked.cached; rt.needsRegeneration = checked.missing; rt.cacheChecked = true;
      rt.preview = null; rt.spans = null;
      rt.selected = Math.max(0, incoming.clips.findIndex(c => !c.validated));
      rt.message = checked.missing.length
        ? '설정 불러오기 완료 · 재생성 필요 ' + checked.missing.length + '개 · 프롬프트와 시드는 유지했습니다.'
        : '설정 불러오기 완료 · 캐시 확인 완료';
      if (matched) rt.message += ` · Settings를 프로젝트 설정으로 맞춤 (${matched})`;
      if (importedDirector?.studio && window.DirectorPlusPromptStudio?.importState?.(node, importedDirector.studio))
        rt.message += " · 프롬프트 작성 창 상태도 불러옴";
      save();
    } catch (e) { rt.message = '설정을 불러오지 못했습니다: ' + e.message; }
    finally { rt.busy = false; refresh(); }
  };

  button(projects, "프로젝트 불러오기", () => load.click());

  element("span", null, projects).className = "dl-spacer";
  if (preview) {
    const link = element("a", "↓ 완성 영상 열기 / 저장", projects);
    link.className = "dl-button dl-blue"; link.href = viewURL(preview); link.target = "_blank"; link.rel = "noopener";
  } else {
    const download = button(projects, "↓ 완성 영상 열기 / 저장", () => {}); download.disabled = true;
  }
  element("small", "영상은 실행 후 자동 저장 · .ext는 장면·레퍼런스·캐시·프롬프트 작성 상태 보관 · 모델/Settings는 워크플로우도 함께 저장", projects).className = "dl-muted";

  if (rt.message) { const message = element("div", rt.message, panel); message.style.color = "#ffbc80"; }

  return panel;

}

// A .ext remembers the LBH settings it was generated with. LBH changes the output size and is part
// of the cache identity, so put it back on the workflow's controls (the Settings subgraph or an
// unlinked Generate node); otherwise the next run would regenerate every approved scene. Audio regen
// and Motion Lab are per scene and not part of the identity, so they are left as the workflow has them.
const PROJECT_SETTING_WIDGETS = [
  { lbh: "lbh_latent_upscale_enabled", scale: "lbh_latent_upscale_scale", full: "lbh_full_first_pass" },
  { lbh: "lbh_enabled", scale: "lbh_scale", full: "lbh_full_first_pass" },
];
function applyProjectSettings(long) {
  if (!("lbh" in long)) return null;
  const lbh = long.lbh || null;
  const full = Boolean(lbh && lbh.first_pass === "full");
  let applied = false;
  for (const target of app.graph?._nodes || []) {
    const find = name => target.widgets?.find(w => w.name === name && !(target.inputs || []).some(i => i.name === name && i.link != null));
    for (const names of PROJECT_SETTING_WIDGETS) {
      const lbhWidget = find(names.lbh);
      if (!lbhWidget) continue;
      window.DirectorPlusLbhToggle?.remember(target, full, Boolean(lbh));
      lbhWidget.value = Boolean(lbh);
      if (lbh && find(names.scale)) find(names.scale).value = Number(lbh.scale);
      if (find(names.full)) find(names.full).value = full;
      applied = true;
      target.setDirtyCanvas?.(true, true);
      break;
    }
  }
  if (!applied) return null;
  return `LBH ${lbh ? `${Number(lbh.scale)}x ${full ? "8+4" : "4+4"}` : "OFF"}`;
}

function directors() { return (app.graph?._nodes || []).filter(n => n.comfyClass === "DirectorPlusTimeline" && n.__directorLong); }

// The Settings toggle (or an unlinked widget of the same name on Director · 긴 영상) is the master
// switch for a per-scene toggle. true / false, or null when no such widget is on the canvas.
const MASTER_SETTINGS = ["derope_enabled", "audio_regen_enabled", "face_refine_enabled"];
function settingValue(name) {
  for (const target of app.graph?._nodes || []) {
    const widget = target.widgets?.find(w => w.name === name);
    if (!widget) continue;
    if ((target.inputs || []).some(i => i.name === name && i.link != null)) continue;
    return Boolean(widget.value);
  }
  return null;
}

// Cards only redraw on their own events; follow the Settings toggles so the card rows dim at once.
// These switches are not part of the cache identity, so approved scenes stay valid; scenes that were
// generated but not approved were made with the old value and are reset (they are regenerated anyway).
setInterval(() => {
  const value = MASTER_SETTINGS.map(settingValue).join();
  for (const node of directors()) {
    const rt = node.__directorLong;
    if (rt.masterSettings === value) continue;
    const first = rt.masterSettings === undefined;
    rt.masterSettings = value;
    node.__directorPlusH3Render?.();
    if (!first && !rt.busy && !rt.running) rt.invalidateUnapproved?.().catch(() => {});
  }
}, 500);

api.addEventListener("director-plus-long-state", event => {

  const d = event.detail;

  for (const node of directors()) {

    const rt = node.__directorLong;

    if (rt.state.long_video.project_id !== d.project_id) continue;

    const lastPreview = rt.state.long_video.last_preview;
    rt.state.long_video = d.state; rt.state.long_video.last_preview = lastPreview; rt.cached = d.ui.cached_clip_ids || []; rt.cacheChecked = true;
    rt.needsRegeneration = (rt.needsRegeneration || []).filter(id => !rt.cached.includes(id));

    rt.message = `생성 ${d.ui.cached_count} / ${d.ui.clip_count} · 승인 ${d.ui.validated_count}`;

    rt.emit(); node.__directorPlusH3Render?.();

  }

});

api.addEventListener("director-plus-long-preview", event => {

  const d = event.detail;

  for (const node of directors()) if (node.__directorLong.state.long_video.project_id === d.project_id) {

    const rt = node.__directorLong;
    rt.preview = { ...d.video, preview_revision: Date.now() }; rt.spans = d.scenes || [];
    rt.state.long_video.last_preview = { video: rt.preview, scenes: rt.spans };
    rt.emit(); node.__directorPlusH3Render?.();

  }

});

api.addEventListener("execution_start", () => {

  for (const node of directors()) { node.__directorLong.running = true; node.__directorPlusH3Render?.(); }

});

function finished() {

  for (const node of directors()) { node.__directorLong.running = false; node.__directorPlusH3Render?.(); }

}

api.addEventListener("execution_error", finished);

api.addEventListener("execution_interrupted", finished);

api.addEventListener("executing", event => { if (event.detail == null || event.detail?.node === null) finished(); });
