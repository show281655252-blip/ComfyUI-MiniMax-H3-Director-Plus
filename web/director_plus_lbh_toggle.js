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
    // Setting the promoted value does not reach these, and a re-render copies their
    // value back (a stale `true` flashed the row on after LBH was switched off).
    const value = Boolean(widget.value);
    for (const inner of innerWidgets(node, FULL)) {
        if (Boolean(inner.disabled) !== disabled) inner.disabled = disabled;
        if (Boolean(inner.value) !== value) inner.value = value;
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

// Root cause of the hover flash: a subgraph node rebuilds its promoted widget views on
// re-render, and a fresh view has no `disabled` of its own, so it draws unlocked until the
// poll runs again. Give every new view a `disabled` backed by the widget store, so a
// rebuilt view is locked from its first frame.
let projectionPatched = false;
function patchProjection(node) {
    if (projectionPatched || typeof node._projectPromotedWidget !== "function") return;
    let proto = Object.getPrototypeOf(node);
    while (proto && !Object.prototype.hasOwnProperty.call(proto, "_projectPromotedWidget")) {
        proto = Object.getPrototypeOf(proto);
    }
    if (!proto) return;
    projectionPatched = true;
    const original = proto._projectPromotedWidget;
    proto._projectPromotedWidget = function (...args) {
        const view = original.apply(this, args);
        if (view && view.widgetId && !Object.getOwnPropertyDescriptor(view, "disabled")?.get) {
            const id = view.widgetId;
            let own = view.disabled;
            delete view.disabled;
            Object.defineProperty(view, "disabled", {
                configurable: true,
                enumerable: true,
                get() {
                    const state = store()?.getWidget?.(id);
                    return state ? Boolean(state.disabled) : Boolean(own);
                },
                set(value) {
                    own = value;
                    const state = store()?.getWidget?.(id);
                    if (state) state.disabled = Boolean(value);
                },
            });
        }
        return view;
    };
}

// Lets other Director Plus code (e.g. .ext load) set 8+4 without the poll restoring an older
// remembered value when it sees LBH switch on.
window.DirectorPlusLbhToggle = {
    remember(node, full, lbhOn) {
        memory.set(node, { lbh: Boolean(lbhOn), remembered: Boolean(full) });
    },
};

function nodes() {
    const graphs = new Set([app.graph, app.canvas?.graph].filter(Boolean));
    return [...graphs].flatMap((graph) => graph._nodes || graph.nodes || []);
}

app.registerExtension({
    name: "DirectorPlus.LbhFullPassToggle",
    setup() {
        setInterval(() => {
            for (const node of nodes()) {
                patchProjection(node);
                sync(node);
            }
        }, 250);
    },
});
