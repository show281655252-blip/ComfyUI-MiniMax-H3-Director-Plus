// Prompt Studio: a full-window editor on the Director node that writes the prompt with
// ComfyUI-MinimaxH3-PromptDirector (scene settings, shot cards, writer, partial revise) and puts
// the result into the Director or a long-video scene card. Layout follows MMH3 Studio's Director
// tab. Server half: director/prompt_studio.py. State lives in node.properties.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const PROP = "directorPlusPromptStudio";
const REF_MAX = 9;
let CATALOG = null, VOCAB = null;
// Jobs belong to the node, not to the window: closing the window must not lose a running write.
// node -> { kind, label, text, t0 }. The result is written into node.properties[PROP] and, if a
// window for the node is open, shown through node.__dpPsView; otherwise kept as a notice.
const JOBS = new WeakMap();

async function runJob(node, job, request, apply) {
  if (JOBS.has(node)) throw new Error("작업이 이미 진행 중입니다.");
  JOBS.set(node, { ...job, t0: Date.now() });
  node.__dpPsView?.started(JOBS.get(node));
  let notice;
  try {
    notice = apply(node.properties[PROP], await request()) || {};
  } catch (e) {
    notice = { text: e.message, err: true };
  } finally {
    JOBS.delete(node);
  }
  notice.kind = job.kind;
  app.graph?.setDirtyCanvas(true, true);
  if (node.__dpPsView) node.__dpPsView.done(notice);
  else node.properties[PROP].notice = notice;  // shown when the window opens again
}

const SETTING_FIELDS = [
  ["style", "스타일"], ["theme", "장르 · 테마", "search"], ["lens", "렌즈"], ["depth_of_field", "심도"],
  ["lighting_key", "조명", "search"], ["dialogue_mode", "대사 정책"], ["dialogue_language", "대사 언어"],
  ["include_soundscape", "환경음"], ["include_music", "음악"], ["must_not", "금지 사항", "wide"],
  ["must_happen", "필수 사항", "wide"], ["custom_style", "직접 쓰는 스타일", "wide"],
];
const CAMERA_FIELDS = [
  ["viewpoint", "시점"], ["vp_target", "시점 주인", "person"], ["angle", "앵글"], ["angle_target", "앵글 기준", "frame"],
  ["facing", "보는 방향"], ["facing_target", "방향 기준", "frame"], ["size", "사이즈"], ["size_target", "사이즈 대상", "frame"],
  ["shot_type", "샷타입"], ["motion", "모션"], ["motion_target", "모션 대상", "frame"], ["amp", "폭"], ["speed", "속도"],
];
const BODY_FIELDS = [["body_actor", "몸 방향 — 누가", "person"], ["body_target", "몸 방향 — 어디로", "destination"],
  ["gaze_actor", "시선 — 누가", "person"], ["gaze_target", "시선 — 어디로", "destination"]];

const blankShot = () => ({ text: "", extra: "", viewpoint: "", vp_target: "", size: "", angle: "", facing: "",
  shot_type: "", motion: "", amp: "", speed: "", at: null, transition: "cut", link: "", acts: [], lines: [] });

function installStyle() {
  if (document.getElementById("dp-ps-style")) return;
  const style = document.createElement("style"); style.id = "dp-ps-style";
  style.textContent = `
  .dp-ps-back{position:fixed;inset:0;z-index:10000;background:#070b0d;display:flex;align-items:stretch;justify-content:center;padding:2.5vh 2.5vw;isolation:isolate;transform:translateZ(0)}
  .dp-ps{flex:1;max-width:1700px;background:#0f1416;border:1px solid #2b373d;border-radius:12px;display:flex;flex-direction:column;color:#d8e2e6;font:13px/1.45 system-ui,"Malgun Gothic",sans-serif;overflow:hidden}
  .dp-ps-top{display:flex;align-items:center;gap:12px;padding:12px 18px;border-bottom:1px solid #243035}
  .dp-ps-top h2{margin:0;font-size:17px;font-weight:700}
  .dp-ps-top .grow{flex:1}
  .dp-ps-body{flex:1;min-height:0;overflow:hidden;display:grid;grid-template-columns:minmax(0,1.05fr) minmax(360px,.95fr);grid-template-rows:minmax(0,1fr);gap:16px;padding:16px 18px}
  .dp-ps-body>.dp-ps-col{overflow-y:auto;overflow-x:hidden;min-height:0;padding-right:6px;overscroll-behavior:contain}
  .dp-ps-col{display:flex;flex-direction:column;gap:14px;min-width:0}
  
  .dp-ps-card{background:#151c1f;border:1px solid #273238;border-radius:10px;padding:14px 16px}
  .dp-ps-card h3{margin:0 0 10px;font-size:15px;display:flex;align-items:center;gap:8px}
  .dp-ps-card h3 .grow{flex:1}
  .dp-ps-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 14px}
  .dp-ps-grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px 10px}
  .dp-ps-field{display:flex;flex-direction:column;gap:4px;min-width:0}
  .dp-ps-field.wide{grid-column:1/-1}
  .dp-ps-field>span{font-size:11.5px;color:#93a4ad}
  .dp-ps select,.dp-ps input[type=text],.dp-ps input[type=number],.dp-ps textarea{background:#0c1113;color:#e3ecef;border:1px solid #2e3b41;border-radius:7px;padding:7px 9px;font:inherit;min-width:0;box-sizing:border-box;width:100%}
  .dp-ps textarea{resize:vertical;min-height:62px}
  .dp-ps select:disabled,.dp-ps input:disabled{opacity:.45}
  .dp-ps button{background:#1d272b;color:#dfe8eb;border:1px solid #33434a;border-radius:7px;padding:7px 12px;font:inherit;cursor:pointer}
  .dp-ps button:hover:not(:disabled){border-color:#5b7d8a}
  .dp-ps button:disabled{opacity:.45;cursor:default}
  .dp-ps button.primary{background:#b9e3cf;color:#0e1a15;border-color:#b9e3cf;font-weight:700;padding:10px}
  .dp-ps button.apply{background:#2f5874;border-color:#4b7ea1;font-weight:700;padding:10px}
  .dp-ps button.small{padding:3px 9px;font-size:12px}
  .dp-ps details{border-top:1px solid #222d32;padding-top:6px;margin-top:8px}
  .dp-ps summary{cursor:pointer;color:#a9bac2;font-size:12.5px;padding:3px 0}
  .dp-ps .muted{color:#7f9099;font-size:12px}
  .dp-ps .shot{border:1px solid #2a363c;border-left:3px solid #5d8f7a;border-radius:9px;padding:12px;background:#11181b;display:flex;flex-direction:column;gap:8px}
  .dp-ps .shot-head{display:flex;align-items:center;gap:8px}
  .dp-ps .shot-head b{color:#b9e3cf}
  .dp-ps .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .dp-ps .row>*{flex:1;min-width:0}
  .dp-ps .list-row{display:grid;gap:6px;align-items:center;margin-top:6px}
  .dp-ps .refs{display:flex;flex-wrap:wrap;gap:10px}
  .dp-ps .ref{display:flex;gap:8px;align-items:center;background:#0f1517;border:1px solid #273238;border-radius:8px;padding:6px;width:260px}
  .dp-ps .ref img{width:46px;height:46px;object-fit:cover;border-radius:5px;background:#000}
  .dp-ps .result{min-height:300px;font-family:Consolas,monospace;font-size:12px}
  .dp-ps .report{white-space:pre-wrap;font-family:Consolas,monospace;font-size:11.5px;color:#a7b6bd;max-height:260px;overflow:auto;background:#0c1113;border-radius:7px;padding:8px}
  .dp-ps .status{font-size:12.5px;color:#b9e3cf;min-height:18px}
  .dp-ps .status.err{color:#ff8e8e}
  .dp-ps .chk{display:flex;align-items:center;gap:6px;height:34px}
  @media (max-width:1150px){.dp-ps-body{grid-template-columns:1fr;grid-template-rows:none;overflow:auto}.dp-ps-body>.dp-ps-col{overflow:visible;padding-right:0}.dp-ps-grid4{grid-template-columns:repeat(2,minmax(0,1fr))}}
  `;
  document.head.append(style);
}

function h(tag, props = {}, children = []) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style") el.style.cssText = v;
    else if (v !== undefined && v !== null && v !== false) el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of [].concat(children)) if (c !== null && c !== undefined && c !== false) el.append(c);
  return el;
}

async function getJSON(path, body) {
  const response = await api.fetchApi(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  let data = {};
  try { data = await response.json(); } catch { /* ignore */ }
  if (!response.ok || data.ok === false) throw new Error(data.error || `${response.status} ${response.statusText}`);
  return data;
}

function viewUrl(value) {
  const text = String(value || ""), cut = text.lastIndexOf("/");
  const params = new URLSearchParams({ filename: cut >= 0 ? text.slice(cut + 1) : text, subfolder: cut >= 0 ? text.slice(0, cut) : "", type: "input" });
  return api.apiURL(`/view?${params}`);
}

const rows = field => (VOCAB && VOCAB[field]) || [];

function unavailable(shot, key) {
  if (key === "vp_target" && (!shot.viewpoint || shot.viewpoint === "objective")) return "시점 주인이 필요한 시점을 먼저 고르세요.";
  if (shot.viewpoint === "pov" && key === "shot_type") return "POV에서는 관계형 샷타입을 쓰지 않습니다.";
  if (shot.viewpoint === "pov" && key === "size" && !shot.size_target) return "POV 사이즈는 사이즈 대상을 먼저 지정하세요.";
  if (key === "motion_target" && (!shot.motion || shot.motion === "static")) return "이동 모션에서만 씁니다.";
  if (shot.motion === "static" && (key === "amp" || key === "speed")) return "고정 카메라에는 폭·속도를 쓰지 않습니다.";
  return "";
}

function targetChoices(kind, pictures) {
  const out = [["", kind === "person" ? "— 대상 없음" : "지정 안 함"]];
  if (kind === "frame") out.push(["scene", "장면 전체"]);
  if (kind === "destination") out.push(["camera", "카메라 쪽"], ["away_camera", "카메라 반대쪽"]);
  for (let i = 1; i <= Math.max(1, Math.min(REF_MAX, pictures)); i++) out.push([`pic:${i}`, `이미지 ${i}의 인물`]);
  out.push(["man", "이 샷의 남자"], ["woman", "이 샷의 여자"], ["third", "지켜보는 제3자"], ["__custom__", "인물·대상 직접 입력…"]);
  return out;
}

// First open: start from the Shot Settings / Shot Builder / Writer nodes already in the workflow,
// so moving from the node chain to this window keeps the style, roles, shots and model.
function importFromGraph() {
  const nodes = app.graph?._nodes || [];
  const values = type => {
    const found = nodes.find(n => n.type === type);
    return found ? Object.fromEntries((found.widgets || []).map(w => [w.name, w.value])) : null;
  };
  const out = { settings: {}, writer: {}, roles: {} };
  const settings = values("MMH3_ShotSettings");
  if (settings) out.settings = settings;
  const builder = values("MMH3_ShotBuilder");
  try {
    const shots = JSON.parse(builder?.shots_data || "null");
    if (Array.isArray(shots?.shots) && shots.shots.length) out.shots = shots.shots.map(s => ({ ...blankShot(), ...s }));
    for (const r of shots?.refs || []) if (r?.n && r.role) out.roles[r.n] = r.role;
  } catch { /* keep defaults */ }
  const writer = values("MMH3_OllamaPromptWriter");
  // Every writer setting the window uses (director/prompt_studio.py WRITER_KEYS), not a subset —
  // max_tokens / max_ref_images were left at the pack defaults before.
  if (writer) for (const key of ["model", "vision_model", "temperature", "llm_seed", "num_ctx", "max_tokens", "max_words", "vision_pass",
    "image_max_side", "max_ref_images", "auto_fix", "force_english", "ollama_url"]) if (writer[key] !== undefined) out.writer[key] = writer[key];
  if (writer) out.writerImported = true;
  return out;
}

export const DirectorPlusPromptStudio = {
  async open(node, options = {}) {
    installStyle();
    document.querySelector(".dp-ps-back")?.remove();
    const target = node.__directorPlusPromptTarget;
    if (!target) return;
    node.properties = node.properties || {};
    if (!node.properties[PROP]) node.properties[PROP] = importFromGraph();
    // Fill defaults into the stored object itself, so every window (and a job finishing after its
    // window closed) works on the same object.
    const data = node.properties[PROP];
    for (const [k, v] of Object.entries({ settings: {}, shots: [blankShot()], roles: {}, writer: {}, prompt: "", previous: "", brief: "", report: "", revise: "" })) if (data[k] === undefined) data[k] = v;
    if (!Array.isArray(data.shots) || !data.shots.length) data.shots = [blankShot()];
    const save = () => { node.properties[PROP] = data; app.graph?.setDirtyCanvas(true, true); };
    let view = null;

    // Long video: every scene keeps its own scene settings (style, lens, lighting, dialogue, sound,
    // must / must-not ...), picture roles, shot cards, result, report, brief, revise text and chat log in
    // data.scenes[clip id]. Only the writer / chat LLM settings stay shared. A single video keeps using
    // the top-level fields as before.
    const st = node.__directorPlusH3State?.() || {};
    const long = st.long_video?.enabled ? st.long_video : null;
    const sceneKey = i => long?.clips?.[i]?.id || `scene-${i}`;
    const nextScene = long ? long.clips.findIndex(c => !c.validated) : -1;
    let current = long ? (Number.isInteger(options.scene) && long.clips[options.scene] ? options.scene : Math.max(0, nextScene)) : -1;
    const blankSlot = () => ({ shots: [blankShot()], prompt: "", previous: "", brief: "", briefReport: "", report: "", revise: "",
      chat: { messages: [] } });
    const fillSlot = s => {
      for (const [k, v] of Object.entries(blankSlot())) if (s[k] === undefined) s[k] = v;
      // A scene saved before settings / roles became per scene starts from the shared ones; its own
      // must / must-not (kept per scene since the first version) move into its settings.
      if (!s.settings || typeof s.settings !== "object") {
        s.settings = { ...(data.settings || {}) };
        for (const k of ["must_happen", "must_not"]) if (s[k] !== undefined) s.settings[k] = s[k];
      }
      delete s.must_happen; delete s.must_not;
      if (!s.roles || typeof s.roles !== "object") s.roles = { ...(data.roles || {}) };
      if (!Array.isArray(s.shots) || !s.shots.length) s.shots = [blankShot()];
      if (!Array.isArray(s.chat?.messages)) s.chat = { messages: [] };
      return s;
    };
    // A scene opened for the first time takes the settings and roles of the scene before it (same style
    // and picture use carries on); its shot cards start empty ("앞 장면에서 복사" copies those).
    const newSlot = (d, key) => {
      const i = long.clips.findIndex((_, j) => sceneKey(j) === key);
      const prev = i > 0 ? d.scenes[sceneKey(i - 1)] : null;
      return { ...blankSlot(), settings: { ...(prev?.settings || d.settings || {}) }, roles: { ...(prev?.roles || d.roles || {}) } };
    };
    if (long) {
      if (!data.scenes) {  // first open since scenes got their own state: the one old state belongs to this scene
        data.scenes = { [sceneKey(current)]: { shots: data.shots, prompt: data.prompt, previous: data.previous, brief: data.brief,
          briefReport: data.briefReport, report: data.report, revise: data.revise, settings: { ...(data.settings || {}) },
          roles: { ...(data.roles || {}) }, chat: { messages: data.chat?.messages || [] } } };
      }
      const ids = new Set(long.clips.map((_, i) => sceneKey(i)));
      for (const k of Object.keys(data.scenes)) if (!ids.has(k)) delete data.scenes[k];  // scenes deleted from the timeline
    }
    // A scene's state inside a given state object: a job that finishes later writes into the scene it
    // was started for, even if the window now shows another scene (or is closed).
    const slotIn = (d, key) => {
      if (!long) return d;
      d.scenes ||= {};
      return fillSlot(d.scenes[key] ||= newSlot(d, key));
    };
    const slot = () => slotIn(data, sceneKey(current));
    const settingsOf = () => long ? slot().settings : data.settings;
    const rolesOf = () => long ? slot().roles : data.roles;
    const sceneRefresh = [];  // redraws of the per-scene parts, run when another scene is picked

    const back = h("div", { class: "dp-ps-back" });
    const box = h("div", { class: "dp-ps" });
    back.append(box); document.body.append(back);
    let chatUsed = false, timer = null;
    // The ComfyUI canvas keeps redrawing under this window; on some GPUs that tears the window's
    // raster tiles (a vertical seam that goes away on focus change). Pause it while we are open.
    const canvas = app.canvas, wasPaused = canvas ? !!canvas.pause_rendering : false;
    try { if (canvas) canvas.pause_rendering = true; } catch { /* ignore */ }
    const close = () => {
      try { if (canvas) canvas.pause_rendering = wasPaused; app.graph?.setDirtyCanvas(true, true); } catch { /* ignore */ }
      if (node.__dpPsView === view) delete node.__dpPsView;
      clearInterval(timer);
      save(); back.remove(); document.removeEventListener("keydown", onKey, true);
      if (chatUsed) getJSON("/director_plus/prompt_studio/chat_unload", { model: data.chat?.llm?.model, ollama_url: data.writer?.ollama_url || "" }).catch(() => {});  // free the card for video generation
    };
    const onKey = e => { if (e.key === "Escape" && document.activeElement?.tagName !== "SELECT") { e.stopPropagation(); close(); } };
    document.addEventListener("keydown", onKey, true);
    for (const name of ["pointerdown", "mousedown", "wheel", "keydown", "keyup"]) box.addEventListener(name, e => e.stopPropagation());

    box.append(h("div", { class: "dp-ps-top" }, [h("h2", { text: "✍ 프롬프트 작성" }), h("span", { class: "muted", text: "PromptDirector · Director의 레퍼런스·모드·길이를 그대로 씁니다" }), h("span", { class: "grow" }), h("button", { text: "닫기 ✕", onclick: close })]));
    const body = h("div", { class: "dp-ps-body" }); box.append(body);
    const loading = h("div", { class: "muted", text: "불러오는 중…" }); body.append(loading);
    try {
      if (!CATALOG) CATALOG = await getJSON("/director_plus/prompt_studio/catalog");
      if (CATALOG.available && !VOCAB) VOCAB = await getJSON("/mmh3/shotcards/vocab");
    } catch (e) { loading.textContent = "불러오지 못했습니다: " + e.message; return; }
    if (!CATALOG.available) { loading.innerHTML = ""; loading.append(`PromptDirector가 설치돼 있지 않습니다. `, h("a", { href: CATALOG.pack_url, target: "_blank", text: CATALOG.pack_url })); return; }
    loading.remove();

    const allSettings = () => [data.settings, ...(long ? Object.keys(data.scenes || {}).map(k => slotIn(data, k).settings) : [])];
    for (const s of allSettings()) for (const [key, spec] of Object.entries(CATALOG.settings)) if (s[key] === undefined) s[key] = spec.default;
    // Saved with the pack's old 1200, which cut video-analysed prompts before the sound sections.
    // (Only for states saved before max_tokens was imported; a value taken from the Writer node is kept.)
    if (!data.writerImported && Number(data.writer.max_tokens) === 1200 && CATALOG.writer.max_tokens) data.writer.max_tokens = CATALOG.writer.max_tokens.default;
    for (const [key, spec] of Object.entries(CATALOG.writer)) if (data.writer[key] === undefined) data.writer[key] = spec.default;
    if (!data.writer.model || (CATALOG.writer.model?.options && !CATALOG.writer.model.options.includes(data.writer.model))) data.writer.model = CATALOG.writer.model?.options?.[0] || "";

    const left = h("div", { class: "dp-ps-col" }), right = h("div", { class: "dp-ps-col dp-ps-right" });
    body.append(left, right);
    const pictures = () => target.pictures();

    // ---------------- scene settings
    const settingsTitle = h("h3", { text: "장면 설정" });
    const settingsCard = h("div", { class: "dp-ps-card" }, [settingsTitle]);
    const settingsTitleRefresh = () => { settingsTitle.textContent = long ? `장면 설정 · 장면 ${current + 1}` : "장면 설정"; };
    sceneRefresh.push(settingsTitleRefresh);
    settingsTitleRefresh();
    const grid = h("div", { class: "dp-ps-grid" }); settingsCard.append(grid);
    // A sound reference (V+A video or audio on the timeline) already decides the sound; the two
    // checkboxes would only add the style preset's own ambience/score. Turn them off when such a
    // reference appears (and back on when it goes away, if we were the ones who turned them off).
    // The user can still tick them again; that sticks until the sound references change.
    const soundSig = (() => {
      try {
        const items = JSON.parse(node.widgets?.find(w => w.name === "timeline_data")?.value || "{}").items || [];
        return items.filter(it => it.enabled !== false && (it.type === "audio" || (it.type === "video" && it.media_mode === "video_audio"))).map(it => it.value).sort().join("|");
      } catch { return ""; }
    })();
    let soundNote = "";
    // The sound references are the Director's, shared by all scenes, so this applies to every scene.
    if (soundSig && soundSig !== data.soundRefSig) {
      for (const s of allSettings()) { s.include_soundscape = false; s.include_music = false; }
      data.soundAutoOff = true;
      soundNote = "레퍼런스에 소리가 있어 환경음·음악을 껐습니다 (소리는 레퍼런스를 그대로 따릅니다).";
    } else if (!soundSig && data.soundRefSig && data.soundAutoOff) {
      for (const s of allSettings()) { s.include_soundscape = true; s.include_music = true; }
      data.soundAutoOff = false;
      soundNote = "소리 레퍼런스가 없어져 환경음·음악을 다시 켰습니다.";
    }
    data.soundRefSig = soundSig;
    let soundCell = null;
    for (const [key, label, extra] of SETTING_FIELDS) {
      const spec = CATALOG.settings[key]; if (!spec) continue;
      if (spec.kind === "boolean" && (key === "include_soundscape" || key === "include_music")) {  // both in one cell, on a row of their own
        if (!soundCell) {
          soundCell = h("div", { class: "dp-ps-field", style: "grid-column:1;flex-direction:row;gap:22px;align-items:flex-start;flex-wrap:wrap" });
          grid.append(soundCell);
          if (soundNote) grid.append(h("div", { class: "muted", style: "grid-column:2;align-self:center", text: soundNote }));
        }
        const box2 = h("input", { type: "checkbox", title: spec.tooltip || "" }); box2.checked = !!settingsOf()[key];
        box2.onchange = () => { settingsOf()[key] = box2.checked; save(); };
        sceneRefresh.push(() => { box2.checked = !!settingsOf()[key]; });
        soundCell.append(h("label", { class: "dp-ps-field", style: "align-items:center;gap:6px;cursor:pointer", title: spec.tooltip || "" }, [h("span", { text: label }), box2]));
        continue;
      }
      const field = h("label", { class: "dp-ps-field" + (extra === "wide" ? " wide" : "") }, [h("span", { text: label })]);
      if (spec.kind === "combo") {
        const sel = h("select", { title: spec.tooltip || "" });
        let search = null;
        const fill = filter => { sel.innerHTML = ""; const v = settingsOf()[key]; for (const o of spec.options) if (!filter || String(o).toLowerCase().includes(filter) || o === v) sel.append(h("option", { value: o, text: o })); sel.value = v; };
        fill("");
        sel.onchange = () => { settingsOf()[key] = sel.value; save(); };
        if (extra === "search") { search = h("input", { type: "text", placeholder: "검색…", oninput: e => fill(e.target.value.trim().toLowerCase()) }); field.append(search); }
        sceneRefresh.push(() => { if (search) search.value = ""; fill(""); });
        field.append(sel);
      } else if (spec.kind === "boolean") {
        const box2 = h("input", { type: "checkbox" }); box2.checked = !!settingsOf()[key];
        box2.onchange = () => { settingsOf()[key] = box2.checked; save(); };
        sceneRefresh.push(() => { box2.checked = !!settingsOf()[key]; });
        field.append(h("div", { class: "chk" }, [box2]));
      } else {
        const area = h("textarea", { title: spec.tooltip || "" }); area.value = settingsOf()[key] ?? "";
        area.oninput = () => { settingsOf()[key] = area.value; save(); };
        sceneRefresh.push(() => { area.value = settingsOf()[key] ?? ""; });
        field.append(area);
      }
      grid.append(field);
    }
    left.append(settingsCard);

    // ---------------- reference roles (Director pictures)
    const refsTitle = h("h3", { text: "레퍼런스 역할" });
    const refsCard = h("div", { class: "dp-ps-card" }, [refsTitle]);
    const pics = pictures();
    if (!pics.length) refsCard.append(h("div", { class: "muted", text: "Director 타임라인에 이미지 레퍼런스가 없습니다. 영상 레퍼런스는 작성할 때 자동으로 분석합니다." }));
    const refsBox = h("div", { class: "refs" }); refsCard.append(refsBox);
    const roleSelects = [];
    pics.slice(0, REF_MAX).forEach((item, i) => {
      const n = i + 1, sel = h("select", { title: "이 이미지를 무엇에 쓸지 정합니다" + (long ? " (이 장면만)" : "") });
      for (const r of rows("ref_role")) sel.append(h("option", { value: r.key, text: r.ko, title: r.tip || "" }));
      sel.value = rolesOf()[n] || "";
      sel.onchange = () => { rolesOf()[n] = sel.value; save(); };
      roleSelects.push([n, sel]);
      refsBox.append(h("div", { class: "ref" }, [h("img", { src: viewUrl(item.value), alt: "" }), h("div", { class: "dp-ps-field", style: "flex:1" }, [h("span", { text: `이미지 ${n} · <Picture ${n}>` }), sel])]));
    });
    const refsRefresh = () => {
      refsTitle.textContent = long ? `레퍼런스 역할 · 장면 ${current + 1}` : "레퍼런스 역할";
      for (const [n, sel] of roleSelects) sel.value = rolesOf()[n] || "";
    };
    sceneRefresh.push(refsRefresh);
    refsRefresh();
    left.append(refsCard);

    // ---------------- shot cards
    const shotsCard = h("div", { class: "dp-ps-card" });
    const shotsBox = h("div", { class: "dp-ps-col" });
    const renderShots = () => {
      shotsBox.innerHTML = "";
      slot().shots.forEach((shot, i) => shotsBox.append(shotCard(shot, i)));
    };
    sceneRefresh.push(() => renderShots());
    const vocabSelect = (field, value, onchange, disabled, tip) => {
      const sel = h("select", { title: tip || "" });
      for (const r of rows(field)) sel.append(h("option", { value: r.key, text: r.ko, title: r.tip || "" }));
      sel.value = value || ""; sel.disabled = !!disabled; sel.onchange = () => onchange(sel.value);
      return sel;
    };
    const targetSelect = (kind, value, onchange, disabled, tip) => {
      const sel = h("select", { title: tip || "" });
      const choices = targetChoices(kind, pictures().length);
      if (String(value || "").startsWith("named:")) choices.splice(choices.length - 1, 0, [value, value.slice(6)]);
      for (const [v, label] of choices) sel.append(h("option", { value: v, text: label }));
      sel.value = value || ""; sel.disabled = !!disabled;
      sel.onchange = () => {
        if (sel.value === "__custom__") {
          const name = window.prompt("인물이나 대상을 이름으로 적으세요 (예: 빨간 우산을 든 여자)", String(value || "").replace(/^named:/, ""));
          if (name && name.trim()) onchange("named:" + name.trim()); else sel.value = value || "";
          renderShots(); return;
        }
        onchange(sel.value);
      };
      return sel;
    };
    const shotCard = (shot, i) => {
      const set = (key, v, rerender) => { shot[key] = v; save(); if (rerender) renderShots(); };
      const card = h("div", { class: "shot" });
      card.append(h("div", { class: "shot-head" }, [h("b", { text: `SHOT ${String(i + 1).padStart(2, "0")}` }), h("span", { class: "grow", style: "flex:1" }),
        h("button", { class: "small", text: "삭제", disabled: slot().shots.length < 2, onclick: () => { slot().shots.splice(i, 1); save(); renderShots(); } })]));
      if (i > 0) {
        const at = h("input", { type: "number", step: "0.1", min: "0", placeholder: "자동" }); at.value = shot.at ?? "";
        at.onchange = () => set("at", at.value === "" ? null : Number(at.value));
        card.append(h("div", { class: "dp-ps-grid" }, [
          h("label", { class: "dp-ps-field" }, [h("span", { text: "시작 시각 (초)" }), at]),
          h("label", { class: "dp-ps-field" }, [h("span", { text: "샷 전환" }), vocabSelect("transition", shot.transition || "cut", v => set("transition", v))]),
          h("label", { class: "dp-ps-field wide" }, [h("span", { text: "앞 샷과의 관계" }), vocabSelect("shot_link", shot.link || "", v => set("link", v, true))]),
        ]));
      }
      const text = h("textarea", { placeholder: shot.link === "same_moment" ? "같은 순간 — 앞 샷의 내용을 이어받습니다" : "장소·인물·표정·행동을 자유롭게 (한국어 가능)" });
      text.value = shot.text || ""; text.disabled = shot.link === "same_moment"; text.oninput = () => set("text", text.value);
      const extra = h("textarea", { placeholder: "행위 위에 겹치는 추가 동작 (선택)", style: "min-height:44px" });
      extra.value = shot.extra || ""; extra.oninput = () => set("extra", extra.value);
      card.append(h("label", { class: "dp-ps-field" }, [h("span", { text: "내용" }), text]), h("label", { class: "dp-ps-field" }, [h("span", { text: "추가 동작" }), extra]));

      const cam = h("div", { class: "dp-ps-grid4" });
      for (const [key, label, kind] of CAMERA_FIELDS) {
        const reason = unavailable(shot, key);
        const input = kind ? targetSelect(kind, shot[key], v => set(key, v, true), reason, reason) : vocabSelect(key, shot[key], v => {
          shot[key] = v;
          if (key === "motion" && v === "static") { shot.amp = ""; shot.speed = ""; }
          if (key === "viewpoint" && v === "pov") { if (!shot.size_target) shot.size = ""; shot.shot_type = ""; }
          if (key === "viewpoint" && (!v || v === "objective")) shot.vp_target = "";
          save(); renderShots();
        }, reason, reason);
        cam.append(h("label", { class: "dp-ps-field" }, [h("span", { text: label }), input]));
      }
      const camOpen = CAMERA_FIELDS.some(([k]) => shot[k]);
      card.append(h("details", { open: camOpen }, [h("summary", { text: "카메라 · 샷 전환" }), cam]));

      const bodyGrid = h("div", { class: "dp-ps-grid" });
      for (const [key, label, kind] of BODY_FIELDS) bodyGrid.append(h("label", { class: "dp-ps-field" }, [h("span", { text: label }), targetSelect(kind, shot[key], v => set(key, v, true))]));
      card.append(h("details", { open: BODY_FIELDS.some(([k]) => shot[k]) }, [h("summary", { text: "몸 방향 · 시선" }), bodyGrid]));

      shot.acts = Array.isArray(shot.acts) ? shot.acts : [];
      const acts = h("div");
      shot.acts.forEach((a, k) => {
        const at = h("input", { type: "number", step: "0.1", min: "0", placeholder: "시각" }); at.value = a.at ?? "";
        at.onchange = () => { a.at = at.value === "" ? null : Number(at.value); save(); };
        acts.append(h("div", { class: "list-row", style: "grid-template-columns:2fr 1.2fr 1fr 1.2fr 1fr 1fr .8fr auto" }, [
          vocabSelect("act", a.act, v => { a.act = v; save(); }),
          targetSelect("person", a.a, v => { a.a = v; save(); renderShots(); }), vocabSelect("act_pos", a.a_pos, v => { a.a_pos = v; save(); }),
          targetSelect("person", a.b, v => { a.b = v; save(); renderShots(); }), vocabSelect("act_pos", a.b_pos, v => { a.b_pos = v; save(); }),
          vocabSelect("mover", a.mover, v => { a.mover = v; save(); }), at,
          h("button", { class: "small", text: "✕", onclick: () => { shot.acts.splice(k, 1); save(); renderShots(); } })]));
      });
      acts.append(h("div", { class: "muted", style: "margin-top:4px", text: shot.acts.length ? "행위 · 칸1 · 위치 · 칸2 · 위치 · 무버 · 시각(초)" : "" }));
      acts.append(h("button", { class: "small", style: "margin-top:6px", text: "＋ 행위 추가", onclick: () => { shot.acts.push({ at: null, act: "", a: "", a_pos: "", b: "", b_pos: "", mover: "" }); save(); renderShots(); } }));
      card.append(h("details", { open: shot.acts.length > 0 }, [h("summary", { text: "행위 라이브러리" }), acts]));

      shot.lines = Array.isArray(shot.lines) ? shot.lines : [];
      const lines = h("div");
      shot.lines.forEach((ln, k) => {
        const txt = h("input", { type: "text", placeholder: "대사 (그대로 옮겨 씁니다)" }); txt.value = ln.text || "";
        txt.oninput = () => { ln.text = txt.value; save(); };
        const at = h("input", { type: "number", step: "0.1", min: "0", placeholder: "시각" }); at.value = ln.at ?? "";
        at.onchange = () => { ln.at = at.value === "" ? null : Number(at.value); save(); };
        lines.append(h("div", { class: "list-row", style: "grid-template-columns:1.2fr 3fr .8fr auto" }, [
          targetSelect("person", ln.who, v => { ln.who = v; save(); renderShots(); }), txt, at,
          h("button", { class: "small", text: "✕", onclick: () => { shot.lines.splice(k, 1); save(); renderShots(); } })]));
      });
      lines.append(h("button", { class: "small", style: "margin-top:6px", text: "＋ 대사 추가", onclick: () => { shot.lines.push({ who: "", text: "", at: null }); save(); renderShots(); } }));
      card.append(h("details", { open: shot.lines.length > 0 }, [h("summary", { text: `대사 (${shot.lines.filter(l => (l.text || "").trim()).length})` }), lines]));
      return card;
    };
    const shotsTitle = h("span", { text: "샷 구성" });
    // Start a new scene from the one before it (its shot cards and must / must-not), then edit.
    const copyPrev = h("button", { class: "small", text: "앞 장면에서 복사", title: "앞 장면의 장면 설정, 레퍼런스 역할, 샷 카드(대사 포함)를 이 장면으로 복사합니다." });
    copyPrev.onclick = () => {
      if (!long || current < 1) return;
      const prev = slotIn(data, sceneKey(current - 1)), here = slot();
      const filled = here.shots.some(s => (s.text || "").trim() || (s.lines || []).some(l => (l.text || "").trim()) || (s.acts || []).some(a => a.act));
      if (filled && !window.confirm(`장면 ${current + 1}의 장면 설정·레퍼런스 역할·샷 카드를 장면 ${current}의 내용으로 바꿀까요?`)) return;
      here.shots = JSON.parse(JSON.stringify(prev.shots));
      here.settings = { ...prev.settings };
      here.roles = { ...prev.roles };
      save(); sceneRefresh.forEach(f => f()); say(`장면 ${current}의 장면 설정, 레퍼런스 역할, 샷 카드를 복사했습니다.`);
    };
    const shotsHeadRefresh = () => {
      shotsTitle.textContent = long ? `샷 구성 · 장면 ${current + 1}` : "샷 구성";
      copyPrev.style.display = long && current > 0 ? "" : "none";
    };
    sceneRefresh.push(shotsHeadRefresh);
    shotsHeadRefresh();
    shotsCard.append(h("h3", {}, [shotsTitle, h("span", { class: "grow" }), copyPrev,
      h("button", { text: "＋ 샷 추가", onclick: () => { slot().shots.push(blankShot()); save(); renderShots(); } })]), shotsBox);
    renderShots();
    left.append(shotsCard);

    // ---------------- prompt panel
    const panel = h("div", { class: "dp-ps-card" });
    const status = h("div", { class: "status" });
    const say = (text, err) => { status.textContent = text || ""; status.classList.toggle("err", !!err); };

    const targetSel = h("select");
    if (long) {
      // Approved scenes can be opened too (to read or rework their writing); 적용 stays refused for them.
      long.clips.forEach((c, i) => targetSel.append(h("option", { value: String(i), text: `장면 ${i + 1} · ${c.duration}초${i === nextScene ? " · NEXT" : ""}${c.validated ? " · 승인됨(적용 불가)" : ""}` })));
      targetSel.value = String(current);
      targetSel.onchange = () => {
        current = Number(targetSel.value); save();
        sceneRefresh.forEach(f => f());
        say(long.clips[current]?.validated ? `장면 ${current + 1}은 승인돼 있어 결과를 적용하려면 먼저 승인을 해제해야 합니다.` : "");
      };
    } else targetSel.append(h("option", { value: "director", text: "Director 프롬프트" }));
    const sceneIndex = () => long ? current : -1;
    const duration = () => long ? Number(long.clips[sceneIndex()]?.duration) || 5 : (target.duration() || 5);

    const modelSel = h("select");
    for (const o of CATALOG.writer.model?.options || []) modelSel.append(h("option", { value: o, text: o }));
    modelSel.value = data.writer.model; modelSel.onchange = () => { data.writer.model = modelSel.value; save(); };
    const adv = h("div", { class: "dp-ps-grid" });
    const advField = (key, label) => {
      const spec = CATALOG.writer[key]; if (!spec) return;
      let input;
      if (spec.kind === "combo") { input = h("select"); for (const o of spec.options) input.append(h("option", { value: o, text: o })); input.value = data.writer[key]; input.onchange = () => { data.writer[key] = input.value; save(); }; }
      else if (spec.kind === "boolean") { input = h("input", { type: "checkbox" }); input.checked = !!data.writer[key]; input.onchange = () => { data.writer[key] = input.checked; save(); }; input = h("div", { class: "chk" }, [input]); }
      else { input = h("input", { type: "number", step: spec.kind === "float" ? "0.05" : "1", min: spec.min ?? "", max: spec.max ?? "" }); input.value = data.writer[key]; input.onchange = () => { data.writer[key] = Number(input.value); save(); }; }
      adv.append(h("label", { class: "dp-ps-field", title: spec.tooltip || "" }, [h("span", { text: label }), input]));
    };
    advField("vision_model", "비전 모델"); advField("temperature", "temperature"); advField("num_ctx", "num_ctx"); advField("max_tokens", "최대 응답 토큰");
    advField("max_words", "최대 단어 수"); advField("llm_seed", "seed (0 = 매번 새로)"); advField("vision_pass", "이미지 판독 (vision pass)");

    const result = h("textarea", { class: "result", placeholder: "완성된 프롬프트를 붙여 넣거나 「프롬프트 작성」으로 만드세요." });
    result.value = slot().prompt || ""; result.oninput = () => { slot().prompt = result.value; save(); };
    const reportBox = h("div", { class: "report" });
    const reportDetails = h("details", {}, [h("summary", { text: "브리프 · 검사 결과" }), reportBox]);
    const reviseBox = h("textarea", { placeholder: "고칠 부분만 적으세요. 예: 끝부분을 계속 빗자루로 쓸고 있게 바꿔줘." });
    reviseBox.value = slot().revise || ""; reviseBox.oninput = () => { slot().revise = reviseBox.value; save(); };

    let busy = false;
    const buttons = [];
    const lock = (on, label, t0 = Date.now()) => {
      busy = on; buttons.forEach(b => { b.disabled = on || b.dataset.off === "1"; });
      clearInterval(timer);
      if (on) { const tick = () => say(`${label}… ${Math.round((Date.now() - t0) / 1000)}초`); tick(); timer = setInterval(tick, 1000); }
    };
    const payload = () => {
      const tw = node.widgets?.find(w => w.name === "timeline_data"), bw = node.widgets?.find(w => w.name === "builder_state");
      const shots = slot().shots.map(s => ({ ...s, acts: (s.acts || []).filter(a => a.act), lines: (s.lines || []).filter(l => (l.text || "").trim()) }));
      const refs = pictures().slice(0, REF_MAX).map((_, i) => ({ n: i + 1, role: rolesOf()[i + 1] || "" }));
      const settings = { ...settingsOf() };
      return { director: { id: node.id, mode: target.mode(), duration: duration(), timeline_data: tw?.value || "{}", builder_state: bw?.value || "{}" },
        shots: { version: 1, shots, refs }, settings, writer: { ...data.writer, model: modelSel.value } };
    };
    const showReport = () => { const s = slot(); reportBox.textContent = [s.brief && "[브리프]\n" + s.brief, s.briefReport && "[샷 구성 점검]\n" + s.briefReport, s.report && "[작성 보고서]\n" + s.report].filter(Boolean).join("\n\n") || "아직 없습니다."; };
    showReport();
    sceneRefresh.push(() => { result.value = slot().prompt || ""; reviseBox.value = slot().revise || ""; showReport(); });
    // A job remembers its scene; its notice says so when the window now shows another scene.
    const jobScene = () => ({ key: sceneKey(current), label: long ? `장면 ${current + 1}` : "" });
    const sceneNote = (scene, text) => long && scene.key !== sceneKey(current) ? `${scene.label}: ${text} (그 장면을 고르면 보입니다)` : text;
    const act = (label, cls, fn) => { const b = h("button", { text: label, class: cls || "" }); b.onclick = async () => { if (busy || JOBS.has(node)) return; try { await fn(); } catch (e) { say(e.message, true); } }; buttons.push(b); return b; };
    const truncatedText = r => `작성 완료 (${r.seconds}초) — 단, 응답이 최대 응답 토큰(${r.max_tokens})에서 잘린 것 같습니다. 끝부분과 빈 칸이 N/A로 채워졌을 수 있으니 「LLM 고급 설정」에서 최대 응답 토큰을 올리고 다시 작성하세요.`;

    const briefBtn = act("브리프 확인", "", async () => {
      const body = payload(), scene = jobScene();
      await runJob(node, { kind: "brief", label: "브리프 만드는 중" }, () => getJSON("/director_plus/prompt_studio/brief", body), (d, r) => {
        const s = slotIn(d, scene.key);
        s.brief = r.brief; s.briefReport = r.report;
        return { text: sceneNote(scene, "브리프를 만들었습니다. 아래 「브리프 · 검사 결과」에서 확인하세요."), openReport: true };
      });
    });
    const writeBtn = act("프롬프트 작성", "primary", async () => {
      if (!modelSel.value) throw new Error("Ollama 모델을 고르세요.");
      const body = payload(), scene = jobScene();
      await runJob(node, { kind: "write", label: `작성 중${scene.label ? ` · ${scene.label}` : ""} (영상 레퍼런스가 있으면 분석 포함, 1~2분)` }, () => getJSON("/director_plus/prompt_studio/write", body), (d, r) => {
        const s = slotIn(d, scene.key);
        if (s.prompt && s.prompt !== r.prompt) s.previous = s.prompt;
        s.prompt = r.prompt; s.brief = r.brief; s.briefReport = r.brief_report; s.report = r.report;
        return r.truncated ? { text: sceneNote(scene, truncatedText(r)), err: true, openReport: true } : { text: sceneNote(scene, `작성 완료 (${r.seconds}초). 확인한 뒤 「적용」을 누르세요.`) };
      });
    });
    const applyNow = async () => {
      const text = result.value.trim();
      if (!text) throw new Error("적용할 프롬프트가 없습니다.");
      if (long) {
        if (!node.__directorLong?.setScenePrompt) throw new Error("장면 타임라인을 찾지 못했습니다.");
        await node.__directorLong.setScenePrompt(sceneIndex(), text);
        say(`장면 ${sceneIndex() + 1} 카드에 넣었습니다 (외부 프롬프트 OFF).`);
      } else {
        target.applyPrompt(text);
        say(target.hasExternalPrompt() ? "Director 프롬프트에 넣었습니다. 단, 외부 프롬프트가 연결돼 있어 생성에는 외부 프롬프트가 쓰입니다." : "Director 프롬프트에 넣었습니다.", target.hasExternalPrompt());
      }
    };

    // ---------------- conversation (LLM chat editing). Stateless server; the log lives in data.chat.
    data.chat = Object.assign({ messages: [], llm: {} }, data.chat || {});
    data.chat.llm = Object.assign({ model: "", temperature: 0.3, num_ctx: 16384, num_predict: -1, history_turns: 6, think: false }, data.chat.llm);
    if (!data.chat.llm.model) data.chat.llm.model = data.writer.model;
    let chatPane = null;
    const openChat = () => {
      const chat = slot().chat, chatScene = jobScene();  // the log is this scene's; the LLM settings are shared
      const pane = h("div", { style: "position:absolute;inset:0;background:#0f1416;display:flex;flex-direction:column;z-index:5" });
      box.style.position = "relative";
      const log = h("div", { style: "flex:1;overflow:auto;padding:14px 18px;display:flex;flex-direction:column;gap:10px" });
      const input = h("textarea", { placeholder: "무엇이 이상한지, 어떻게 바꾸고 싶은지 적으세요. (Ctrl+Enter 전송)", style: "min-height:70px;flex:1" });
      const sendBtn = h("button", { class: "primary", text: "보내기", style: "padding:10px 22px" });
      const chatStatus = h("div", { class: "status" });
      const bubble = (m, i) => {
        const user = m.role === "user";
        const el = h("div", { style: `max-width:880px;align-self:${user ? "flex-end" : "flex-start"};background:${user ? "#1f3a4a" : "#151c1f"};border:1px solid #2c3a41;border-radius:10px;padding:10px 14px;white-space:pre-wrap` });
        el.append(h("div", { text: user ? m.content : (m.explanation || m.content) }));
        if (!user && m.prompt) {
          const same = m.prompt === result.value.trim();
          const put = h("button", { class: "small", text: same ? "결과 칸에 들어 있음" : "결과 칸에 넣기", disabled: same });
          put.onclick = () => { if (result.value.trim() !== m.prompt) slot().previous = result.value; result.value = m.prompt; slot().prompt = m.prompt; save(); put.textContent = "결과 칸에 들어 있음"; put.disabled = true; chatStatus.textContent = "결과 칸에 넣었습니다. 「적용」을 누르면 장면/Director에 들어갑니다."; chatStatus.classList.remove("err"); };
          const now = h("button", { class: "small", text: "바로 적용" });
          now.onclick = async () => { put.onclick(); try { await applyNow(); chatStatus.textContent = status.textContent; } catch (e) { chatStatus.textContent = e.message; chatStatus.classList.add("err"); } };
          const view = h("details", {}, [h("summary", { text: "제안된 프롬프트 보기" }), h("div", { class: "report", style: "max-height:320px", text: m.prompt })]);
          el.append(view, h("div", { class: "row", style: "margin-top:6px;justify-content:flex-start" }, [put, now]));
        }
        return el;
      };
      const renderLog = () => {
        log.innerHTML = "";
        if (!chat.messages.length) log.append(h("div", { class: "muted", text: "지금 결과 칸의 프롬프트를 두고 대화합니다. 무엇이 이상한지 적으면 원인을 설명하고, 고친 프롬프트를 제안합니다. 제안은 「결과 칸에 넣기」를 눌러야 반영되고, 이전 프롬프트로 되돌릴 수 있습니다." }));
        chat.messages.forEach((m, i) => log.append(bubble(m, i)));
        log.scrollTop = log.scrollHeight;
      };
      const llm = data.chat.llm, models = CATALOG.writer.model?.options || [];
      const setField = (label, key, props) => { const inp = h("input", { type: "number", ...props }); inp.value = llm[key]; inp.onchange = () => { llm[key] = Number(inp.value); save(); }; return h("label", { class: "dp-ps-field" }, [h("span", { text: label }), inp]); };
      const modelPick = h("select"); for (const o of models.includes(llm.model) ? models : [llm.model, ...models]) modelPick.append(h("option", { value: o, text: o })); modelPick.value = llm.model; modelPick.onchange = () => { llm.model = modelPick.value; save(); };
      const think = h("input", { type: "checkbox" }); think.checked = llm.think; think.onchange = () => { llm.think = think.checked; save(); };
      const settingsBox = h("details", { style: "margin:0 18px" }, [h("summary", { text: "대화 LLM 설정" }), h("div", { class: "dp-ps-grid4", style: "margin-top:8px" }, [
        h("label", { class: "dp-ps-field" }, [h("span", { text: "대화 모델" }), modelPick]), setField("temperature", "temperature", { step: "0.05", min: "0", max: "2" }),
        setField("문맥 길이 (토큰)", "num_ctx", { step: "1024", min: "2048", max: "131072" }), setField("최대 응답 토큰 (-1 무제한)", "num_predict", { step: "1", min: "-1" }),
        setField("기억할 이전 대화 (턴)", "history_turns", { step: "1", min: "0", max: "30" }), h("label", { class: "dp-ps-field" }, [h("span", { text: "생각(think) 모드" }), h("div", { class: "chk" }, [think])])])]);
      let tick = null;
      const pendingBubble = text => h("div", { style: "align-self:flex-end;background:#1f3a4a;border:1px solid #2c3a41;border-radius:10px;padding:10px 14px;white-space:pre-wrap;max-width:880px;opacity:.7", text });
      const showRunning = job => {  // also used when the window is reopened during a turn
        sendBtn.disabled = true; chatStatus.classList.remove("err"); clearInterval(tick);
        const t = () => { chatStatus.textContent = `${job.label}… ${Math.round((Date.now() - job.t0) / 1000)}초`; }; t(); tick = setInterval(t, 1000);
        if (job.kind === "chat" && job.text) { log.append(pendingBubble(job.text)); log.scrollTop = log.scrollHeight; }
      };
      const closeChat = () => { clearInterval(tick); pane.remove(); chatPane = null; save(); };
      const send = async () => {
        const text = input.value.trim(); if (!text || JOBS.has(node)) return;
        if (!llm.model) { chatStatus.textContent = "대화 모델을 고르세요."; chatStatus.classList.add("err"); settingsBox.open = true; return; }
        const p = payload();
        const body = {
          message: text, prompt: result.value, history: chat.messages.map(m => ({ role: m.role, content: m.role === "user" ? m.content : (m.explanation || m.content) })), llm,
          ollama_url: data.writer.ollama_url || "",
          context: { mode: p.director.mode, duration: p.director.duration, brief: slot().brief || "",
            references: pictures().slice(0, REF_MAX).map((_, i) => `<Picture ${i + 1}> role=${rolesOf()[i + 1] || "unset"}`),
            scene: long ? { index: sceneIndex(), count: long.clips.length, context_frames: Number(long.context_length) || 0, previous_prompt: sceneIndex() > 0 ? long.clips[sceneIndex() - 1]?.prompt || "" : "" } : null } };
        input.value = ""; chatUsed = true;
        await runJob(node, { kind: "chat", label: "생각 중", text }, () => getJSON("/director_plus/prompt_studio/chat", body), (d, r) => {
          const log = slotIn(d, chatScene.key).chat.messages;
          log.push({ role: "user", content: text }, { role: "assistant", content: r.reply, explanation: r.explanation, prompt: r.prompt });
          if (log.length > 60) log.splice(0, log.length - 60);
          return { text: r.prompt ? `답변 완료 (${r.seconds}초). 제안된 프롬프트를 확인하고 「결과 칸에 넣기」를 누르세요.` : `답변 완료 (${r.seconds}초).` };
        });
      };
      chatPane = {
        running: showRunning,
        done: notice => {
          clearInterval(tick); sendBtn.disabled = false; renderLog();
          chatStatus.textContent = notice.text || ""; chatStatus.classList.toggle("err", !!notice.err);
        },
      };
      sendBtn.onclick = send;
      input.addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } });
      const clear = h("button", { class: "small", text: "대화 지우기", onclick: () => { if (JOBS.has(node) || !chat.messages.length || !window.confirm("이 대화를 지울까요?")) return; chat.messages.splice(0); save(); renderLog(); } });
      pane.append(h("div", { class: "dp-ps-top" }, [h("h2", { text: "💬 LLM과 대화하며 다듬기" }), h("span", { class: "muted", text: long ? `장면 ${sceneIndex() + 1} · ${duration()}초` : `${duration()}초` }), h("span", { class: "grow" }), clear, h("button", { text: "← 돌아가기", onclick: closeChat })]),
        settingsBox, log,
        h("div", { style: "padding:10px 18px 14px;border-top:1px solid #243035;display:flex;flex-direction:column;gap:8px" }, [chatStatus, h("div", { class: "row", style: "align-items:stretch" }, [input, h("div", { style: "flex:0 0 auto;display:flex" }, [sendBtn])])]));
      box.append(pane); renderLog(); input.focus();
      if (JOBS.has(node)) showRunning(JOBS.get(node));
    };
    const chatBtn = act("LLM과 대화하며 다듬기", "", async () => {
      if (!CATALOG.ollama) throw new Error("Ollama에 연결하지 못했습니다. Ollama를 켜고 창을 다시 여세요.");
      openChat();
    });
    const reviseBtn = act("부분 수정", "", async () => {
      if (!result.value.trim()) throw new Error("수정할 프롬프트가 없습니다.");
      if (!reviseBox.value.trim()) throw new Error("고칠 부분을 적으세요.");
      const before = result.value, body = { prompt: before, request: reviseBox.value, writer: { ...data.writer, model: modelSel.value } }, scene = jobScene();
      await runJob(node, { kind: "revise", label: "부분 수정 중" }, () => getJSON("/director_plus/prompt_studio/revise", body), (d, r) => {
        const s = slotIn(d, scene.key);
        s.report = r.report;
        if (!r.applied) return { text: sceneNote(scene, "수정하지 않았습니다. 보고서를 확인하세요."), err: true };
        s.previous = before; s.prompt = r.prompt; s.revise = "";
        return { text: sceneNote(scene, "수정했습니다. 바뀐 내용은 「브리프 · 검사 결과」의 보고서에서 볼 수 있습니다.") };
      });
    });
    const prevBtn = act("이전 프롬프트", "", async () => {
      const s = slot();
      if (!s.previous) throw new Error("이전 프롬프트가 없습니다.");
      [s.prompt, s.previous] = [s.previous, result.value]; result.value = s.prompt; save(); say("이전 프롬프트로 바꿨습니다. 다시 누르면 되돌아갑니다.");
    });
    const applyBtn = act("적용", "apply", applyNow);

    panel.append(
      h("h3", {}, [h("span", { text: "프롬프트" }), h("span", { class: "grow" }), briefBtn]),
      h("label", { class: "dp-ps-field" }, [h("span", { text: "Ollama 모델" }), modelSel]),
      h("details", {}, [h("summary", { text: "LLM 고급 설정" }), adv]),
      h("label", { class: "dp-ps-field", style: "margin-top:8px" }, [h("span", { text: long ? "적용할 장면" : "적용 대상" }), targetSel]),
      h("div", { class: "dp-ps-col", style: "gap:8px;margin-top:10px" }, [writeBtn, chatBtn]),
      h("div", { class: "muted", style: "margin:8px 0", text: "작성은 ComfyUI 대기열 밖에서 실행됩니다. 시작할 때 ComfyUI 모델을 내리고, 끝나면 Ollama 모델도 내립니다. Director 타임라인의 영상 레퍼런스는 자동으로 분석합니다." }),
      result, reportDetails,
      h("div", { class: "row", style: "margin-top:10px" }, [applyBtn]),
      status,
      h("details", { open: true }, [h("summary", { text: "Prompt Freeze · 부분 수정" }), reviseBox, h("div", { class: "row", style: "margin-top:6px" }, [reviseBtn, prevBtn])]),
    );
    if (!CATALOG.ollama) say("Ollama에 연결하지 못했습니다. Ollama를 켜고 창을 다시 여세요.", true);
    right.append(panel);

    view = {
      started: job => { lock(true, job.label, job.t0); chatPane?.running(job); },
      done: notice => {
        lock(false);
        result.value = slot().prompt || ""; reviseBox.value = slot().revise || ""; showReport();
        if (notice.openReport) reportDetails.open = true;
        say(notice.text, notice.err);
        if (notice.kind === "chat") chatUsed = true;
        chatPane?.done(notice);
      },
    };
    node.__dpPsView = view;
    const running = JOBS.get(node);
    if (running) {  // reopened while a job started from an earlier window is still running
      lock(true, running.label, running.t0);
      if (running.kind === "chat") openChat();
    } else if (data.notice) {  // a job finished while the window was closed
      const n = data.notice; delete data.notice; save();
      if (n.openReport) reportDetails.open = true;
      if (n.kind === "chat") { chatUsed = true; say(n.err ? n.text : "창을 닫은 동안 대화 답변이 도착했습니다. 「LLM과 대화하며 다듬기」에서 확인하세요.", n.err); }
      else say(n.text, n.err);
    }
  },

  // .ext projects carry the window state (per-scene shot cards, settings, roles, results, chat).
  isBusy(node) { return JOBS.has(node); },
  exportState(node) {
    const data = node.properties?.[PROP];
    if (!data) return null;
    const copy = JSON.parse(JSON.stringify(data));
    delete copy.notice;
    return copy;
  },
  // Writer / chat LLM settings (Ollama address, models ...) belong to this PC, so the workflow's
  // current ones are kept; everything else comes from the project.
  importState(node, incoming) {
    if (!incoming || typeof incoming !== "object" || JOBS.has(node)) return false;
    node.properties = node.properties || {};
    const cur = node.properties[PROP];
    const next = JSON.parse(JSON.stringify(incoming));
    delete next.notice;
    if (cur?.writer) { next.writer = cur.writer; next.writerImported = cur.writerImported; }
    if (cur?.chat?.llm) next.chat = { ...(next.chat || {}), llm: cur.chat.llm };
    else if (cur && next.chat) delete next.chat.llm;
    node.properties[PROP] = next;
    app.graph?.setDirtyCanvas(true, true);
    return true;
  },
};

window.DirectorPlusPromptStudio = DirectorPlusPromptStudio;
app.registerExtension({ name: "DirectorPlus.PromptStudio" });
