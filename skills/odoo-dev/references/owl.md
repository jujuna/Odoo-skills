# OWL 2 & Frontend — Odoo 19

Odoo 19 ships **OWL 2** (`addons/web/static/lib/owl/owl.js` reports `2.8.4`): `useState`,
`static props`, `useRef` + `ref.el`, `useEffect(fn, () => deps)`. Signals, `proxy()`,
`computed()` and `useProps` are OWL 3 (Odoo 20) and do not exist here.

**Working rule: before writing a component, open the nearest equivalent in
`addons/web/static/src/` and copy its shape.** Idioms are set by what core does, not by
external documentation or memory of another version.

1. [What OWL 2 exports](#1-what-owl-2-exports)
2. [Canonical component](#2-canonical-component)
3. [Reactivity](#3-reactivity)
4. [Props](#4-props)
5. [Effects and lifecycle](#5-effects-and-lifecycle)
6. [Templates](#6-templates)
7. [Services and registries](#7-services-and-registries)
8. [Asset bundles](#8-asset-bundles)
9. [Common patterns](#9-common-patterns)
10. [Inheriting core OWL templates and patching](#10-inheriting-core-owl-templates-and-patching)
11. [Tests](#11-tests)
12. [Review checklist](#12-review-checklist)

---

## 1. What OWL 2 exports

**`@odoo/owl`** (the `exports.*` block at the end of
[owl.js](../../../../addons/web/static/lib/owl/owl.js)): `App Component EventBus OwlError
batched blockDom htmlEscape loadFile markRaw markup mount onError onMounted onPatched
onRendered onWillDestroy onWillPatch onWillRender onWillStart onWillUnmount
onWillUpdateProps reactive status toRaw useChildSubEnv useComponent useEffect useEnv
useExternalListener useRef useState useSubEnv validate validateType whenReady xml`.

Importing a name it does not export (`proxy`, `signal`, `computed`, `useProps`, `t`,
`useListener` — all OWL 3) does **not** fail the bundle: the binding is `undefined` and the
component crashes when `setup()` calls it. Grep imports against this list.

Counts in `addons/web/static/src`: `useState(` 120, `static props` 299,
`useExternalListener(` 43, `t-esc=` 323, `t-out=` 90, `t-slot=` 205.

---

## 2. Canonical component

Shape of [addons/web/static/src/core/notebook/notebook.js](../../../../addons/web/static/src/core/notebook/notebook.js):

```js
import { Component, onWillRender, onWillUpdateProps, useEffect, useRef, useState } from "@odoo/owl";

export class Notebook extends Component {
    static template = "web.Notebook";
    static defaultProps = {
        className: "",
        onPageUpdate: () => {},
    };
    static props = {
        slots: { type: Object, optional: true },
        pages: { type: Object, optional: true },
        className: { type: String, optional: true },
        defaultPage: { type: String, optional: true },
        onPageUpdate: { type: Function, optional: true },
    };

    setup() {
        this.activePane = useRef("activePane");
        this.pages = this.computePages(this.props);
        this.state = useState({ currentPage: null });
        this.state.currentPage = this.computeActivePage(this.props.defaultPage, true);
        useEffect(
            () => {
                this.props.onPageUpdate(this.state.currentPage);
                this.activePane.el?.classList.add("show");
            },
            () => [this.state.currentPage]
        );
        onWillUpdateProps((nextProps) => {
            this.pages = this.computePages(nextProps);
            this.state.currentPage = this.computeActivePage(nextProps.defaultPage, true);
        });
    }

    get navItems() {
        return this.pages.filter((e) => e[1].isVisible);
    }
}
```

Shape rules:
- `static template = "module.ComponentName"`
- `static props` (and `static defaultProps` for optional props with a default)
- everything reactive and every hook created in `setup()`, never in the constructor
- getters for derived values; recompute in `onWillUpdateProps` when the value depends on props
- no `/** @odoo-module */` header needed: 9 of 526 core files in `web/static/src` still have it

---

## 3. Reactivity

```js
import { useState, reactive } from "@odoo/owl";

this.state = useState({ count: 0, items: [] });   // component state, re-renders on change
this.state.count++;

const store = reactive({ items: [] });             // shared object outside a component
this.store = useState(store);                      // subscribe a component to it
```

- `useState` for component state; `reactive` for a store shared between components or a
  service, then `useState(store)` in each component that renders it
- getters re-run on every render; cache in state (set in `onWillUpdateProps` or an effect)
  only when the derivation is expensive
- mutate in place (`this.state.items.push(x)`) — replacing the whole state object breaks
  the subscription

---

## 4. Props

```js
export class MyField extends Component {
    static template = "my_module.MyField";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
    };
    static defaultProps = { readonly: false };
}
```

| Component | v19 declaration (copy from core) |
|---|---|
| field widget | `static props = { ...standardFieldProps, ... }` ([char_field.js](../../../../addons/web/static/src/views/fields/char/char_field.js)) |
| client action | `static props = { ...standardActionServiceProps }` from `@web/webclient/actions/action_service` |
| dialog / any component | `static props = { close: Function, x: { type: Number, optional: true } }` |

- every prop the parent passes must be declared, or dev mode raises a props validation error
- `optional: true` props without a `defaultProps` entry are `undefined`
- `["*"]` disables validation — only when the props genuinely vary

---

## 5. Effects and lifecycle

```js
import { onWillStart, onMounted, onWillUnmount, onWillUpdateProps, useEffect,
         useExternalListener } from "@odoo/owl";

setup() {
    onWillStart(async () => { this.data = await this.orm.call(...); });  // before first render
    onMounted(() => { ... });                                            // DOM is live
    onWillUnmount(() => { ... });                                        // cleanup

    useEffect(
        (enabled) => {
            if (!enabled) return;
            const id = setInterval(tick, 1000);
            return () => clearInterval(id);
        },
        () => [this.state.enabled],     // dependency list, as a function
    );

    onWillUpdateProps(async (nextProps) => {
        if (nextProps.resId !== this.props.resId) await this.load(nextProps.resId);
    });

    useExternalListener(window, "resize", this.onResize);
}
```

- `useEffect(effect, () => deps)` — deps are a **function**; the effect runs after mount
  and after each patch where a dep changed; omitting deps (default `[NaN]`) re-runs it after
  every patch, `() => []` runs it once ([owl.js:6268](../../../../addons/web/static/lib/owl/owl.js#L6268))
- return a cleanup function from the effect; never leave a listener or interval behind
- `onWillUpdateProps` for "react to a prop changing", `useEffect` for "sync the DOM"
- `onWillStart` for the initial async load; do not fetch in `setup()` directly
- `useExternalListener(target, ev, fn)` attaches on mount and detaches on unmount
  ([owl.js:6304](../../../../addons/web/static/lib/owl/owl.js#L6304)), with `this` bound
  to the component

---

## 6. Templates

```xml
<t t-name="my_module.MyField">
    <div t-attf-class="o_my_field {{ props.readonly ? 'o_readonly' : '' }}">
        <span t-out="displayValue"/>
        <t t-foreach="items" t-as="item" t-key="item.id">
            <button t-on-click="() => this.select(item)" t-out="item.name"/>
        </t>
        <input t-ref="input" t-att-value="state.value"/>
        <t t-if="props.slots" t-slot="default"/>
        <MyChild value="state.value" t-props="childProps"/>
    </div>
</t>
```

- the template scope is the component: `props.x`, `state.x`, `myGetter` work without
  `this.`; inside arrow functions write `this.select(...)`
- `t-out` is preferred; `t-esc` still works (323 uses in core). Both escape; `t-out`
  renders a `markup()` value as HTML, so never wrap user input in `markup()`
- `t-key` on every `t-foreach`
- `t-slot="name"` renders a slot, `t-set-slot="name"` fills one
- `t-ref="name"` (a string) pairs with `useRef("name")`; read `ref.el` after mount
- `t-custom-click="handler"` is an Odoo custom directive that also binds `auxclick`
  (middle-click) — [env.js:174](../../../../addons/web/static/src/env.js#L174)
- `t-portal` exists (5 core uses) for rendering into another DOM node

---

## 7. Services and registries

```js
import { registry } from "@web/core/registry";

registry.category("services").add("myService", {
    dependencies: ["orm", "notification"],
    start(env, { orm, notification }) {
        return {
            async doThing(id) { return orm.call("my.model", "do_thing", [[id]]); },
        };
    },
});
```

```js
import { useService } from "@web/core/utils/hooks";
this.orm = useService("orm");
this.action = useService("action");
this.notification = useService("notification");
this.dialog = useService("dialog");
this.ui = useService("ui");                       // this.ui.isSmall; env.isSmall also works
```

Not services in v19 (0 `useService("rpc")` / `useService("user")` in `addons/`):

```js
import { rpc } from "@web/core/network/rpc";      // rpc("/my_module/route", { x: 1 })
import { user } from "@web/core/user";            // user.userId, user.context, user.hasGroup(...)
```

Common categories: `services`, `actions`, `fields`, `view_widgets`, `systray`, `main_components`,
`formatters`, `parsers`, `command_provider`.

```xml
<record id="my_dashboard_action" model="ir.actions.client">
    <field name="name">My Dashboard</field>
    <field name="tag">my_module.my_dashboard</field>
</record>
```

---

## 8. Asset bundles

```python
'assets': {
    'web.assets_backend': [
        'my_module/static/src/**/*',
    ],
    'web.assets_frontend': [
        'my_module/static/src/public/**/*',
    ],
    'web.assets_unit_tests': [
        'my_module/static/tests/**/*',
    ],
},
```

- `web.assets_backend` — the webclient
- `web.assets_frontend` — website / portal
- `web.assets_unit_tests` — Hoot tests
- glob the directory; do not list files one by one unless order matters
- `('replace', old, new)`, `('remove', path)`, `('before', ref, path)` for surgical edits

### Dark mode

`web.assets_web_dark` is `('include', 'web.assets_web')` plus every `*.dark.scss`
([web manifest](../../../../addons/web/__manifest__.py)); `web_enterprise` loads the dark
values of the primary variables first, so **every backend SCSS file is compiled twice**.
A hard-coded `#fff` card or `#333` text stays light in dark mode, and light text lands on
a light box.

- Neutrals come from Odoo variables, never hex: `$o-view-background-color` (card/surface),
  `$o-gray-100` (inset boxes, table header/footer, toolbars), `$o-gray-300` (borders),
  `$o-gray-400` (input borders), `$o-main-text-color`, `$o-gray-600` (muted text). Their
  light values equal the usual Bootstrap greys, so the light theme does not move.
- Tints that must work on both backgrounds: `rgba($o-info, 0.08)` for hover, Bootstrap
  `text-bg-*` / `alert-*` classes for badges and banners.
- Colours of your own that need a different shade on dark get both values in the token
  block. `$o-webclient-color-scheme` is `bright` by default
  ([primary_variables.scss:13](../../../../addons/web/static/src/scss/primary_variables.scss#L13))
  and `dark` in the dark build
  ([web_enterprise primary_variables.dark.scss:55](../../../../enterprise/web_enterprise/static/src/scss/primary_variables.dark.scss#L55)):

```scss
$my-dark: $o-webclient-color-scheme == dark;
$my-primary:      #2563eb;                         // fill: white text on it reads on both
$my-primary-text: if($my-dark, #60a5fa, #2563eb);  // text/icon/border on the page
$my-soft:         if($my-dark, mix(#2563eb, $o-view-background-color, 18%), #eaf1fe);
```

  The light value stays the original hex, so the light theme cannot move. Keep a
  separate token for fills and for text: a mid-tone fill is fine on both themes, the
  same colour as text on a dark background is not. Tints: `mix(<colour>, $o-view-background-color, 10–45%)`.
- `*.dark.scss` in `web.assets_web_dark` (core `web_enterprise`) is for overriding
  selectors you do not own. For your own stylesheet, one token block is easier to keep
  correct than a parallel file of selectors.
- CSS `min()` / `max()` / `clamp()` with mixed units (`min(22rem, 100%)`) are evaluated by
  libsass ([assetsbundle.py:1044](../../../../odoo/addons/base/models/assetsbundle.py#L1044))
  as Sass functions and fail with "Incompatible units: '%' and 'rem'". The error breaks
  the whole bundle: Odoo serves the previous CSS plus an error banner. Escape it
  (`#{"min(22rem, 100%)"}`) or use a media query, and compile the bundles after every SCSS edit.
- `web.dark_mode_variables` with `('before', 'x.variables.scss', 'x.variables.dark.scss')`
  (core `onboarding`, `documents`): the target **must** be in `web._assets_primary_variables`.
  `web_enterprise` also includes `web.dark_mode_variables` in `web.assets_backend_lazy_dark`
  ([web_enterprise manifest:53](../../../../enterprise/web_enterprise/__manifest__.py#L53)), so a
  target in `web.assets_backend` raises `File(s) ... not found in bundle web.dark_mode_variables`:
  `/web/bundle/web.assets_backend_lazy_dark` returns 500 and graph/pivot/gantt/grid views break
  for dark-mode users only.
- `var(--o-component-background)`, `var(--o-text-color)`, `var(--o-border-color)`,
  `var(--o-text-color-muted)`, `var(--o-brand-primary)`, `var(--o-view-background-color)`,
  `var(--o-main-text-color)` do **not exist** (`--o-input-background-color` is only set
  locally in three core stylesheets) — a `var(--x, #fff)` always renders its light fallback.
- Components that route colours through their own CSS custom properties get both values
  by interpolation, so only the property block changes:
  `--grid-surface: #{if($my-dark, $o-view-background-color, #fff)};`
- A module that is not installed can still be checked: compile its SCSS with `sass`
  (libsass, in the venv) after a prelude that sets the light, then the dark, values of the
  `$o-*` variables it uses, and compare the resolved colours.
- `$o-gray-200` equals the view background in dark mode — for a light border use
  `mix($o-gray-200, $o-gray-300)` or `$o-gray-300`.
- HTML that is also sent by email (`body_html`, `message_post` bodies) keeps its inline
  light styles; make sure every text node in it sets its own `color`, so it reads as a
  light card in the dark chatter, as core emails do.
- Verify: before editing, compile `web.assets_web` and `web.assets_web_dark`
  (`env['ir.qweb']._get_asset_bundle(name).css()`), keep your module's rules; after editing,
  the light set must be identical and the dark set must have no light background or
  near-black text left.

---

## 9. Common patterns

```js
// ORM call
const records = await this.orm.searchRead("my.model", [["state", "=", "draft"]], ["name"]);

// open a record
this.action.doAction({
    type: "ir.actions.act_window",
    res_model: "my.model",
    res_id: id,
    views: [[false, "form"]],
});

// notification
this.notification.add(_t("Saved"), { type: "success" });

// dialog
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
this.dialog.add(ConfirmationDialog, {
    body: _t("Delete this record?"),
    confirm: () => this.delete(),
});

// bus between components
import { useBus } from "@web/core/utils/hooks";
useBus(this.env.bus, "my-event", (ev) => this.onEvent(ev.detail));

// debounce
import { debounce } from "@web/core/utils/timing";
this.onSearch = debounce(this.search.bind(this), 300);

// translation
import { _t } from "@web/core/l10n/translation";
```

`_t()` marks a translatable string; never build it from concatenation.

Errors from `orm.call` / `rpc` are `RPCError` (`error.data.message` holds the server
message). Let them propagate unless you can recover — the webclient shows the error
dialog; a `catch` that only notifies hides the traceback.

Browser RPC cache (IndexedDB, `rpc_cache.js`): `orm.cache({type: "disk"})` calls (get_views) and
`/web/action/load` are keyed by `{url, params}`, and the ORM merges `user.context`, which
carries `uid` ([orm_service.js:129](../../../../addons/web/static/src/core/orm_service.js#L129),
[user.js:172](../../../../addons/web/static/src/core/user.js#L172)): the key holds the uid even when a
caller filters its own context ([view_service.js:92](../../../../addons/web/static/src/views/view_service.js#L92)).
To drop cached views and actions after the server's answers change, call
`rpcBus.trigger("CLEAR-CACHES")` (`import { rpcBus } from "@web/core/network/rpc"`), as core does in
[view_service.js:51](../../../../addons/web/static/src/views/view_service.js#L51).

---

## 10. Inheriting core OWL templates and patching

```xml
<!-- copy the attribute text from the current core template -->
<xpath expr="//t[@t-component='props.Renderer']" position="replace">
```

- Open the core template and copy the attribute **as it is now**
  ([list_controller.xml:87](../../../../addons/web/static/src/views/list/list_controller.xml#L87)
  for `web.ListView`). Never write an xpath from memory or from another Odoo version — the
  v20 templates use `this.props.Renderer` and match nothing here.
- `replace` of a node that carries `t-if`: check the next sibling. A replacement without the
  `t-if` can leave an orphan `t-elif`/`t-else`, and the template fails to compile. Put the
  condition on your wrapper.
- Props you duplicate from a core node must match the core node exactly.
- Templates rendered through `t-call` with a `t-set` (e.g. account report warnings:
  `<t t-set="warningParams" .../>` in
  [account_report.xml:63](../../../../enterprise/account_reports/static/src/components/account_report/account_report.xml#L63))
  receive **locals** — read them by name.
- Test every xpath against the core template before shipping:

```python
# data_venv/bin/python, repo root — prints OK/MISS per xpath
from lxml import etree
core = etree.parse('addons/web/static/src/views/list/list_controller.xml')
tpl = next(t for t in core.iter('t') if t.get('t-name') == 'web.ListView')
print(bool(tpl.xpath("//t[@t-component='props.Renderer']")))
```

Patching core JS:

```js
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        // extra hooks here, inside setup
    },
    async onRecordSaved(record) {
        await super.onRecordSaved(...arguments);
        if (record.resModel === "my.model") { ... }
    },
});
```

- patch the **prototype** for instance methods; patch the class itself for statics
  (`static props`, `components`) — and extend `props` there when your template passes a new one
- always call `super` with `...arguments`; check the target method still exists and has the
  same signature in this version before patching
- hooks only inside a patched `setup()`
- the patch applies to every instance — guard on `resModel` or a prop, never assume one view

---

## 11. Tests

JS tests are Hoot (`@odoo/hoot`, 1173 files in `addons/`); QUnit is legacy (7 files).
Helpers come from `@web/../tests/web_test_helpers` (`mountWithCleanup`, `contains`,
`defineModels`, `onRpc`); test files go in `static/tests/` and the
`web.assets_unit_tests` bundle. Copy a core `*.test.js` next to the feature you test.

---

## 12. Review checklist

- [ ] Only names `@odoo/owl` exports are imported (§1); no OWL 3 names
- [ ] `static props` declares every prop the parent passes; defaults in `static defaultProps`
- [ ] State via `useState` / `reactive`, mutated in place
- [ ] `useEffect(fn, () => deps)` with deps as a function, and a cleanup return
- [ ] `useRef("x")` + `t-ref="x"`; `ref.el` read only after mount
- [ ] Every xpath into a core template matches the **current** v19 core attribute text (§10)
- [ ] Every `patch()` target method exists in the v19 class; `super` called
- [ ] Icons are Font Awesome (`fa fa-*`) or Odoo UI icons (`oi oi-*`) — `views.md`
- [ ] Every `t-foreach` has `t-key`
- [ ] `t-out` in new code; no `markup()` around user input
- [ ] Effects and `onWillUnmount` clean up; no leaked listeners or timers
- [ ] Async loading in `onWillStart`, not in `setup()`
- [ ] `rpc` and `user` imported, not `useService("rpc")` / `useService("user")`
- [ ] User-facing strings wrapped in `_t()`
- [ ] Component shape matches the nearest core component you copied from
