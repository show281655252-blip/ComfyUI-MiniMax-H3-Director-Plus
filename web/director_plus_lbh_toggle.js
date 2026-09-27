import { app } from "../../scripts/app.js";

// "LBH 8+4" only means something while LBH itself is on. On any node (usually the
// Settings subgraph) that exposes both widgets, LBH OFF forces 8+4 OFF and greys it
// out; LBH ON gives back the value it had before (ON when unknown, e.g. opened while OFF).
//
// Subgraph widgets are projections rebuilt on every render (hover, focus...). Their real
// state (value, disabled) lives in the frontend's "widgetValue" store keyed by widgetId,
// so the lock is written there; a flag set on the projection alone is lost on re-render.
const LBH = "lbh_latent_upscale_enabled";
const FULL = "lbh_full_first_pass";
const memory = new WeakMap();
let widgetStore;

function store() {
    if (widgetStore !== undefined) return widgetStore;
    const root = document.querySelector("#vue-app") || [...document.querySelectorAll("body *")].find((e) => e.__vue_app__);
    const stores = root?.__vue_app__?.config?.globalProperties?.$pinia?._s;
    widgetStore = stores?.get("widgetValue") ?? null;
    return widgetStore;
}

// A re-render re-registers the promoted widget from the widgets it is linked to inside
// the subgraph, so those must carry the lock too or it flashes off on every hover.
function innerWidgets(node, name) {
    const subgraph = node.subgraph;
    const input = subgraph?.inputs?.find((i) => i.name === name);
    if (!input) return [];
    return (input.linkIds || []).flatMap((id) => {
        const link = subgraph.getLink?.(id) ?? subgraph.links?.get?.(id) ?? subgraph.links?.[id];
        const target = link && subgraph.getNodeById?.(link.target_id);
        const slot = target?.inputs?.[link.target_slot];
        const widget = slot && target.getWidgetFromSlot?.(slot);
        return widget ? [widget] : [];
    });
}

function setDisabled(node, widget, disabled) {
    const state = widget.widgetId ? store()?.getWidget?.(widget.widgetId) : null;
    let changed = false;
    for (const inner of innerWidgets(node, FULL)) {
        if (Boolean(inner.disabled) !== disabled) inner.disabled = disabled;
    }
    if (state && Boolean(state.disabled) !== disabled) {
        state.disabled = disabled;
        changed = true;
    }
    if (Boolean(widget.disabled) !== disabled) {
        widget.disabled = disabled;
        changed = true;
    }
    return changed;
}

function sync(node) {
    const lbh = node.widgets?.find((w) => w.name === LBH);
    const full = node.widgets?.find((w) => w.name === FULL);
    if (!lbh || !full) return;
    let state = memory.get(node);
    if (!state) {
        state = { lbh: Boolean(lbh.value), remembered: lbh.value ? Boolean(full.value) : true };
        memory.set(node, state);
    }
    const on = Boolean(lbh.value);
    let changed = state.lbh !== on;
    if (on && !state.lbh) full.value = state.remembered;
    if (on) {
        state.remembered = Boolean(full.value);
    } else if (full.value) {
        full.value = false;
        changed = true;
    }
    changed = setDisabled(node, full, !on) || changed;
    if (changed) node.setDirtyCanvas?.(true, true);
    state.lbh = on;
}

function nodes() {
    const graphs = new Set([app.graph, app.canvas?.graph].filter(Boolean));
    return [...graphs].flatMap((graph) => graph._nodes || graph.nodes || []);
}

app.registerExtension({
    name: "DirectorPlus.LbhFullPassToggle",
    setup() {
        setInterval(() => {
            for (const node of nodes()) sync(node);
        }, 250);
    },
});
