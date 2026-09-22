# OWL 3 & Frontend — Odoo 20

Odoo 20 ships **OWL 3** (`addons/web/static/lib/owl/owl.js` reports `3.0.0-alpha.49`).
This is a new reactivity model — signals and proxies — not a version bump. Anything you
remember from OWL 2 (`useState`, `reactive`, `t-esc`, implicit `this` in templates) is
either gone or moved to a compatibility layer.

**Working rule: before writing a component, open the nearest equivalent in
`addons/web/static/src/` and copy its shape.** OWL 3 is still alpha and the idioms are set
by what core does, not by external documentation.

1. [What changed from OWL 2](#1-what-changed-from-owl-2)
2. [Canonical component](#2-canonical-component)
3. [Reactivity: proxy, signal, computed](#3-reactivity-proxy-signal-computed)
4. [Props with `useProps` and `t`](#4-props-with-useprops-and-t)
5. [Effects and lifecycle](#5-effects-and-lifecycle)
6. [Templates](#6-templates)
7. [Services and registries](#7-services-and-registries)
8. [Asset bundles](#8-asset-bundles)
9. [Common patterns](#9-common-patterns)
10. [Review checklist](#10-review-checklist)

---

## 1. What changed from OWL 2

| OWL 2 | OWL 3 | Import |
|---|---|---|
| `useState(obj)` | `proxy(obj)` | `@odoo/owl` |
| `reactive(obj)` | `proxy(obj)` | `@odoo/owl` |
| — | `signal(v)`, `signal.ref()` | `@odoo/owl` |
| computed getter | `computed(() => ...)`, **called**: `this.pages()` | `@odoo/owl` |
| `static props = {...}` | `props = useProps(schema)` with `t.*` types | `@odoo/owl` |
| `useEffect` | `useLayoutEffect` | `@web/owl2/utils` |
| `onWillRender`, `onRendered` | same names | `@web/owl2/utils` |
| `useEnv`, `useSubEnv`, `useChildSubEnv` | same names | `@web/owl2/utils` |
| `useRef`, `useComponent`, `useExternalListener` | same names | `@web/owl2/utils` |
| `t-esc` | `t-out` | — |
| `t-slot="x"` | `t-call-slot="x"` | — |
| implicit `props.x` in templates | explicit `this.props.x` | — |
| `t-portal` | `t-custom-portal` | compat layer |

Counts in `addons/web/static/src`: `useState` 0, `proxy(` 146, `useProps(` 320,
`signal.ref()` 143, `computed(` 73, `t-esc` 2, `t-slot=` 0, `t-call-slot=` 95.

Importing a legacy hook from `@odoo/owl` fails. Legacy hooks come from `@web/owl2/utils`,
which is a thin re-export — [addons/web/static/src/owl2/utils.js](../../../../addons/web/static/src/owl2/utils.js).

---

## 2. Canonical component

Straight from [addons/web/static/src/core/notebook/notebook.js](../../../../addons/web/static/src/core/notebook/notebook.js):

```js
import { useLayoutEffect } from "@web/owl2/utils";
import { Component, computed, proxy, signal, t, useOnChange, useProps } from "@odoo/owl";

export const notebookProps = {
    slots: t.object().optional(),
    pages: t.array().optional(),
    className: t.string().optional(""),
    defaultPage: t.string().optional(),
    onPageUpdate: t.function().optional(() => () => {}),
};

export class Notebook extends Component {
    static template = "web.Notebook";
    props = useProps(notebookProps);

    activePane = signal.ref();

    setup() {
        this.pages = computed(() => this.computePages(this.props));
        this.state = proxy({ currentPage: null });
        this.state.currentPage = this.computeActivePage(this.props.defaultPage, true);

        useLayoutEffect(
            () => { this.props.onPageUpdate(this.state.currentPage); },
            () => [this.state.currentPage],
        );

        useOnChange(
            () => [this.props.defaultPage],
            (defaultPage) => { this.state.currentPage = this.computeActivePage(defaultPage, true); },
            { initialRun: false },
        );
    }

    get navItems() {
        return this.pages().filter((e) => e[1].isVisible);
    }
}
```

Shape rules:
- `static template = "module.ComponentName"`
- `props = useProps(schema)` as a class field, schema exported for reuse
- refs as class fields: `myRef = signal.ref()`
- everything reactive created in `setup()`
- getters for derived values used once; `computed()` for derived values used repeatedly or
  in dependency lists

---

## 3. Reactivity: proxy, signal, computed

```js
// mutable reactive object — the replacement for useState
this.state = proxy({ count: 0, items: [] });
this.state.count++;                   // triggers a re-render

// a single reactive value
const count = signal(0);
count(1);                             // write
count();                              // read

// a DOM/component ref
this.inputRef = signal.ref();         // template: t-ref="this.inputRef"
this.inputRef()?.focus();

// derived value — lazily evaluated, cached, called like a function
this.total = computed(() => this.state.items.reduce((a, i) => a + i.price, 0));
this.total();
```

- `proxy()` for an object you mutate in place (component state, a form buffer)
- `signal()` for one value passed around or shared between components
- `computed()` when the derivation is non-trivial or read from several places — a plain
  getter re-runs on every access, `computed()` caches until a dependency changes
- `computed()` and `signal()` results are **called**: `this.total()`, not `this.total`.
  This is the most common OWL 3 mistake — a forgotten `()` renders the function.

---

## 4. Props with `useProps` and `t`

```js
export const myProps = {
    record: t.object(),                       // required
    readonly: t.boolean().optional(false),    // optional with default
    label: t.string().optional(),
    onChange: t.function().optional(() => () => {}),
    slots: t.object().optional(),
    extra: t.any().optional(),
};

export class MyField extends Component {
    static template = "my_module.MyField";
    props = useProps(myProps);
}
```

- export the schema so other components can spread it (`{ ...myProps, extra: t.string() }`)
- `.optional(defaultValue)` replaces the OWL 2 `static defaultProps`
- `t.any()` only when the type genuinely varies — it disables validation

---

## 5. Effects and lifecycle

```js
import { useLayoutEffect, onWillRender } from "@web/owl2/utils";
import { onWillStart, onMounted, onWillUnmount, useOnChange } from "@odoo/owl";

setup() {
    onWillStart(async () => { this.data = await this.orm.call(...); });  // before first render
    onMounted(() => { ... });                                            // DOM is live
    onWillUnmount(() => { ... });                                        // cleanup

    useLayoutEffect(
        () => { const id = setInterval(tick, 1000); return () => clearInterval(id); },
        () => [this.state.enabled],     // dependency list, as a function
    );

    useOnChange(
        () => [this.props.resId],       // deps
        (resId) => { this.load(resId); },
        { initialRun: false },
    );
}
```

- `useLayoutEffect` takes `(effect, () => deps)` — the deps are a **function**
- return a cleanup function from the effect; never leave a listener or interval behind
- `useOnChange` is for "react to a prop changing", `useLayoutEffect` for "sync the DOM"
- `onWillStart` for the initial async load; do not fetch in `setup()` directly

---

## 6. Templates

```xml
<t t-name="my_module.MyField">
    <div t-attf-class="o_my_field {{ this.props.readonly ? 'o_readonly' : '' }}">
        <span t-out="this.displayValue"/>
        <t t-foreach="this.items()" t-as="item" t-key="item.id">
            <button t-on-click="() => this.select(item)" t-out="item.name"/>
        </t>
        <input t-ref="this.inputRef" t-att-value="this.state.value"/>
        <t t-if="this.props.slots" t-call-slot="default"/>
        <MyChild prop="this.state.value" t-props="this.childProps"/>
    </div>
</t>
```

Non-negotiable in OWL 3 templates:

- **explicit `this.`** — `this.props.x`, `this.state.x`, `this.myGetter`
- `t-out`, never `t-esc`
- `computed`/`signal` values are **called**: `this.items()`
- `t-key` on every `t-foreach`
- `t-call-slot="name"` to render a slot, `t-set-slot="name"` to fill one
- `t-ref="this.someSignalRef"` — the ref is a signal, not a string name
- `t-custom-click="handler"` is an Odoo custom directive that also binds `auxclick`
  (middle-click) — [addons/web/static/src/env.js:47](../../../../addons/web/static/src/env.js#L47)

QWeb server-side templates follow the same `t-out` rule and additionally changed `t-call`
parameter passing — see `views.md`.

---

## 7. Services and registries

Unchanged in shape from v19:

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
this.notification = useService("notification");
```

Common categories: `services`, `actions`, `fields`, `view_widgets`, `systray`, `main_components`,
`formatters`, `parsers`, `command_provider`.

v20 also introduces **plugins** (`usePlugin`, `*_plugin.js` in core, e.g. `orm_plugin`,
`dialog_plugin`). Use a plugin only when you are extending a core feature that is already
plugin-based; otherwise a service is still the right unit.

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
- `web.assets_unit_tests` — hoot tests
- glob the directory; do not list files one by one unless order matters
- `('replace', old, new)`, `('remove', path)`, `('before', ref, path)` for surgical edits

---

## 9. Common patterns

```js
// ORM call
const records = await this.orm.searchRead("my.model", [["state", "=", "draft"]], ["name"]);

// notification
this.notification.add(_t("Saved"), { type: "success" });

// dialog
this.dialog.add(ConfirmationDialog, {
    body: _t("Delete this record?"),
    confirm: () => this.delete(),
});

// debounce
import { debounce } from "@web/core/utils/timing";
this.onSearch = debounce(this.search.bind(this), 300);

// translation
import { _t } from "@web/core/l10n/translation";
```

`_t()` marks a translatable string; never build it from concatenation.

---

## 10. Review checklist

- [ ] No `useState` / `reactive` — `proxy()` instead
- [ ] Legacy hooks imported from `@web/owl2/utils`, not `@odoo/owl`
- [ ] `computed` / `signal` values are called with `()` in JS **and** in templates
- [ ] `props = useProps(schema)` with `t.*` types; schema exported
- [ ] Every `t-foreach` has `t-key`
- [ ] `t-out` everywhere, no `t-esc`
- [ ] Explicit `this.` in every template expression
- [ ] Effects return their cleanup; no leaked listeners or timers
- [ ] Async loading in `onWillStart`, not in `setup()`
- [ ] User-facing strings wrapped in `_t()`
- [ ] Component shape matches the nearest core component you copied from
