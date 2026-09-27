import { app } from "../../scripts/app.js";

// "LBH 8+4" only means something while LBH itself is on. On any node (usually the
// Settings subgraph) that exposes both widgets, LBH OFF forces 8+4 OFF and greys it
// out; LBH ON gives back the value it had before (ON when unknown, e.g. opened while OFF).
// Promoted subgraph widgets are recreated on re-render, so state is kept per node and
// re-applied on a short poll instead of being attached to widget objects.
const LBH = "lbh_latent_upscale_enabled";
const FULL = "lbh_full_first_pass";
const memory = new WeakMap();

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
    if (on && !state.lbh) full.value = state.remembered;
    if (on) {
        state.remembered = Boolean(full.value);
        if (full.disabled) full.disabled = false;
    } else {
        if (full.value) full.value = false;
        if (!full.disabled) full.disabled = true;
    }
    if (state.lbh !== on) node.setDirtyCanvas?.(true, true);
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
