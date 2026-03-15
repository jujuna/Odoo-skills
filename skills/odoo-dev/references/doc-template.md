# Documentation Template — Odoo Business Module

Use this exact structure for every module documentation file.
Replace all `<placeholders>` with real content. Delete sections that genuinely don't apply.
Every code reference MUST be a markdown link to an actual file you read.

The documentation serves two audiences simultaneously:
1. **Business learner** — someone learning Odoo flows, wanting to understand when/how/why to use features
2. **Technical developer** — someone who needs code references, field definitions, and method details

Front-load business context before technical details. Every feature should answer: "When would I use this? What problem does it solve? Show me a real example."

---

```markdown
# <Module Name>

> **Module:** `<technical_module_name>` | **Path:** [`<addons/module_name>/`](<addons/module_name>/)
> **Odoo Apps category:** <Sales / Inventory / Accounting / HR / ...>

## What It Does

<3–5 sentences. Focus on business purpose: what problem it solves, who uses it, what the output is.
No vague statements. Be specific about the business outcome.>

---

## When to Use This Module

<Answer clearly: What business need triggers the use of this module? Who benefits from it (which roles/departments)?
Compare briefly with alternative approaches if relevant — e.g., "Use X for simple cases, this module for Y.">

### Best For
- <Scenario 1 — concrete business situation where this module is the right choice>
- <Scenario 2>

### Not For
- <Scenario where a different module or approach is better — and which one>

---

## Real-World Use Cases

<Concrete, named scenarios that show how real businesses use this module. Each use case should have:
a situation, what the user does in Odoo, and what the outcome is.>

### Use Case 1: <Descriptive Name>
**Situation:** <Who has what problem? Be specific — role, company type, context.>
**In Odoo:** <Step-by-step what they do — menu paths, buttons, fields they fill.>
**Result:** <What business outcome they get — reports, documents, automation.>

### Use Case 2: <Descriptive Name>
**Situation:** <...>
**In Odoo:** <...>
**Result:** <...>

<Add as many use cases as needed to cover the module's main features. Each major feature should appear in at least one use case.>

---

## How-To Scenarios

<Practical "I want to do X, how?" guides. These are task-oriented — the reader has a goal and needs steps.
Each scenario should be self-contained and actionable.>

### How to <accomplish task 1>
1. <Step with exact menu path or button name>
2. <Step — mention which fields to fill and why>
3. <Step — what happens after, what to verify>

**Why this works:** <Brief explanation of what Odoo does behind the scenes — connect to the technical model/method if relevant.>

### How to <accomplish task 2>
1. <...>

<Cover the most common tasks users need to perform with this module.>

---

## Dependencies

### Requires (must be installed)
| Module | Why |
|---|---|
| `<module>` | <reason — e.g., "provides res.partner, used for customer records"> |

### Optional Integrations
| Module | What it enables |
|---|---|
| `<module>` | <e.g., "enables invoice generation from orders"> |

### Provides To (what other modules consume from this one)
| Consumers | What they use |
|---|---|
| `<module>` | <e.g., "reads stock.move for COGS journal entries"> |

---

## Business Flow

> The end-to-end process from user action to business outcome.

```
<State/Step 1>  →  <State/Step 2>  →  <State/Step 3>  →  <Final State>
     ↓                   ↓                   ↓
<What happens>    <What happens>    <What happens>
```

### States (if stateful)
| State | Meaning | Can Transition To |
|---|---|---|
| `draft` | <meaning> | `confirmed`, `cancelled` |

### Key Triggers
- **<User action / button>** → calls `<method>()` → <what happens>
- **<Scheduled action>** → triggers `<method>()` → <what happens>

---

## Key Models

### `<model.name>` — <short description>
> [`<models/filename.py>`](<addons/module/models/filename.py>)

| Field | Type | Purpose |
|---|---|---|
| `<field_name>` | `<Many2one / Char / Selection / ...>` | <what it stores or computes> |

**Computed fields:**
- `<field>` — computed by [`<method>()`](<path/file.py#Lnn>) — <what it calculates and when>

**Constraints:**
- `<_check_something>` — <what it enforces>

---

## Key Methods

| Method | File:Line | Purpose |
|---|---|---|
| `<method_name>()` | [`<file.py:nn>`](<path/file.py#Lnn>) | <what it does in one sentence> |

### <method_name>() — detailed
> [`<file.py:nn–mm>`](<path/file.py#Lnn>)

<Explain the logic: inputs, what it changes, side effects, what it calls next.>

---

## UI Entry Points

| Entry Point | Path in UI | What It Does |
|---|---|---|
| <Menu item> | <Top Menu → Sub Menu → Page> | <what the user does here> |
| <Button / Action> | <Form view / List view> | <what it triggers> |
| <Wizard> | <where it appears> | <what it collects / does> |

---

## Configuration

| Setting | Location | Effect |
|---|---|---|
| `<setting_name>` | Settings → <section> | <what changes when enabled> |
| `<security group>` | — | <what access it grants> |

---

## Edge Cases & Gotchas

- **<Topic>:** <Non-obvious behavior. Be specific. Include file reference if relevant.>
- **<Topic>:** <Constraint or limit that surprises people.>
- **<Topic>:** <Integration behavior that's easy to miss.>

---

## Related Docs

- [`INDEX.md`](INDEX.md)
- [`<other-module>.md`](<other-module>.md) — <why it's related>
```

---

## Writing Rules (enforced)

1. **No fact without a source.** If you cannot link to a file you actually read, do not write the sentence.
2. **No vague language.** Not "handles various cases" — say what cases.
3. **Code links are mandatory** for: models, methods, fields, views, wizards.
4. **Business flow diagram is mandatory** for any stateful process.
5. **Dependencies table is mandatory** — always identify what is needed and what is produced.
6. **Short sentences.** One idea per sentence. No padding.
7. **Tables over prose** for structured data (fields, states, settings).
8. **Update INDEX.md** when you create or update a module doc.
9. **Every feature needs a use case.** Don't just describe what a feature does technically — show when and why a real user would use it.
10. **Use cases must be concrete.** Name roles ("warehouse manager"), company types ("e-commerce company"), and specific situations ("end-of-month inventory count") — not abstract descriptions.
11. **How-to scenarios are task-oriented.** Start with the user's goal, give exact steps (menu paths, button names, field values), explain what happens behind the scenes.
12. **Connect business to technical.** In use cases and how-tos, link back to the relevant method/model when explaining "why this works" — this bridges the two audiences.

## Research Rules (enforced — must run before writing)

### Rule R1 — Link paths
All links in `documentations/*.md` MUST use `../` prefix for source paths.
- Correct: `[stock_quant.py:42](../addons/stock/models/stock_quant.py#L42)`
- Wrong: `[stock_quant.py:42](addons/stock/models/stock_quant.py#L42)`

### Rule R2 — Always check settings (mandatory)
Before documenting any configuration option or behavior gated by a setting:
1. Read `addons/<module>/models/res_config_settings.py` (or the module that extends it).
2. Find the exact field name, type, and `implied_group` / `config_parameter` it sets.
3. Document: field technical name, UI label (`string=`), implied group or config key, and what behavior it enables.

Skipping this step leads to wrong or missing configuration docs. It is the #1 source of errors.

### Rule R3 — Document both technical name and UI label
For every field documented, include both:
- Technical name: `delivery_steps` (Python field name)
- UI label: "Outgoing Shipments" (`string=` value from field definition or view `string=` override)

Find the UI label from the Python field `string=` argument. Only read the specific view XML if the label differs or visibility is unclear.

### Rule R4 — Document visibility conditions for settings
When a setting or field is controlled by a security group or another setting:
1. Note the `groups=` condition.
2. State in the docs: "Only visible when [Setting Name] is enabled" — with the implied group name.
3. Read ONLY the specific view element containing the field, not the entire view file.

### Rule R5 — Selection fields with 2+ values need examples
For any `Selection` field that controls a business process (e.g., `delivery_steps`, `reception_steps`, `invoice_policy`):
- Each value gets its own subsection.
- Each subsection must include: "When to use", "What Odoo creates", step-by-step flow.
- Get exact operation type names and sequence codes from `_get_picking_type_create_values()` or equivalent — not from assumptions.

### Rule R6 — Use cases must reflect real module capabilities
When writing use cases and how-to scenarios:
1. Base them on actual features found in the source code — not on assumptions about what the module "should" do.
2. Include exact UI paths (menu → submenu → button) verified from view XML or menu records.
3. Each major feature of the module must appear in at least one use case or how-to.
4. Connect each use case back to the technical implementation: "This works because `method_name()` does X" with a code link.

### Rule R7 — Business context before technical depth
Structure each documentation file so a reader can understand the business value without reading the technical sections:
1. "What It Does", "When to Use", "Real-World Use Cases", and "How-To Scenarios" must be self-sufficient — no forward references to Key Models or Key Methods required to understand them.
2. Technical sections (Key Models, Key Methods) come after and provide the "proof" and implementation details.
3. How-to scenarios bridge the two: steps are business-language, "Why this works" connects to technical.
