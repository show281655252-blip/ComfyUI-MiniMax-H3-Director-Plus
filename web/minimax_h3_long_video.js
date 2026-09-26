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
function newClip(useExternal = true) {

  return { id: crypto.randomUUID(), name: "", prompt: "", use_external_prompt: useExternal, duration: 5, seed: Math.floor(Math.random() * 1e12), seed_mode: "fixed", validated: false, loras: [] };

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
  let prefixValid = true;
  settings.clips.forEach((clip, index) => {
    const exists = prefixValid && cached[index] === clip.id;
    if (exists) reusable.push(clip.id); else missing.push(clip.id);
    clip.validated = Boolean(exists && clip.validated && approved.has(clip.id));
    prefixValid = clip.validated;
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
  .dp-h3 .dl-panel .dl-cards{display:flex;gap:12px;overflow-x:auto;overflow-y:hidden;padding:3px 3px 12px;scroll-snap-type:x proximity;scrollbar-gutter:stable}
  .dp-h3 .dl-panel .dl-card{flex:0 0 480px;width:480px;min-height:900px;border:1px solid #466071;border-radius:9px;background:#14222b;padding:9px;display:flex;flex-direction:column;gap:8px;scroll-snap-align:start;cursor:pointer}
  .dp-h3 .dl-panel .dl-card-title{font-size:15px}
  .dp-h3 .dl-panel .dl-next{color:#f7c35f;font-size:11px;font-weight:700;white-space:nowrap}
  .dp-h3 .dl-panel .dl-card-row{display:flex;align-items:center;gap:6px}
  .dp-h3 .dl-panel .dl-label{color:#9fb6c5;font-size:12px;font-weight:600}
  .dp-h3 .dl-panel .dl-linked{color:#7feeff;font-size:11px;font-weight:600;white-space:nowrap}
  .dp-h3 .dl-panel textarea.dl-card-prompt{flex:1 1 auto;min-height:420px;font-size:12px!important;line-height:1.45;cursor:text}
  .dp-h3 .dl-panel textarea.dl-card-prompt.locked{opacity:.65;cursor:default}
  .dp-h3 .dl-panel .dl-card-grid{display:grid;grid-template-columns:1fr 38px 84px;gap:6px;align-items:end}
  .dp-h3 .dl-panel .dl-field{display:flex;flex-direction:column;gap:3px;min-width:0}
  .dp-h3 .dl-panel .dl-field input{width:100%!important;padding:6px 8px!important;font-size:13px!important}
  .dp-h3 .dl-panel button.dl-dice{padding:6px 0!important;height:33px}
  .dp-h3 .dl-panel button.dl-small{padding:6px 10px!important;font-size:12px!important}
  .dp-h3 .dl-panel .dl-card .dl-toggle{padding:4px 9px!important;min-width:60px;font-size:12px!important}
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

  // Without an external prompt link, the Director's main Prompt feeds the scene that will be
  // generated next (the first unapproved one, marked NEXT) — scene 1, then scene 2 after
  // scene 1 is approved, and so on. Called from the Director's emit(): only a change of the main
  // prompt is copied (an empty NEXT scene is filled only when the workflow opens), so direct card
  // edits and freshly approved scenes are not overwritten by unrelated updates.
  rt.syncMainPrompt = text => {
    const long = rt.state?.long_video;
    const index = long?.clips?.findIndex(c => !c.validated) ?? -1;
    const target = index >= 0 ? long.clips[index] : null;
    const value = String(text || "").trim() ? String(text) : "";
    const previous = rt.lastMainPrompt;
    rt.lastMainPrompt = value;
    if (!long?.enabled || !target || !value || target.prompt === value) return;
    const changed = previous !== undefined && previous !== value;
    if (!changed && (previous !== undefined || String(target.prompt || "").trim())) return;
    target.prompt = value;
    if (long.cache_owner && rt.cached.includes(target.id)) {
      // Same as editing the card: the generated scene no longer matches its prompt.
      rt.cached = rt.cached.filter(id => long.clips.findIndex(c => c.id === id) < index);
      // Drop the now-stale approve checkboxes right away; a full re-render would steal the typing focus.
      (rt.validateEls || []).forEach((el, k) => { if (k >= index) el?.remove(); });
      request("/director_plus/extender/local_ref_invalidate", { owner_id: long.cache_owner, generation_mode: "ref2va", motion_context: true, clip_index: index, validated: false }).catch(() => {});
    }
    const box = rt.nextPromptEl;
    if (box?.isConnected && document.activeElement !== box) box.value = value;
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
  button(title, "+ 장면 추가", () => { s.clips.push(newClip(hasExternal())); rt.selected = s.clips.length - 1; });

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

  const preview = rt.preview || s.last_preview?.video;
  const spans = rt.spans || s.last_preview?.scenes || [];
  rt.selected = Math.max(0, Math.min(rt.selected, s.clips.length - 1));

  // Extender-style strip: fixed-width tall cards side by side, each with its own editor.
  const strip = element("div", null, timeline); strip.className = "dl-strip";
  const cards = element("div", null, strip); cards.className = "dl-cards";
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
      const target = cards.children[rt.scrollTo];
      rt.scrollTo = null;
      if (target) glide(target.offsetLeft - cards.offsetLeft - 4);
    } else if (restoreLeft) cards.scrollLeft = restoreLeft;
    settle();
  }, 0);

  rt.nextPromptEl = null;
  rt.validateEls = [];
  s.clips.forEach((c, i) => {
    const span = spans.find(x => x.id === c.id);
    const available = rt.cached.includes(c.id) || (!rt.cacheChecked && !!span);
    const needsRegeneration = (rt.needsRegeneration || []).includes(c.id);
    const label = c.validated ? "✓ 승인 완료" : available ? "◷ 검토 중" : needsRegeneration ? "↻ 재생성 필요" : "Ⅱ 대기";
    const locked = c.validated || rt.busy || rt.running;
    const card = element("div", null, cards); card.className = "dl-card" + (i === rt.selected ? " selected" : "");
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

    if (preview && span && available) {
      const video = element("video", null, card); video.className = "dl-preview";
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
      const empty = element("div", available ? "▶ 실행 완료 후 미리보기" : needsRegeneration ? "↻ 캐시 없음 · 재생성 필요" : "▶ 생성 대기", card);
      empty.className = "dl-preview dl-empty";
    }

    const useExternal = c.use_external_prompt ?? !String(c.prompt || "").trim();
    const promptHead = element("div", null, card); promptHead.className = "dl-card-row";
    element("span", "프롬프트", promptHead).className = "dl-label";
    if (isNextScene && !node.__directorPlusH3HasExternalPrompt?.()) {
      const linked = element("span", "↔ 아래 Prompt 연동", promptHead); linked.className = "dl-linked";
      linked.title = "외부 프롬프트가 연결되지 않은 동안, 노드 아래쪽 Prompt를 고치면 다음에 생성할 장면(NEXT)의 프롬프트에 자동으로 들어갑니다.";
    }
    element("span", null, promptHead).className = "dl-spacer";
    element("span", "외부 프롬프트", promptHead).className = "dl-label";
    const externalToggle = button(promptHead, useExternal ? "ON" : "OFF", async () => { c.use_external_prompt = !useExternal; });
    externalToggle.className = "dl-toggle"; externalToggle.setAttribute("aria-pressed", String(useExternal));
    externalToggle.disabled ||= c.validated;
    externalToggle.title = "ON: 실행할 때 Prompt Freeze의 출력을 이 장면에 저장합니다. OFF: 장면 프롬프트를 유지합니다.";

    const prompt = element("textarea", null, card); prompt.className = "dl-card-prompt"; prompt.value = c.prompt || "";
    if (isNextScene) rt.nextPromptEl = prompt;
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
    const number = (label, key, min, max) => {
      const wrap = element("label", null, numbers); wrap.className = "dl-field";
      element("span", label, wrap).className = "dl-label";
      const input = element("input", null, wrap); input.type = "number"; input.min = min; input.max = max; input.value = c[key];
      input.disabled = locked;
      input.onchange = async () => { try { await invalidate(i); c[key] = Number(input.value); save(); refresh(); } catch (e) { rt.message = e.message; refresh(); } };
    };
    number("Seed", "seed", 0, Number.MAX_SAFE_INTEGER);
    const dice = button(numbers, "🎲", async () => { await invalidate(i); c.seed = Math.floor(Math.random() * 1e12); });
    dice.className = "dl-dice"; dice.title = "새 시드"; dice.disabled ||= c.validated;
    number("길이(초)", "duration", 1, 1000);

    const foot = element("div", null, card); foot.className = "dl-card-row";
    const again = button(foot, "다시 생성", async () => { rt.selected = i; await invalidate(i); save(); await app.queuePrompt(0, 1); });
    again.className = "dl-small";
    const remove = button(foot, "삭제", async () => { if (s.clips.length < 2) return; await invalidate(i); s.clips.splice(i, 1); rt.selected = Math.min(rt.selected, s.clips.length - 1); });
    remove.className = "dl-small"; remove.disabled ||= s.clips.length < 2;
    element("span", null, foot).className = "dl-spacer";
    element("span", `${c.duration}초`, foot).className = "dl-muted";
  });

  const summary = row(timeline);
  button(summary, "▶ 생성 / 실행", async () => { save(); await app.queuePrompt(0, 1); }).className = "dl-blue";
  element("span", `설정 길이 ${s.clips.reduce((sum, c) => sum + Number(c.duration), 0)}초 · 승인 ${s.clips.filter(c => c.validated).length} / ${s.clips.length}`, summary);
  element("span", null, summary).className = "dl-spacer";
  element("small", "최종 길이는 겹치는 문맥 구간만큼 줄어듭니다.", summary).className = "dl-muted";

  const projects = row(section());

  button(projects, "프로젝트 저장 (.ext)", async () => {
    const widgets = Object.fromEntries(node.widgets.filter(w => ["width", "height", "duration", "ref_image_size", "frame_rate", "mode", "builder_state"].includes(w.name)).map(w => [w.name, w.value]));
    const result = await request("/director_plus/project/save", {state, widgets});
    const link = element("a"); link.href = api.apiURL('/director_plus/extender/project/download?' + new URLSearchParams({token: result.token}));
    link.download = "Director_Project.ext"; link.click();
  });

  const load = element("input", null, projects); load.type = "file"; load.accept = ".ext,.json"; load.style.display = "none";

  load.onchange = async () => {
    if (!load.files?.[0] || rt.busy || rt.running) return;
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
      rt.cached = checked.cached; rt.needsRegeneration = checked.missing; rt.cacheChecked = true;
      rt.preview = null; rt.spans = null;
      rt.selected = Math.max(0, incoming.clips.findIndex(c => !c.validated));
      rt.message = checked.missing.length
        ? '설정 불러오기 완료 · 재생성 필요 ' + checked.missing.length + '개 · 프롬프트와 시드는 유지했습니다.'
        : '설정 불러오기 완료 · 캐시 확인 완료';
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
  element("small", "영상은 실행 후 자동 저장 · .ext는 장면·레퍼런스·캐시 보관 · 모델/Settings는 워크플로우도 함께 저장", projects).className = "dl-muted";

  if (rt.message) { const message = element("div", rt.message, panel); message.style.color = "#ffbc80"; }

  return panel;

}

function directors() { return (app.graph?._nodes || []).filter(n => n.comfyClass === "DirectorPlusTimeline" && n.__directorLong); }

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
