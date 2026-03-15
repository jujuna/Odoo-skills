# OWL 2 & Frontend — Odoo 19+

## Table of Contents

1. [OWL 2 Overview](#1-owl-2-overview)
2. [Component Structure](#2-component-structure)
3. [Hooks](#3-hooks)
4. [Services](#4-services)
5. [Registries](#5-registries)
6. [QWeb Templates](#6-qweb-templates)
7. [Asset Bundling](#7-asset-bundling)
8. [Common Patterns](#8-common-patterns)
9. [Error Handling](#9-error-handling)
10. [Inter-Component Communication](#10-inter-component-communication)
11. [Lifecycle Deep-Dive](#11-lifecycle-deep-dive)
12. [Performance Patterns](#12-performance-patterns)
13. [Testing OWL Components](#13-testing-owl-components)

---

## 1. OWL 2 Overview

Odoo 19 uses **OWL 2** natively — no `owl="1"` attribute needed. OWL is Odoo's reactive
component framework (similar to React/Vue but XML-templated).

**Key differences from OWL 1:**
- No more `owl="1"` on templates
- Composition API with hooks (like React hooks / Vue 3 Composition)
- `useState`, `useRef`, `useEffect` patterns
- `setup()` replaces constructor logic
- Reactive state with fine-grained tracking

---

## 2. Component Structure

### Basic OWL 2 Component

```javascript
/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MyDashboard extends Component {
    /**
     * Dashboard component showing key metrics.
     *
     * @extends Component
     */
    static template = "my_module.MyDashboard";
    static props = {
        title: { type: String, optional: true },
    };

    setup() {
        /**
         * Initialize component state and services.
         * Called once when the component is created.
         */
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            records: [],
            loading: true,
            count: 0,
        });

        this.loadData();
    }

    async loadData() {
        /**
         * Fetch dashboard data from the server.
         */
        try {
            this.state.loading = true;
            const records = await this.orm.searchRead(
                "my.module.model",
                [["state", "=", "confirmed"]],
                ["name", "amount", "partner_id"],
                { limit: 20, order: "create_date desc" }
            );
            this.state.records = records;
            this.state.count = records.length;
        } catch (error) {
            this.notification.add(
                "Failed to load dashboard data",
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    onRecordClick(record) {
        /**
         * Navigate to the record's form view.
         *
         * @param {Object} record - The clicked record data.
         */
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "my.module.model",
            res_id: record.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}
```

### OWL 2 Template (XML)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="my_module.MyDashboard">
        <div class="o_my_dashboard">
            <div class="o_dashboard_header">
                <h2 t-esc="props.title or 'Dashboard'"/>
                <span class="badge bg-primary" t-esc="state.count"/>
            </div>

            <div t-if="state.loading" class="o_loading text-center p-4">
                <i class="fa fa-spinner fa-spin fa-2x"/>
            </div>

            <div t-else="" class="o_dashboard_content">
                <t t-foreach="state.records" t-as="record" t-key="record.id">
                    <div class="o_dashboard_card card mb-2"
                         t-on-click="() => this.onRecordClick(record)">
                        <div class="card-body">
                            <h5 class="card-title" t-esc="record.name"/>
                            <p class="card-text">
                                Amount: <t t-esc="record.amount"/>
                            </p>
                        </div>
                    </div>
                </t>

                <div t-if="!state.records.length" class="text-muted p-4 text-center">
                    No records found.
                </div>
            </div>
        </div>
    </t>
</templates>
```

---

## 3. Hooks

### Common OWL 2 Hooks

```javascript
import { useState, useRef, useEffect, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

setup() {
    // Reactive state
    this.state = useState({ count: 0, data: null });

    // DOM reference
    this.inputRef = useRef("myInput");

    // Services
    this.orm = useService("orm");
    this.rpc = useService("rpc");
    this.notification = useService("notification");
    this.action = useService("action");
    this.dialog = useService("dialog");
    this.user = useService("user");

    // Lifecycle: before first render (async allowed)
    onWillStart(async () => {
        this.state.data = await this.loadInitialData();
    });

    // Lifecycle: after DOM is mounted
    onMounted(() => {
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    });

    // Lifecycle: before unmount (cleanup)
    onWillUnmount(() => {
        // Clean up event listeners, intervals, etc.
    });

    // Reactive effect (re-runs when dependencies change)
    useEffect(
        () => {
            console.log("Count changed to:", this.state.count);
        },
        () => [this.state.count]
    );
}
```

---

## 4. Services

### Using Odoo Services

```javascript
// ORM service — for database operations
this.orm = useService("orm");
await this.orm.searchRead("res.partner", domain, fields, options);
await this.orm.read("res.partner", [id], fields);
await this.orm.create("res.partner", values);
await this.orm.write("res.partner", [id], values);
await this.orm.unlink("res.partner", [id]);
await this.orm.call("res.partner", "method_name", args, kwargs);

// Action service — for navigation
this.action = useService("action");
this.action.doAction("my_module.my_action_id");
this.action.doAction({
    type: "ir.actions.act_window",
    res_model: "res.partner",
    views: [[false, "list"], [false, "form"]],
    domain: [["is_company", "=", true]],
});

// Notification service
this.notification = useService("notification");
this.notification.add("Record saved!", { type: "success", sticky: false });

// Dialog service
this.dialog = useService("dialog");

// User service
this.user = useService("user");
const isAdmin = this.user.isAdmin;
const userId = this.user.userId;

// RPC service (low-level)
this.rpc = useService("rpc");
const result = await this.rpc("/my_module/endpoint", { param: "value" });
```

---

## 5. Registries

### Registering Components

```javascript
import { registry } from "@web/core/registry";

// Register as a client action (accessible via menu/action)
registry.category("actions").add("my_module.my_dashboard", MyDashboard);

// Register as a systray item (top-right icons)
registry.category("systray").add("my_module.MySystrayItem", {
    Component: MySystrayItem,
    isDisplayed: (env) => true,
}, { sequence: 100 });

// Register as a field widget
registry.category("fields").add("my_custom_widget", {
    component: MyCustomField,
    supportedTypes: ["char", "text"],
});

// Register a service
registry.category("services").add("myService", {
    dependencies: ["orm", "notification"],
    start(env, { orm, notification }) {
        return {
            async doSomething() { /* ... */ },
        };
    },
});
```

### Client Action in XML

```xml
<record id="my_dashboard_action" model="ir.actions.client">
    <field name="name">My Dashboard</field>
    <field name="tag">my_module.my_dashboard</field>
</record>
```

---

## 6. QWeb Templates

### QWeb Directives Cheat Sheet

| Directive | Purpose | Example |
|-----------|---------|---------|
| `t-esc` | Output escaped text | `<span t-esc="record.name"/>` |
| `t-out` | Output raw HTML (careful!) | `<div t-out="record.html_field"/>` |
| `t-if` / `t-elif` / `t-else` | Conditional rendering | `<div t-if="state.loading">...` |
| `t-foreach` / `t-as` / `t-key` | Loop iteration | `<t t-foreach="items" t-as="item" t-key="item.id">` |
| `t-att-*` | Dynamic attribute | `<div t-att-class="state.active ? 'active' : ''"/>` |
| `t-on-*` | Event handler | `<button t-on-click="onSave"/>` |
| `t-ref` | DOM reference | `<input t-ref="myInput"/>` |
| `t-component` | Render sub-component | `<t t-component="ChildComponent" data="props"/>` |
| `t-slot` | Define slot content | `<t t-slot="default"/>` |
| `t-set` / `t-value` | Variable assignment | `<t t-set="total" t-value="a + b"/>` |
| `t-call` | Include sub-template | `<t t-call="my_module.sub_template"/>` |

**Security note:** NEVER use `t-out` with user-provided content — XSS risk. Always use `t-esc`.

---

## 7. Asset Bundling

### In __manifest__.py

```python
'assets': {
    'web.assets_backend': [
        # JS components
        'my_module/static/src/components/**/*.js',
        'my_module/static/src/components/**/*.xml',
        # SCSS styles
        'my_module/static/src/scss/**/*.scss',
    ],
    'web.assets_frontend': [
        # For website/portal components
        'my_module/static/src/public/**/*.js',
    ],
},
```

### File Organization

```
static/src/
├── components/
│   ├── my_dashboard/
│   │   ├── my_dashboard.js
│   │   ├── my_dashboard.xml
│   │   └── my_dashboard.scss
│   └── my_widget/
│       ├── my_widget.js
│       └── my_widget.xml
├── js/
│   └── services/
│       └── my_service.js
└── scss/
    └── my_module.scss
```

---

## 8. Common Patterns

### Form View Widget (Custom Field)

```javascript
/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ColorPickerField extends Component {
    /**
     * Custom color picker field widget.
     * Renders a color input and syncs with the record field.
     */
    static template = "my_module.ColorPickerField";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({
            color: this.props.record.data[this.props.name] || "#000000",
        });
    }

    onColorChange(ev) {
        /**
         * Handle color change and update the record.
         *
         * @param {Event} ev - Input change event.
         */
        const color = ev.target.value;
        this.state.color = color;
        this.props.record.update({ [this.props.name]: color });
    }
}

ColorPickerField.template = "my_module.ColorPickerField";

registry.category("fields").add("color_picker", {
    component: ColorPickerField,
    supportedTypes: ["char"],
});
```

### Extending Existing Views

```javascript
/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    /**
     * Extend form controller to add custom save logic.
     */
    async onRecordSaved(record) {
        await super.onRecordSaved(record);
        // Custom post-save logic
        if (record.resModel === "my.module.model") {
            this.notification.add("Custom save completed!", { type: "info" });
        }
    },
});
```

### Debounced Search Input

```javascript
import { debounce } from "@web/core/utils/timing";

setup() {
    this.state = useState({ searchTerm: "", results: [] });
    this.orm = useService("orm");

    // Debounced search — avoids flooding the server
    this._debouncedSearch = debounce(this._performSearch.bind(this), 300);
}

onSearchInput(ev) {
    this.state.searchTerm = ev.target.value;
    this._debouncedSearch();
}

async _performSearch() {
    /**
     * Execute search query after debounce delay.
     */
    if (this.state.searchTerm.length < 2) {
        this.state.results = [];
        return;
    }
    this.state.results = await this.orm.searchRead(
        "res.partner",
        [["name", "ilike", this.state.searchTerm]],
        ["name", "email"],
        { limit: 10 }
    );
}
```

---

## 9. Error Handling

### Try/catch with user notification:
```javascript
async onSave() {
    try {
        await this.orm.write("my.model", [this.recordId], this.getValues());
        this.notification.add("Record saved successfully!", { type: "success" });
    } catch (error) {
        // Odoo RPC errors have a specific structure
        if (error.data && error.data.message) {
            this.notification.add(error.data.message, { type: "danger", sticky: true });
        } else {
            this.notification.add("An unexpected error occurred.", { type: "danger" });
        }
    }
}
```

### Error boundary component:
```javascript
import { Component, onError, useState } from "@odoo/owl";

export class ErrorBoundary extends Component {
    static template = "my_module.ErrorBoundary";
    static props = { slots: { type: Object } };

    setup() {
        this.state = useState({ hasError: false, error: null });
        // OWL 2 error handling via onError hook
        onError((error) => {
            this.state.hasError = true;
            this.state.error = error.message || "Unknown error";
            console.error("[ErrorBoundary]", error);
        });
    }
}
```

```xml
<t t-name="my_module.ErrorBoundary">
    <div t-if="state.hasError" class="alert alert-danger m-3">
        <i class="fa fa-exclamation-triangle"/> Something went wrong.
        <small class="d-block mt-1" t-esc="state.error"/>
    </div>
    <t t-else="" t-slot="default"/>
</t>
```

---

## 10. Inter-Component Communication

### Using the bus service (EventBus):
```javascript
import { useBus } from "@web/core/utils/hooks";

setup() {
    // Listen for events from other components
    useBus(this.env.bus, "my-custom-event", (ev) => {
        this.onCustomEvent(ev.detail);
    });
}

// In another component, trigger the event:
this.env.bus.trigger("my-custom-event", { recordId: 42 });
```

### Parent-child communication:
```javascript
// Parent passes callback as prop:
// <ChildComponent onSelect.bind="onChildSelect"/>

// Child calls the callback:
this.props.onSelect(selectedData);
```

### Using a custom service for shared state:
```javascript
registry.category("services").add("mySharedState", {
    start() {
        let data = {};
        return {
            getData: () => data,
            setData: (key, value) => { data[key] = value; },
        };
    },
});

// In components:
this.sharedState = useService("mySharedState");
const value = this.sharedState.getData();
```

---

## 11. Lifecycle Deep-Dive

```
Component Creation:
  setup()                  → Initialize hooks, state, services
  onWillStart() [async]    → Fetch data before first render
  [first render]
  onMounted()              → DOM is available, attach listeners

Props/State Change:
  onWillUpdateProps()      → New props incoming (before re-render)
  [re-render]
  onPatched()              → DOM updated after re-render

Destruction:
  onWillUnmount()          → Cleanup before DOM removal
  [destroy]
```

### Key hooks:

```javascript
import { onWillStart, onMounted, onWillUnmount, onPatched, onWillUpdateProps } from "@odoo/owl";

setup() {
    onWillStart(async () => {
        // Async data loading before first render
        // Component is NOT in DOM yet
    });

    onMounted(() => {
        // DOM is ready. Safe to use this.myRef.el
        // Set up DOM listeners, third-party libraries
    });

    onPatched(() => {
        // DOM was re-rendered after state/props change
        // Good for: scrolling, canvas redraw, third-party lib update
    });

    onWillUpdateProps((nextProps) => {
        // New props are about to be applied
        // Good for: loading data based on new props
        if (nextProps.recordId !== this.props.recordId) {
            this.loadRecord(nextProps.recordId);
        }
    });

    onWillUnmount(() => {
        // CRITICAL: Clean up here
        // Remove event listeners, destroy third-party instances,
        // cancel pending RPCs, disconnect observers
    });
}
```

---

## 12. Performance Patterns

### Avoid unnecessary re-renders:
```javascript
// BAD — creates a new object every render, causing child re-render
get childProps() {
    return { items: this.state.items.filter(i => i.active) };
}

// GOOD — use useState for derived state that changes rarely
setup() {
    this.state = useState({ items: [] });
    this.filteredItems = useState({ value: [] });

    useEffect(
        () => {
            this.filteredItems.value = this.state.items.filter(i => i.active);
        },
        () => [this.state.items]
    );
}
```

### Lazy-load heavy components:
```javascript
// Only load the component when needed (e.g., when a tab is clicked)
import { Component, xml, useState } from "@odoo/owl";

export class LazyTabContent extends Component {
    static template = xml`
        <div t-if="state.loaded">
            <HeavyComponent data="state.data"/>
        </div>
        <div t-else="" t-on-click="load" class="btn btn-link">
            Click to load...
        </div>
    `;

    setup() {
        this.state = useState({ loaded: false, data: null });
    }

    async load() {
        this.state.data = await this.loadData();
        this.state.loaded = true;
    }
}
```

### Cleanup resources in onWillUnmount:
```javascript
setup() {
    this._interval = null;

    onMounted(() => {
        this._interval = setInterval(() => this.refresh(), 30000);
    });

    onWillUnmount(() => {
        // ALWAYS clean up intervals, observers, event listeners
        if (this._interval) {
            clearInterval(this._interval);
            this._interval = null;
        }
    });
}
```

---

## 13. Testing OWL Components

### Basic component test pattern:
```javascript
/** @odoo-module */

import { mountComponent } from "@web/../tests/web_test_helpers";
import { MyComponent } from "@my_module/components/my_component";

QUnit.module("MyComponent", (hooks) => {
    QUnit.test("renders correctly with initial data", async (assert) => {
        const component = await mountComponent(MyComponent, {
            props: {
                title: "Test Title",
            },
        });

        assert.containsOnce(component, ".o_my_component");
        assert.strictEqual(
            component.el.querySelector("h2").textContent,
            "Test Title"
        );
    });

    QUnit.test("handles click event", async (assert) => {
        const component = await mountComponent(MyComponent, {
            props: {
                onSelect: (value) => {
                    assert.step(`selected:${value}`);
                },
            },
        });

        await click(component.el.querySelector(".o_select_btn"));
        assert.verifySteps(["selected:expected_value"]);
    });
});
```
