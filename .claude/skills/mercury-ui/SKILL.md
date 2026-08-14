---
name: mercury-ui
description: The house UI skill. Mercury design tokens (dark, electric-blue accent, Geist, strictly flat, pill interactives) fused with the anti-slop build process - brief inference, three dials, layout discipline, AI-tell bans, redesign audit, and a mandatory pre-flight check. Use for every design task, whether building new screens and pages or redesigning existing ones.
disable-model-invocation: true
packages:
  - name: "@fontsource-variable/geist"
    purpose: Self-hosted Geist variable sans - the brand typeface
    kind: dependency
    curated: true
  - name: "@fontsource-variable/geist-mono"
    purpose: Self-hosted Geist Mono variable - tabular figures only
    kind: dependency
    curated: true
  - name: clsx
    purpose: Tiny utility for conditionally joining class names
    kind: dependency
    curated: true
  - name: tailwind-merge
    purpose: Merge Tailwind classes without style conflicts (Tailwind projects only)
    kind: dependency
    curated: true
  - name: class-variance-authority
    purpose: Type-safe component style variants (CVA)
    kind: dependency
    curated: true
---

# Mercury UI

> The design system is Mercury. The build process is anti-slop. This file is both.
> **Precedence: Mercury wins on surface, process wins on structure.** Where a process rule below would pick a color, a typeface, a radius, a shadow, or a theme, it has already been deleted or rewritten - Section 1 is the only source for those. Where Mercury is silent (page structure, hero composition, motion mechanics, content discipline, QA), the process rules govern.

---

## 0. READ THE ROOM (before any code)

### 0.A Signals to read first
1. **Surface kind** - app screen (dashboard, table, form, flow step), marketing page (landing, pricing, about), or system surface (empty state, error, email).
2. **Mode** - new build, modification of an existing screen, or full re-skin. See Section 11.
3. **Audience** - the person using it decides the density, not your taste. A finance operator scanning 200 invoices needs different density from a first-time visitor.
4. **Reference signals** - URLs, screenshots, products named, existing screens in the repo.
5. **Quiet constraints** - accessibility, regulated content, legal copy, analytics dependencies. These OVERRIDE aesthetic preference.

### 0.B Output a one-line Design Read before generating
State in one line: **"Reading this as: \<surface kind> for \<audience>, \<mode>, at dials \<V/M/D>."**

Examples:
- *"Reading this as: invoice table screen for a finance operator, modification of an existing screen, at dials 5/3/6."*
- *"Reading this as: share-link landing for an external recipient, new build, at dials 6/3/4."*

### 0.C If the brief is ambiguous, ask ONE question
Never a multi-question dump. Ask only when the read genuinely diverges. If you can infer from the repo or the conversation, do not ask - declare the read and proceed.

### 0.D Delivery Target (declare this before Section 3)
Two targets, and they are orthogonal to the mode in Section 8. Everything in Sections 1, 2, 4, 7 and 8 applies identically to both. Sections 3, 5 and 6 are the ones that differ, and each rule there is tagged.

* **DRAFT** - a self-contained artifact for looking at and deciding on: a static HTML screen, a generated flow under `docs/flows/`, an inline preview. No npm, no bundler, no component framework, often no JavaScript at all. The deliverable is the rendered screen, not shippable app code.
* **PRODUCTION** - code that lands in the running app. Framework, bundler, and dependency graph are whatever the host project already uses.

**Draft is not a lower standard.** Tokens, layout discipline, content rules, AI-tell bans, and the visual half of the pre-flight check apply in full. What changes is the delivery mechanism, and a draft that quietly invents a different palette or a looser type scale has failed at the thing drafts exist to test.

State the target in the Design Read: *"...at dials 5/3/6, DRAFT."*

### 0.E Anti-Default Discipline
Do not reach for: centered hero over a dark mesh, three equal feature cards, infinite-loop micro-animations, div-based fake product screenshots, generic glassmorphism. These are the LLM defaults. The Mercury tokens will not save a templated layout.

---

## 1. MERCURY TOKENS (authoritative - nothing below overrides this section)

```yaml
brand: Mercury
mood: A sophisticated, modern, and trustworthy atmosphere designed for ambitious tech startups and scaling companies.
scheme: dark

colors:
  primary: "#5266eb"
  primary-bright: "#7483ef"
  primary-deep: "#3c4dc5"
  on-primary: "#ffffff"
  ink: "#fbfcfd"
  ink-soft: "#c3c3cc"
  on-ink: "#1e1e2a"
  canvas: "#1e1e2a"
  canvas-deep: "#171721"
  paper: "#272735"
  cloud: "#f4f5f9"
  hairline: "#272735"
  hairline-strong: "#70707d"
  link: "#ededf3"
  link-pressed: "#c3c3cc"
  accent-pale-blue: "#cdddff"

fonts:
  sans: '"Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
  mono: '"Geist Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'
  loading: "@fontsource-variable/geist + @fontsource-variable/geist-mono. Self-host; never <link> to fonts.googleapis in production."

typography:
  display-xl: { fontFamily: "{fonts.sans}", fontSize: 65px, fontWeight: 500, lineHeight: 1.1, letterSpacing: -0.03em }
  display-lg: { fontFamily: "{fonts.sans}", fontSize: 49px, fontWeight: 500, lineHeight: 1.2, letterSpacing: -0.025em }
  display-md: { fontFamily: "{fonts.sans}", fontSize: 42px, fontWeight: 500, lineHeight: 1.2, letterSpacing: -0.02em }
  body-xl: { fontFamily: "{fonts.sans}", fontSize: 24px, fontWeight: 400, lineHeight: 1.4, letterSpacing: -0.01em }
  body-lg: { fontFamily: "{fonts.sans}", fontSize: 18px, fontWeight: 400, lineHeight: 1.5, letterSpacing: 0 }
  body-md: { fontFamily: "{fonts.sans}", fontSize: 16px, fontWeight: 400, lineHeight: 1.5, letterSpacing: 0 }
  body-sm: { fontFamily: "{fonts.sans}", fontSize: 14px, fontWeight: 400, lineHeight: 1.5, letterSpacing: 0 }
  button-md: { fontFamily: "{fonts.sans}", fontSize: 16px, fontWeight: 500, lineHeight: 1, letterSpacing: 0 }
  caption-md: { fontFamily: "{fonts.sans}", fontSize: 12px, fontWeight: 400, lineHeight: 1.5, letterSpacing: 0 }
  link-md: { fontFamily: "{fonts.sans}", fontSize: 16px, fontWeight: 400, lineHeight: 1.5, letterSpacing: 0 }
  numeric-md: { fontFamily: "{fonts.mono}", fontSize: 16px, fontWeight: 400, lineHeight: 1.5, fontVariantNumeric: "tabular-nums" }
  numeric-sm: { fontFamily: "{fonts.mono}", fontSize: 14px, fontWeight: 400, lineHeight: 1.5, fontVariantNumeric: "tabular-nums" }

rounded:
  none: 0px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 32px
  pill: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 72px

shadows:
  none: "none"
  soft-lift: "none"
  card: "none"
  modal: "none"

motion:
  duration-fast: "150ms"
  duration-base: "300ms"
  duration-slow: "500ms"
  ease-standard: "cubic-bezier(0.4, 0, 0.2, 1)"
  ease-emphasized: "cubic-bezier(0.65, 0.05, 0.36, 1)"
  transition-default: "all {motion.duration-base} {motion.ease-standard}"

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    color: "{colors.on-primary}"
    rounded: "{rounded.pill}"
    padding: "{spacing.sm} {spacing.lg}"
    typography: "{typography.button-md}"
    cursor: "pointer"
    border: "1px solid transparent"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
  button-secondary:
    backgroundColor: "{colors.accent-pale-blue}"
    color: "{colors.primary-deep}"
    rounded: "{rounded.pill}"
    padding: "{spacing.sm} {spacing.lg}"
    typography: "{typography.button-md}"
    cursor: "pointer"
    border: "1px solid transparent"
  button-secondary-hover:
    backgroundColor: "{colors.on-primary}"
  input-text:
    backgroundColor: "rgba(39, 39, 53, 0.5)" # paper, with transparency
    color: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "{spacing.sm} {spacing.lg}"
    typography: "{typography.body-md}"
    border: "1px solid transparent"
    cursor: "text"
  input-text-focus:
    border: "1px solid {colors.primary}"
    boxShadow: "{shadows.none}"
  nav-link:
    color: "{colors.link}"
    typography: "{typography.link-md}"
    padding: "{spacing.xs} {spacing.md}"
    rounded: "{rounded.sm}"
    cursor: "pointer"
  nav-link-hover:
    color: "{colors.ink}"
    backgroundColor: "{colors.paper}"
  card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
    shadow: "{shadows.none}"
    border: "1px solid {colors.hairline}"
```

### 1.A Token Wiring (do this before writing components)
Land the tokens ONCE as CSS custom properties, then build against variables. Retyping hex values into components is how a system drifts by the third screen.

* **Any project:** `:root { --canvas: #1e1e2a; --paper: #272735; ... --space-lg: 24px; --r-pill: 9999px; --font: ...; }` in a single tokens file. Components reference `var(--paper)`, never `#272735`.
* **Tailwind v4 projects:** the same values in an `@theme` block so utilities generate from them.
* **Never** inline a raw hex, a raw px spacing value, or a font stack in a component. If a value you need has no token, pick the nearest token - do not invent one.
* **Exception, transactional email.** Email clients do not support custom properties, and many strip `<style>` blocks entirely, so email inlines literal values as `style` attributes. That is the one place raw hex is correct. Keep the literals in one template with a comment pointing back to this section, and never let email values drift from the tokens above.

### 1.B Status Colors (local extension, not Mercury brand tokens)
Section 1 ships no success, warning, or danger token, but Section 4.5 requires error states and Section 4.2 bans inventing colors. Resolve it here rather than improvising per screen:

* **Error / destructive** is the only status color the system genuinely needs. Define exactly one, once, in the tokens file as `--danger`, and one `--danger-soft` for its low-emphasis background. Pick a red that holds WCAG AA against `{colors.canvas}` and `{colors.paper}`.
* **Success needs no color.** Confirmation is carried by copy and by the absence of an error, not by a green badge on every saved field. This matches the restraint in Section 4.10 about exclamation marks.
* **Warning needs no color** in a product with two real states. If a screen genuinely has three, say so explicitly and add `--warning` the same way.
* Status colors are **never** decorative and never appear outside an actual error or destructive-action context. `{colors.primary}` remains the only accent.
* Record the chosen values in the project tokens file, not here. This section states the rule; the project states the hex.

---

## 2. THE THREE DIALS

Set three dials after the design read. Layout, motion, and density decisions below are gated by these. Overrides happen conversationally; do not ask the user to edit this file.

* **`DESIGN_VARIANCE`** - 1 = perfect symmetry, 10 = artsy chaos
* **`MOTION_INTENSITY`** - 1 = static, 10 = cinematic. **Hard ceiling of 4 in this system** (Section 1's motion scale tops out at 500ms and calls motion restrained). A brief that genuinely needs 7 is a brief for a different design system.
* **`VISUAL_DENSITY`** - 1 = art gallery, 10 = cockpit

### 2.A Presets
| Surface | VARIANCE | MOTION | DENSITY |
|---|---|---|---|
| Dashboard / data table / list view | 4-5 | 2-3 | 6-7 |
| Form, flow step, settings | 4-5 | 3 | 4-5 |
| Empty / loading / error state | 4 | 2 | 3 |
| Marketing or landing page | 6-7 | 3-4 | 3-4 |
| Share / recipient-facing page | 5-6 | 3 | 4 |
| Transactional email | 2 | 1 | 4 |
| Redesign - preserve | match existing | match, +1 max | match existing |
| Redesign - overhaul | +2 | +1 | match existing |

Use these exact variable names in cross-references. Never invent aliases like `LAYOUT_VARIANCE`.

### 2.B Dial Definitions
**DESIGN_VARIANCE**
* **1-3** Symmetrical grid, equal padding, centered alignment.
* **4-7** Offset overlaps, varied aspect ratios, left-aligned headers over centered data.
* **8-10** Masonry, fractional grid units (`2fr 1fr 1fr`), large deliberate empty zones.
* **MOBILE OVERRIDE:** at 4-10, asymmetric layouts above `md:` MUST collapse to strict single column below 768px.

**MOTION_INTENSITY** (capped at 4 here)
* **1-2** No automatic animation. `:hover` / `:active` / `:focus` only.
* **3** Add `{motion.transition-default}` on interactive state changes; entry fades on route or view change.
* **4** Adds scroll-reveal stagger on first paint of long pages. Nothing pins, nothing hijacks scroll.

**VISUAL_DENSITY**
* **1-3** Section gaps at `{spacing.section}`, generous internal padding at `{spacing.xl}`+.
* **4-7** Standard product spacing: `{spacing.lg}` internal, `{spacing.xxl}` between blocks.
* **8-10** Tight. Card containers dropped in favor of `1px {colors.hairline}` rules. `{typography.numeric-*}` mandatory for every figure.

---

## 3. ARCHITECTURE & CONVENTIONS

**This whole section is delivery-target dependent (Section 0.D).** Rules are tagged `[PRODUCTION]`, `[DRAFT]`, or untagged for both. Applying a `[PRODUCTION]` rule to a draft is a category error, not diligence.

### 3.A Stack
* **Framework:** match the host project. Do not migrate frameworks to satisfy this skill. `[DRAFT]` there is no framework - plain HTML, or whatever generator already produces the artifact.
* **Styling:** CSS custom properties are the baseline strategy for both targets (Section 1.A). `[PRODUCTION]` Tailwind v4 only where the project already uses it - use `@tailwindcss/postcss` or the Vite plugin, never the `tailwindcss` PostCSS plugin.
* **Animation:** CSS transitions cover everything up to `MOTION_INTENSITY: 3` on both targets. `[PRODUCTION]` reach for Motion (`import { motion } from "motion/react"`) only at 4, and only for scroll-reveal. `[DRAFT]` use the CSS scroll-reveal in Section 5.A2, or ship it static.
* **Fonts:** `[PRODUCTION]` self-host via `@fontsource-variable/geist` (or `next/font` on Next.js). Never `<link>` to Google Fonts in production - a page that stalls on `fonts.gstatic` is a broken page. `[DRAFT]` a Google Fonts `@import` is acceptable and usually correct, since a draft has no build step; leave a comment naming the fontsource package the production version should use.
* **RSC safety:** `[PRODUCTION]` global state and any motion/pointer/scroll code lives in `'use client'` leaf components. Server components render static layout only.

### 3.B State `[PRODUCTION]`
* Local `useState` / `useReducer` for isolated UI. Global state only to avoid deep prop drilling.
* **NEVER** use `useState` for continuous input-driven values (scroll progress, pointer position). Use motion values. `useState` re-renders the tree every frame and collapses on mobile.

`[DRAFT]` there is no state. A flow is expressed as one file per state, linked to each other, which is a feature: every state gets designed instead of only the happy path.

### 3.C Icons
One set, one grid, one stroke width, across every screen of the project. How you get there depends on the target.

* `[PRODUCTION]` **Allowed libraries (priority order):** `@phosphor-icons/react`, `hugeicons-react`, `@radix-ui/react-icons`, `@tabler/icons-react`. **Discouraged:** `lucide-react` - the default AI icon choice, acceptable only on explicit request or when already a dependency. Do not hand-roll paths when a library is available: a missing glyph means installing a second library, not drawing from scratch.
* `[DRAFT]` **inline SVG is the only option and is correct.** A static file has no npm. Hand-rolled paths here are required, not a violation. The discipline that replaces the library guarantee:
  - One viewBox for the whole set (`0 0 24 24`), with the drawing confined to a consistent live area inside it.
  - One `stroke-width` for every icon, one join and cap style, `fill="none"` and `stroke="currentColor"` so icons inherit `{colors.ink}` / `{colors.ink-soft}`.
  - Emit them from a single helper in the generator, never pasted per-use, so the set cannot drift.
  - `aria-hidden="true"` on decorative icons; a real label on meaningful ones.
* **Both targets:** one family per project, never two. Replace cliche metaphors - not a rocketship for "launch", not a shield for "security". An icon that is not the obvious metaphor still has to be recognisable; unusual is not the goal, unthinking is the thing being avoided.
* **Neither target** hand-rolls decorative illustration. The rule above is about icons, which are a system; illustrations are not (Section 4.9).

### 3.D Emoji
Not in code, markup, or visible text. Use icon glyphs.

### 3.E Responsive Mechanics
Mercury breakpoints, with Tailwind equivalents:

| Band | Range | Behavior |
|---|---|---|
| Mobile | <480px | Single column. Nav collapses to hamburger. `{typography.display-xl}` scales down hard. |
| Mobile-Large | 480-767px | Still single column, larger type and spacing. |
| Tablet | 768-1023px (`md` 768) | Two-column grids appear. Nav may stay collapsed. Touch targets stay priority. |
| Desktop | 1024-1279px (`lg` 1024) | Nav fully visible horizontally. Content constrained to a max width. |
| Desktop-Large | >=1280px (`xl` 1280) | Layout stays centered with generous side margins. No new layout. |

Mercury's 480px band has **no Tailwind equivalent** - Tailwind's `sm` is 640px, which falls inside the Mobile-Large band rather than starting it. On a Tailwind project either add a `xs: 480px` screen or accept 640 as the first step and say which you chose. `2xl` (1536px) is unused; Desktop-Large is the last band.

* Contain page layouts with `max-width: 1400px; margin-inline: auto`.
* **NEVER `h-screen`.** Always `min-h-[100dvh]` - iOS Safari address bar causes layout jump.
* **Grid over flex-math.** Never `w-[calc(33%-1rem)]`. Use CSS Grid with a `{spacing.*}` gap.
* Every multi-column layout declares its `<768px` fallback in the same component. No "Tailwind handles it" assumptions.
* **Touch targets minimum 44x44px** on Mobile and Tablet, achieved with `{spacing.sm}` vertical and `{spacing.md}` horizontal padding even when the glyph is smaller.

**Component libraries:** `[PRODUCTION]` shadcn/ui and similar copy-in primitives are allowed, but **never in their default state**. Radii, colors, typography, and focus styles get retokenized to Section 1 on the way in. A screen that ships recognisable shadcn defaults has skipped the design system.

### 3.F Dependency Verification `[PRODUCTION]`
Before importing any third-party library, read `package.json`. If missing, output the install command first. Never assume a library exists.

`[DRAFT]` there is nothing to verify because there are no imports. The equivalent discipline is that a draft depends on nothing it cannot reach from the filesystem or a plain CDN URL, and it opens correctly from `file://` with no server.

---

## 4. DESIGN DIRECTIVES

### 4.1 Typography
The family question is settled by Section 1: **Geist for everything, Geist Mono for figures, no third family.** What remains are the mechanics.

* **Hierarchy comes from size, tracking, and a 400 -> 500 weight step.** Never from a different typeface, never from 700+ weights. Heavy weights read as loud and this brand is not loud.
* **Tracking tightens with size.** `-0.03em` at `{typography.display-xl}` easing to `0` by `{typography.body-lg}`. Never positive letter-spacing.
* **No all-caps.** Sentence case or title case. `text-transform: uppercase` is banned, which also kills the eyebrow pattern outright (Section 4.8).
* **Every figure goes through `{typography.numeric-md}` or `{typography.numeric-sm}`.** Money, dates, counts, byte sizes, percentages. In a financial product, figures get compared down a column and alignment is functional, not decorative.
* **Body measure:** cap paragraph width around 65 characters. Line height stays at `1.5` for all body tokens.
* **Emphasis within a headline** uses italic or a weight step of the SAME font. Injecting a different family for one word is amateur.
* **ITALIC DESCENDER CLEARANCE (mandatory):** an italic word containing `y g j p q` will clip at `line-height: 1`. Use `1.1` minimum plus `padding-bottom: 4px` reserve on the wrapper. Audit every italic word in display type before shipping.
* **Orphaned words:** fix a single trailing word with `text-wrap: balance` on headlines, `text-wrap: pretty` on body.

### 4.2 Color
The palette question is settled by Section 1. What remains is discipline in applying it.

* **The working palette is five tokens:** `{colors.canvas}`, `{colors.paper}`, `{colors.ink}`, `{colors.ink-soft}`, `{colors.primary}`. Everything else is a supporting role. Introducing a color not in Section 1 is banned - reuse beats invention.
* **`{colors.primary}` is rationed.** One, at most two, primary actions per screen view. Also allowed as a focus indicator. Never for body text, never decorative, never for secondary actions.
* **Surfaces:** `{colors.canvas}` is the base. `{colors.canvas-deep}` for globals that should recede (footer, app chrome). `{colors.paper}` for anything that needs visual containment.
* **Text:** `{colors.ink}` for headings and primary text, `{colors.ink-soft}` for secondary, helper, and metadata. On a primary background, always `{colors.on-primary}`.
* **Links:** `{colors.link}`, hovering to `{colors.ink}` with a `{colors.paper}` background. Not underlined by default.
* **Borders:** `{colors.hairline}` for dividers. `{colors.hairline-strong}` only for an active tab or a focused outline that needs more weight.
* **`{colors.accent-pale-blue}`** is reserved for secondary buttons, carrying `{colors.primary-deep}` as its label.
* **`{colors.primary-bright}` is a non-text accent.** `{colors.on-primary}` over it is 3.4:1, so it is never a background for a label. It belongs on icons, graphic marks, meter fills and status dots, where the 3:1 non-text threshold applies: it clears 4.9:1 on `{colors.canvas}`, 5.3:1 on `{colors.canvas-deep}` and 4.4:1 on `{colors.paper}`. The primary button darkens to `{colors.primary-deep}` on hover rather than brightening.
* **COLOR CONSISTENCY LOCK (mandatory):** the accent is `{colors.primary}` on every screen of the project. No screen gets a different CTA color. No status badge in a color outside Section 1.

### 4.3 Layout Diversification
* **ANTI-CENTER BIAS:** centered hero / H1 blocks are avoided when `DESIGN_VARIANCE > 4`. Use split screen, left-content with right-asset, or asymmetric whitespace.
* **Override:** a centered composition is fine for a manifesto, a launch announcement, or a single-message system state (404, revoked link) where the message IS the design.

### 4.4 Surfaces, Cards, Shape
* **FLATNESS IS LAW.** No `box-shadow` on any element, ever. All shadow tokens resolve to `none`. Elevation, grouping, and hierarchy come from color contrast (`{colors.paper}` on `{colors.canvas}`), space, and typographic weight. There is no glassmorphism, no frosted panel, no tinted shadow, no inner-shadow edge refraction, and no grain or noise overlay in this system.
* **Cards only when containment communicates real hierarchy.** Otherwise group with a `1px {colors.hairline}` rule, a `divide-y`, or plain negative space.
* At `VISUAL_DENSITY > 7`, generic card containers are banned outright. Data breathes in plain layout separated by hairlines.
* **SHAPE CONSISTENCY LOCK:** the radius rule is documented and fixed - interactive elements (buttons, inputs, pills) are `{rounded.pill}`, cards and containers are `{rounded.lg}`, inner elements and badges are `{rounded.sm}` or `{rounded.xs}`. Follow it everywhere. Do not "vary the radius for interest".
* **No texture ornament.** Sections that feel empty get fixed with better type scale, real imagery, or tighter composition, not with noise overlays or ambient gradients.

### 4.5 Interactive States
LLMs ship "static successful state only". Always build the full cycle.

* **Loading:** skeleton loaders shaped like the final layout. Not circular spinners.
* **Empty:** composed, and it says how to populate.
* **Error:** inline for forms, contextual toasts only for transient events. Never `window.alert()`.
* **Focus:** visible ring on every interactive element - `1px solid {colors.primary}` border per `input-text-focus`. Accessibility requirement, not optional.
* **Active:** `translateY(1px)` or `scale(0.98)` to simulate physical press.
* **Transitions:** every state change animates over `{motion.duration-fast}` with `{motion.ease-standard}`. Zero-duration state flips feel broken.
* **CURSORS (mandatory):** every clickable element - button, link, tab, row action - sets `cursor: pointer`. Every text field sets `cursor: text`. A default arrow on a clickable element is a Pre-Flight fail.
* **BUTTON CONTRAST CHECK (mandatory, a11y):** verify label against button background. WCAG AA, 4.5:1 body / 3:1 for 18px+. The three shipped pairs measure `{colors.on-primary}` on `{colors.primary}` at 4.7:1, `{colors.on-primary}` on `{colors.primary-deep}` at 6.9:1, and `{colors.primary-deep}` on `{colors.accent-pale-blue}` at 5.0:1. `{colors.on-primary}` on `{colors.primary-bright}` is 3.4:1 and fails, which is why no button uses it. Audit anything else, especially ghost buttons over imagery.
* **CTA WRAP BAN:** button labels fit on one line at desktop. 3 words max for primary actions, ideally 1-2. A wrapped CTA is a Pre-Flight fail.
* **NO DUPLICATE CTA INTENT:** "Get started" + "Try free" + "Sign up" on one page = one intent, three labels. Pick one label per intent and use it in nav, body, and footer.
* **FORM CONTRAST CHECK (mandatory, a11y):** inputs, placeholders, focus rings, helper text, and error text all pass WCAG AA against their section background.
* **Active nav state:** the current page or tab is visually distinct. Users need to know where they are.
* **No dead links.** A button pointing at `#` either gets a real destination or a visible disabled state.

### 4.6 Forms & Data
* Label ABOVE the input. Helper text present in markup even when empty. Error text BELOW. `{spacing.xs}` between the parts of an input block.
* **No placeholder-as-label. Ever.**
* Client-side validation for emails, required fields, and formats.
* Tables: figures right-aligned and set in `{typography.numeric-*}`; labels left-aligned. Column headers in `{typography.body-sm}` `{colors.ink-soft}`.
* Do not put `border-t` AND `border-b` on every row. Pick one, use it sparsely, or group rows into chunks.

### 4.7 Component Cliches (replace on sight)

These are the default component choices that make a product look assembled rather than designed. Each has a stated alternative; reach for the alternative unless the cliche is genuinely the right call.

* **Generic card look** (border + background + containment on everything). A card earns its container only when grouping communicates hierarchy. Otherwise: background alone, or spacing alone, or a `1px {colors.hairline}` rule.
* **One filled button + one ghost button, everywhere.** Add a tertiary text-link tier so not every action shouts at the same volume. `button-primary` is already rationed to 1-2 per view; the rest of the actions need somewhere quieter to live.
* **Accordion FAQ sections.** Prefer a side-by-side list, searchable help, or inline progressive disclosure. (Accordions remain a legitimate tool for compressing a long categorisable list per Section 4.10 - the ban is on accordion-as-default-FAQ-layout, not on the control itself.)
* **Three-card carousel testimonials with dots.** Prefer a masonry wall, an embedded real post, or one rotating quote. Same distinction: carousels are fine for breadth-heavy lists, wrong as the default testimonial pattern.
* **Pricing table with three equal towers.** Highlight the recommended tier with `{colors.primary}` and emphasis, not with extra height.
* **Modals for everything.** Use inline editing, a slide-over panel, or an expanding section for simple actions. Reserve modals for genuinely blocking decisions.
* **Badges as pills by default.** Badge shape follows the Section 4.4 radius rule - `{rounded.xs}` or `{rounded.sm}` for inline status markers. `{rounded.pill}` is the signature of an interactive control, so a pill-shaped non-interactive badge misreads as a button.
* **Avatar circles exclusively.** Rounded squares at `{rounded.sm}` read less generic and sit better in dense table rows.
* **Footer link farm in four columns.** Simplify to the real navigation paths plus the legally required links.
* **Dashboard with an inevitable left sidebar.** Consider top navigation, a command menu, or a collapsible panel. The sidebar is a default, not a decision.
* **No theme toggle at all** in this system. Section 4.12 is dark-only, so the sun/moon switch question does not arise.

### 4.8 Layout Discipline (hard rules)
* **Hero MUST fit the initial viewport.** Headline max 2 lines desktop, subtext max 20 words and max 4 lines, CTA visible without scrolling. A 4-line hero headline is a font-size error, never a copy-length error.
* **Hero font-scale discipline.** Plan type size and asset size together. Default range `text-4xl md:text-5xl lg:text-6xl`; go larger only for a 3-5 word headline.
* **Hero top padding cap:** max ~96px at desktop. More and the content floats halfway down the viewport and reads as a bug.
* **HERO STACK DISCIPLINE - max 4 text elements:** headline, subtext, CTAs (1 primary + max 1 secondary), and at most one small supporting element. **BANNED in the hero:** tagline under the CTAs, trust micro-strip, pricing teaser, feature bullets, avatar row. Those become sections below.
* **EYEBROWS ARE BANNED OUTRIGHT.** The small uppercase wide-tracking label above a section headline (`SELECTED WORK`, `THE HARDWARE`, `001 - Capabilities`) violates the no-all-caps and no-positive-tracking rules in Section 4.1, and it is the single most templated pattern in AI-built pages. The headline alone is enough; a section's position on the page already categorizes it. Mechanical check: zero instances of `uppercase tracking` micro-labels in the output.
* **"Trusted by" logo walls live UNDER the hero**, never inside it.
* **Navigation renders on ONE line at desktop**, height 80px max, 64-72px default. A two-line nav at desktop is broken.
* **SPLIT-HEADER BAN:** "left big headline + right small explainer paragraph floating in a corner" as a section header is banned. Stack them vertically, headline then body at 65ch. The split is allowed only when the right column carries a real visual or interactive element.
* **Bento / feature grids need rhythm.** Do not stack 6 identical left-image / right-text rows.
* **BENTO CELL COUNT:** N items produce exactly N cells. An empty cell in the middle or at the end means the grid was planned wrong. Reshape it; never paste a blank tile.
* **SECTION-LAYOUT-REPETITION BAN:** a layout family appears at most once per page. 8 sections need at least 4 different families.
* **ZIGZAG CAP:** max 2 consecutive image+text split sections. The 3rd is a Pre-Flight fail. Break with a full-width section, a vertical stack, or a grid.
* **Bento background diversity:** at least 2-3 cells in a multi-cell grid carry real visual variation - an image, a tint from `{colors.canvas-deep}` or `{colors.paper}`, a pattern. Six identical `{colors.paper}` text cards reads as AI default.
* **Whitespace is active.** All padding, margin, and gap values come from `{spacing.*}`. Arbitrary pixel values are forbidden; if a value you want is not in the scale, take the nearest one.
* **Section rhythm:** `{spacing.section}` between major page sections, modulated by `VISUAL_DENSITY` within the scale (down to `{spacing.xxl}` at high density). Do not substitute arbitrary `py-32`-style values.
* **Optical alignment:** icons beside text, glyphs inside circles, and text inside buttons often need 1-2px adjustment. Mathematical centering is not always optical centering.
* **Align shared elements across side-by-side items.** Titles, values, and buttons in a card row share a baseline. Pin card CTAs to the bottom so they form a clean horizontal line regardless of content length above.
* **Do not force equal card heights with flexbox** when the content genuinely varies. Either allow variable heights, or fix the height of the shared blocks (title, value) so the variable part is the only thing that differs.
* **Vertical padding is optical, not symmetrical.** Identical top and bottom padding often reads as bottom-light because descenders and trailing elements sit high in their box. Adjust the bottom by one step on the `{spacing.*}` scale when it looks short.

### 4.9 Images & Visual Assets
Text-only pages with fake-screenshot divs are slop. Even a restrained interface needs real imagery where imagery belongs.

**Priority order:**
1. **Image-generation tool first.** If any image-gen tool is available, use it for section-specific assets at the right aspect ratio.
2. **Real web images second.** `https://picsum.photos/seed/{descriptive-seed}/{w}/{h}`, real brand URLs when the brief provides them, or open-license sources when allowed.
3. **Last resort: say so.** Leave a labeled slot (`<!-- TODO: hero product shot, 1600x1200 -->`) and tell the user exactly which placements need real images. Do NOT fill the gap with hand-rolled SVG illustrations or div-based fake screenshots.

* **Div-based fake screenshots are banned.** A "product preview" built from styled `<div>` rectangles with fake rows and fake terminal chrome is the number one LLM design tell. Use a real screenshot, a generated image, a real mini-instance of the component, or nothing.
* **Hand-rolled decorative SVG is strongly discouraged.** Acceptable only for a single simple geometric mark, or when the brief explicitly asks for it.
* **Logo walls use real SVG logos** - Simple Icons (`https://cdn.simpleicons.org/{slug}/fbfcfd`) or devicon. Not text wordmarks in a row. For invented brands, generate a simple monogram mark.
* **LOGO-ONLY rule:** a logo wall contains logos and nothing else. No category label under each logo.
* All imagery must sit legibly on `{colors.canvas}`. Ensure single-color logos render in `{colors.ink}` or `{colors.cloud}`.
* **Missing favicon is a bug.** Always ship a branded one.
* No stock "diverse team" photography. No repeated avatar for distinct people.

### 4.10 Content Density & Copy
* **Default section shape:** headline <= 8 words, sub-paragraph <= 25 words, plus one visual or one CTA. More requires justification from the section's job.
* **No data-dump marketing sections.** A 20-row table on a marketing page is the wrong layout: show the top 3-5 with a "view all" link, or move the data to a real product surface where density is the point.
* **Long lists need a different component, not a longer list.** Past 5 items reach for a 2-column split, a card grid, tabs, an accordion, or scroll-snap pills.
* **COPY SELF-AUDIT (mandatory before ship).** Re-read every visible string: headlines, labels, button text, body, captions, alt text, footer, error messages. Rewrite anything that is grammatically broken, has an unclear referent, reads as cute-but-wrong wordplay, or sounds like an LLM performing thoughtfulness. Plain functional copy beats clever copy.
* **AI copy cliches are banned:** "Elevate", "Seamless", "Unleash", "Next-Gen", "Game-changer", "Revolutionize", "Delve", "Tapestry", "In the world of".
* **Fake-precise numbers are banned** unless they come from real data or are explicitly labeled as sample. Do not fake engineering precision the product does not claim.
* **No generic placeholder identities:** no "John Doe", "Jane Smith", "Acme Corp", "Nexus", "SmartFlow", no Lorem Ipsum. Use realistic contextual names and real draft copy.
* **No fake-round numbers** (`99.99%`, `50%`, `$100.00`). Use organic values.
* **Sentence case for headers**, not Title Case On Every Header.
* **No exclamation marks in success messages.** Be confident, not loud. **No "Oops!"** - say "Connection failed. Try again."
* **Active voice.** "We couldn't save your changes", not "Mistakes were made".
* **One copy register per page.** Do not mix technical mono-metadata, editorial prose, and marketing punch in one composition.
* Vary blog and record dates; identical timestamps across items read as fake.

### 4.11 Quotes & Testimonials
* Max 3 lines of quote body. Cut the original if needed - a page quote is a snippet, not a full review.
* Attribution is name + role + optional company. Never a bare first name.
* Real typographic quotes or none. Not straight ASCII quotes.
* No em-dash inside quote text. See Section 7.D.

### 4.12 Theme Lock
**This system is dark. There is no light mode.** `scheme: dark` in Section 1 is a brand decision, not a default.

* All surfaces derive from `{colors.canvas}` / `{colors.canvas-deep}` / `{colors.paper}`. A light section sandwiched between dark ones reads as a copy-paste accident.
* Do not implement a `prefers-color-scheme: light` branch, a theme toggle, or `dark:` variant pairs. There is one theme.
* Contrast targets still apply in full: WCAG AA minimum for body, AAA target for display copy. `{colors.ink}` on `{colors.canvas}` clears both.
* Section-level variation within the dark family is fine (`{colors.canvas-deep}` beside `{colors.canvas}`). Flipping to a light background mid-page is broken.
* No pure `#000000` and no pure `#ffffff` as surfaces. Section 1 already avoids both.

---

## 5. MOTION

Motion is purposeful and restrained. It exists to give feedback and to show that state changed, not to perform.

* **Every interactive state change** transitions over `{motion.duration-fast}` with `{motion.ease-standard}`. Hovers, focus, press, disclosure.
* **MOTION MUST BE MOTIVATED.** Before adding any animation, name what it communicates: hierarchy, sequence, feedback, or state transition. "It looked cool" is not an answer. If you cannot justify it in one sentence, delete it.
* **MOTION CLAIMED = MOTION SHOWN.** If `MOTION_INTENSITY` is 3-4, interactive feedback and view transitions must actually be implemented. A static page claiming 4 is broken. Conversely, if you cannot ship working motion in scope, set the dial to 2 and ship a clean static page. Never half-build motion that breaks.
* **Scroll-reveal is the only scroll-driven effect in this system** and only at `MOTION_INTENSITY: 4`. See 5.A.
* **Banned in this system:** scroll hijacking, horizontal scroll-pan, sticky card stacks, pinned sections, parallax, marquees, magnetic cursor physics, perpetual pulse/float/shimmer loops, smooth-scroll inertia libraries, custom cursors, text scramble, and particle effects. These belong to a cinematic design language; Mercury is not one. `scroll-behavior: smooth` on anchor links is fine.

### 5.A Scroll-Reveal Stagger - canonical skeleton `[PRODUCTION]`
```tsx
"use client";
import { motion, useReducedMotion } from "motion/react";

export function RevealStagger({ items }: { items: React.ReactNode[] }) {
  const reduce = useReducedMotion();
  return (
    <ul className="grid gap-6">
      {items.map((item, i) => (
        <motion.li
          key={i}
          initial={reduce ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.3, delay: i * 0.05, ease: [0.4, 0, 0.2, 1] }}
        >
          {item}
        </motion.li>
      ))}
    </ul>
  );
}
```
Duration and easing match `{motion.duration-base}` and `{motion.ease-standard}`. Do not lengthen them.

### 5.A2 Scroll-Reveal - CSS only, no JavaScript `[DRAFT]`
A draft has no bundler and often no `<script>` at all. Scroll-driven animation is native CSS; use it, and let it degrade to visible-and-static where unsupported.

```css
/* Element is visible by default. The animation only ever runs where both
   scroll-timeline and no-preference are true, so the no-JS, unsupported,
   and reduced-motion paths all land on the same correct state. */
@media (prefers-reduced-motion: no-preference) {
  @supports (animation-timeline: view()) {
    .reveal {
      animation: reveal-in linear both;
      animation-timeline: view();
      animation-range: entry 10% cover 30%;
    }
    @keyframes reveal-in {
      from { opacity: 0; transform: translateY(16px); }
      to   { opacity: 1; transform: none; }
    }
  }
}
```
Stagger by varying `animation-range` per item, or with `animation-delay: calc(var(--i) * 50ms)` where `--i` is set inline by the generator. Never animate anything but `transform` and `opacity`.

### 5.B Forbidden Animation Mechanics
* **`window.addEventListener("scroll", ...)` is banned** on both targets. Runs every frame, no batching. Use `useScroll()`, IntersectionObserver, or CSS `animation-timeline: view()`.
* **Animating `top` / `left` / `width` / `height`.** Animate `transform` and `opacity` only. Both targets.
* `[PRODUCTION]` **Scroll progress in React state** using `window.scrollY` - same reason as above.
* `[PRODUCTION]` **`requestAnimationFrame` loops touching React state.** Use motion values.
* `[PRODUCTION]` Use Motion's `layout` / `layoutId` for real layout changes (reordering, expanding). Do not wrap static content in `layout` "for safety" - it costs measurement work every render.
* `useEffect` animations require strict cleanup.

---

## 6. PERFORMANCE & ACCESSIBILITY

* **Hardware acceleration:** animate `transform` and `opacity` only. `will-change` sparingly, only on elements that actually animate.
* **Reduced motion (mandatory):** anything above `MOTION_INTENSITY: 3` honors `prefers-reduced-motion`. Wrap with `useReducedMotion()` or gate CSS behind `@media (prefers-reduced-motion: no-preference)`.
* `[PRODUCTION]` **Core Web Vitals:** LCP < 2.5s (hero image preloaded or `priority`), INP < 200ms, CLS < 0.1 (reserve space for images, fonts, embeds). Self-hosted fonts matter here.
* `[PRODUCTION]` **Bundle:** lazy-load anything below the fold. Motion is not tiny.
* **Z-index restraint:** never spam `z-50`. Keep a documented scale in a constants file for sticky nav, overlays, modals.

**Accessibility is not target-dependent.** Every rule below this line applies to a draft exactly as it applies to production. A mockup is where keyboard order, focus visibility, contrast, and semantics are cheapest to get right, and a draft that ships without them teaches the production build the wrong shape.
* **Semantic HTML:** `<nav>`, `<main>`, `<article>`, `<aside>`, `<section>`. Not div soup.
* **Alt text on every meaningful image.** Never `alt=""` or `alt="image"` on content images.
* **Skip-to-content link** for keyboard users.
* **Keyboard navigation** works for every interactive element, with a visible focus ring.
* **Relative units** for widths. No hardcoded pixel widths on layout containers.
* Meta tags: `<title>`, `description`, `og:image` on every public page.

### 6.A Strategic Omissions (what gets forgotten every time)
These are not polish. A flow missing any of them is unfinished, and they are the items most reliably left out.

* **Legal links.** Privacy policy and terms in the footer of any public surface.
* **Cookie consent.** Where the jurisdiction requires it, a compliant banner. The Section 1 `card` recipe is the canonical container for it.
* **A way back.** Every screen in a flow has an exit. Dead ends where the only escape is the browser back button are a bug.
* **A custom 404** and a custom error page, branded and helpful, not the framework default.
* **Form validation** on the client for emails, required fields, and formats, matching the inline error pattern in Section 4.5.
* **A favicon.** See Section 4.9.

---

## 7. AI TELLS (forbidden patterns)

### 7.A Visual
* No neon or outer glows. No gradient text on large headers. No custom mouse cursors.
* No three-column equal feature cards. Use a 2-column zigzag, an asymmetric grid, or a horizontal-scroll alternative.
* No decorative crosshairs or hairline grid lines drawn just to look designed. Rules organize real content or they are removed.
* No vertical rotated text.
* No scoring or progress bars with filled background tracks as comparison visuals. A number plus a small icon reads better.
* No decorative colored status dots. Zero by default. A dot is allowed only when it conveys real semantic state, once per section at most.

### 7.B Content
* No section-number eyebrows (`00 / INDEX`, `001 - Capabilities`, `06 - how it works`). Eyebrows are banned entirely anyway (Section 4.8).
* No version labels in the hero (`V0.6`, `BETA`, `EARLY ACCESS`) unless the brief is literally a launch announcement.
* No version footers (`v1.4.2`, `Build 0048`, `last sync 4s ago`) on any page that is not a devtool status surface.
* No `Brand - No. 01` micro-meta lines.
* No generic step labels (`Stage 1 / Stage 2`, `Phase 01`). The step content is the label.
* No micro-meta-sentences under a heading explaining the heading.
* No poetic section labels: "From the field", "Field notes", "Currently on the bench", "On our desks". Use plain functional labels or none.
* No "Quietly in use at" / "Quietly trusted by". Say "Trusted by", "Used at", or let the logos speak.
* No locale / time / weather strips (`LIS 14:23 - 18C`) unless the product is genuinely place or timezone specific.
* No scroll cues (`Scroll`, `Scroll to explore`, animated mouse-wheel icons). The user knows what scroll is.
* No decoration text strips at the hero bottom (`DESIGN. BUILD. SHIP.`).
* No pills or tags overlaid on images. Caption below the image, outside it, or nothing.
* No photo-credit captions as decoration. Real credit for a real photographer only.
* **The middle dot (`.`) separator is rationed** to one per metadata line. Prefer line breaks, hairlines, or columns.

### 7.C Code
* No hand-rolled SVG icon paths.
* No broken image links. Use seeded Picsum or real assets.
* No commented-out dead code or debug artifacts.
* No import hallucinations. Verify against `package.json`.
* No arbitrary `z-index: 9999`.
* No inline styles mixed into a project that has a styling system.

### 7.D EM-DASH BAN
**The em-dash (`-`, U+2014) is completely banned.** No "limited use" allowance, no "in body copy is fine" allowance.

* Banned in headlines - use a period or comma.
* Banned in labels, button text, captions, nav items, alt text.
* Banned in body copy - restructure into two sentences, or use a comma, parentheses, or a colon.
* Banned in quote attribution - use a hyphen with spaces or a line break.
* Banned in en-dash form (U+2013) as a separator. Ranges use a plain hyphen (`2018-2026`, `40-80k`).

The only permitted dash characters in visible output are the regular hyphen and a minus sign in math. A single em-dash or en-dash anywhere visible fails the Pre-Flight Check.

---

## 8. MODE: NEW, MODIFY, OR RE-SKIN

Misclassifying the mode is the biggest source of bad output on an existing codebase.

### 8.A Detect the mode first
* **New** - a screen or page that does not exist yet. Dials from Section 2.A.
* **Modify** - an existing screen changes. Audit first, preserve everything not in scope.
* **Re-skin** - existing content and IA, new visual language. Treat visuals as new; preserve content, routes, and behavior exactly.

If genuinely ambiguous, ask once.

### 8.B Audit before touching
Document the current state before proposing changes:
* **Tokens in play** - which colors, type, radii the screen currently uses, and whether they come from a tokens file or are inlined.
* **Information architecture** - routes, nav labels, conversion paths.
* **Content blocks** - what exists, what is doing work, what is filler.
* **Patterns to preserve** - signature interactions, recognisable structure, copy voice.
* **Patterns to retire** - AI tells from Section 7, broken layouts, dead links, perf traps.
* **Dial reading of the current screen** - infer its existing `DESIGN_VARIANCE` / `MOTION_INTENSITY` / `VISUAL_DENSITY`. That is your starting point, not the preset.
* **SEO baseline** for public pages - meta titles, structured data, OG cards. SEO migration is the top redesign risk.

### 8.C Preservation rules
* **Do not change information architecture** unless asked. Route slugs, anchor IDs, and nav labels stay stable.
* **Preserve copy voice** unless a rewrite was requested. Visual work is not a content rewrite.
* **Honor existing accessibility wins.** Never regress focus states, alt text, keyboard nav, or contrast.
* **Respect analytics.** Do not rename buttons, form fields, or section IDs that tracking depends on.
* **Work with the existing stack.** Do not migrate frameworks or styling libraries to satisfy this skill.
* **Keep changes reviewable.** Small targeted improvements over big rewrites. Test after each change.

### 8.D Fix priority (highest impact per unit of risk)
1. **Token wiring** - get Section 1 into a tokens file and point components at it.
2. **Typography pass** - family, scale, tracking, tabular figures.
3. **Spacing and rhythm** - `{spacing.*}` everywhere, section rhythm, vertical alignment.
4. **Color recalibration** - collapse to the Section 4.2 working palette, one accent.
5. **State coverage** - hover, focus, active, loading, empty, error.
6. **Component replacement** - swap cliche patterns for the Section 1 component recipes.
7. **Composition** - restructure sections only when the existing block is unsalvageable.

### 8.E Targeted evolution vs full rebuild
Pick the smaller intervention that satisfies the brief:
* Structure, content, and routes are sound, the problem is visual → **targeted evolution** using levers 1-5 above. Roughly 70% of the value at 40% of the risk, and it is the right call most of the time.
* The debt is structural (no token layer, broken responsive, incoherent IA) → **full rebuild of the surface** with strict content and route preservation.
* The brand itself is changing → treat as new, per Section 8.A.

### 8.F Never change silently
Route slugs. Primary nav labels. Form field names or order. Brand logo or wordmark. Legal, consent, or cookie copy. Any of these needs explicit approval.

---

## 9. SCOPE

**In scope:** product UI (dashboards, tables, forms, flow steps, settings), system surfaces (empty, loading, error, 404), marketing and landing pages, share and recipient-facing pages, transactional email.

Dense data surfaces are in scope and are governed by `VISUAL_DENSITY` 6-10 plus the table rules in Section 4.6. For a genuinely complex data grid, a headless library (TanStack Table) handles behavior while this skill handles presentation - that is a valid split, not an escape hatch.

**Transactional email is in scope with three carve-outs**, because the medium cannot honor the mechanics: values are inlined as `style` attributes rather than referenced from custom properties (Section 1.A), layout uses tables rather than grid, and web fonts are unreliable so the fallback stack has to carry the design. Everything else holds - the same palette, the same type scale, the same copy discipline, the same flat surfaces.

**Section 4.8's hero rules are marketing-page rules.** An app screen has a header, not a hero, and the viewport-fit, hero-stack, and hero-padding constraints do not apply to it. The rules that apply everywhere are the ones about eyebrows, layout repetition, grid cell counts, nav, spacing scale, and alignment.

**Out of scope:** code editors (use Monaco or CodeMirror with their own skinning), native mobile (Apple HIG / Material), realtime collaborative presence UI. Say so explicitly if the brief is one of these.

---

## 10. FINAL PRE-FLIGHT CHECK

**Not optional. Run every box. Any failure means the output is not done.**

**System fidelity**
- [ ] Design Read declared (Section 0.B) and dial values explicit, reasoned, not silently defaulted?
- [ ] Every color, spacing, radius, and font value comes from a Section 1 token via CSS variables? Zero inlined hex, zero arbitrary px spacing?
- [ ] `{colors.primary}` used on at most 2 actions per screen, and never for text or decoration?
- [ ] **Zero `box-shadow`** anywhere? No glassmorphism, no grain, no tinted shadow?
- [ ] Radius rule followed everywhere: pill for interactive, `{rounded.lg}` for containers, `{rounded.sm}`/`{rounded.xs}` inside?
- [ ] Single theme - dark throughout, no light section, no theme toggle, no `dark:` pairs?
- [ ] Geist everywhere, Geist Mono on every figure, no third family, no weight above 500?
- [ ] Every figure uses `{typography.numeric-*}` with `tabular-nums`?
- [ ] No all-caps text and no positive letter-spacing anywhere?

**Interaction & a11y**
- [ ] `cursor: pointer` on every clickable element, `cursor: text` on every text field?
- [ ] Visible focus ring on every interactive element, using `{colors.primary}`?
- [ ] Button contrast passes WCAG AA? Form inputs, placeholders, helper and error text all pass?
- [ ] No CTA label wraps to 2+ lines at desktop?
- [ ] No two CTAs share the same intent?
- [ ] Empty, loading, and error states all provided?
- [ ] No component cliches (Section 4.7) - no three-tower pricing, no dot-carousel testimonials, no accordion-by-default FAQ, no modal for a simple inline action, no pill-shaped non-interactive badge?
- [ ] Strategic omissions covered (Section 6.A) - legal links, a way back from every flow screen, custom 404, form validation, favicon?
- [ ] Touch targets >= 44x44px at Mobile and Tablet?
- [ ] Reduced motion honored for anything above `MOTION_INTENSITY: 3`?
- [ ] Keyboard navigable, semantic HTML, skip-link present, alt text on meaningful images?

**Layout**
- [ ] Hero fits the viewport: headline <= 2 lines, subtext <= 20 words and <= 4 lines, CTA visible without scroll?
- [ ] Hero has <= 4 text elements, with no tagline under the CTAs and no trust strip inside it?
- [ ] **Zero eyebrows** - no uppercase wide-tracking micro-labels above section headlines?
- [ ] No split-header (big left headline + small floating right paragraph)?
- [ ] No 3+ consecutive image+text split sections?
- [ ] No two sections share a layout family (4+ families across 8 sections)?
- [ ] Grid cell count matches item count exactly - no empty tiles?
- [ ] Multi-cell grids have 2-3 cells with real visual variation?
- [ ] Nav on one line at desktop, height <= 80px?
- [ ] Section rhythm from `{spacing.*}`, mobile collapse declared explicitly per multi-column layout?
- [ ] `min-h-[100dvh]`, never `h-screen`? Grid, never flex percentage math?

**Content**
- [ ] **Zero em-dashes and zero en-dashes** anywhere visible (Section 7.D)?
- [ ] Copy self-audit run - every visible string re-read, nothing broken or AI-hallucinated?
- [ ] No AI cliche verbs, no "Oops!", no exclamation marks in success messages, sentence case headers?
- [ ] No generic placeholder identities, no Lorem Ipsum, no fake-round numbers?
- [ ] No fake-precise stats without a real source or an explicit sample label?
- [ ] Quotes <= 3 lines with full attribution?
- [ ] Real images used - gen tool, then seeded Picsum, then labeled placeholder slots? No div-based fake screenshots, no hand-rolled decorative SVG? (Rendering the product's own real UI with real data is not a fake screenshot - the ban is on simulating a product you are not building.)
- [ ] Logo walls use real SVG logos with no category labels?

**Motion (both targets)**
- [ ] Every animation justifiable in one sentence?
- [ ] Nothing pins, hijacks scroll, marquees, or loops perpetually?
- [ ] No `window.addEventListener('scroll')`? Only `transform` and `opacity` animated?
- [ ] One icon set, one viewBox, one stroke width across every screen?

**Code `[PRODUCTION] only`**
- [ ] Icons from an allowed library, no hand-rolled paths? (Draft inverts this - see Section 3.C.)
- [ ] Motion isolated in `'use client'` leaves with `useEffect` cleanup?
- [ ] Every import verified against `package.json`?
- [ ] Core Web Vitals plausibly hit? Fonts self-hosted, not CDN?
- [ ] No framework or styling-library migration introduced?

**Code `[DRAFT] only`**
- [ ] Opens correctly from `file://` with no server and no build step?
- [ ] Every state of the flow exists as its own file, not just the happy path?
- [ ] Icons emitted from one generator helper, not pasted per use?
- [ ] A comment names the fontsource package the production version should self-host?
- [ ] Token values come from the shared tokens file, not re-declared locally?

**Mode (when modifying an existing surface)**
- [ ] Mode detected and audit performed (Section 8.B)?
- [ ] Routes, nav labels, form field names, and legal copy unchanged?

If a single applicable box cannot be honestly ticked, it is not done. Boxes tagged for the other delivery target are not failures - skip them and say which target you built for.

---

## 11. ITERATION GUIDE

1. **Establish the surface.** Main page flow is `{colors.canvas}`; a contained module is `{colors.paper}`; receding chrome is `{colors.canvas-deep}`.
2. **Set the hierarchy.** `{typography.display-*}` for titles, `{typography.body-md}` for content, `{typography.numeric-*}` for every figure. Separate levels with size, tracking, and the 400 -> 500 weight step. Color with `{colors.ink}` and `{colors.ink-soft}`.
3. **Set the rhythm.** `{spacing.lg}` internal padding, `{spacing.xl}` between elements, `{spacing.section}` between page sections. Nothing off-scale.
4. **Style the primary action.** One `button-primary` per view. Secondary actions use `button-secondary`. Both are `{rounded.pill}` with `cursor: pointer`.
5. **Build every state.** Hover, focus, active, disabled, loading, empty, error. All transitions at `{motion.duration-fast}` with `{motion.ease-standard}`.
6. **Verify flatness.** Search the diff for `box-shadow`, `backdrop-filter`, and gradient declarations. There should be none.
7. **Check cursors.** Every clickable element pointer, every field text.
8. **Responsive pass.** Open at each band in Section 3.E. Layouts stack, type stays readable, touch targets hold at 44px.
9. **Run the Pre-Flight Check.** Every box in Section 10.

---

## 12. WHAT THIS SKILL DELIBERATELY DROPPED

For traceability, these rules exist in the upstream anti-slop skills and were removed here because they contradict Section 1:

* Font selection guidance (serif pools, banned display serifs, family pairings) - Section 1 settles the typeface.
* Palette selection machinery (the AI-purple rule, the premium-consumer beige-and-brass ban, accent rotation, "desaturate accents below 80%") - Section 1 settles the palette, and `{colors.primary}` is deliberately saturated.
* Glassmorphism, Liquid Glass approximation, tinted shadows, inner-shadow edge refraction, grain and noise overlays, "add texture to flat sections" - the system is strictly flat.
* Dual light/dark mode protocol, `prefers-color-scheme` branching, theme toggles - the system is dark only.
* Radius variation for visual interest - the Section 1 radius scale is the documented rule. (The "pill badges are generic" note survives in Section 4.7, reframed: pill is reserved for interactive controls, so badges take `{rounded.xs}`/`{rounded.sm}`.)
* The sun/moon theme-toggle alternative - there is no toggle, the system is dark only.
* Eyebrow allowances (1 per 3 sections) - all-caps and positive tracking are banned, so eyebrows are gone entirely.
* GSAP sticky-stack and horizontal-pan skeletons, magnetic cursor physics, perpetual micro-interaction loops, marquees, smooth-scroll inertia - the motion ceiling is 4.
* The design-system selection map and its install appendices (Fluent, Carbon, Material, Polaris, Radix Themes, GOV.UK, USWDS, Bootstrap) - Mercury is the design system.
* The "not for dashboards or data tables" scope exclusion - inverted in Section 9, since this is a financial product.

Two further sections were dropped as inapplicable rather than conflicting:

* The **reference vocabulary** (a naming list of ~50 patterns: Dome Gallery, Holographic Foil Card, Liquid Swipe Transition, Kinetic Marquee, and so on). Most entries are banned by the motion ceiling or the flatness rule; the survivors (bento grid, masonry, split-screen) are described where they are used. If you want the full vocabulary as a brainstorming aid, it is intact in `design-taste-frontend` Section 10.
* The **block library schema** - a frontmatter and file-layout contract for a `blocks/` directory that was never populated upstream and does not exist here.

If a task genuinely needs one of these, it needs a different design system, and that is a conversation to have explicitly rather than a rule to bend quietly.
