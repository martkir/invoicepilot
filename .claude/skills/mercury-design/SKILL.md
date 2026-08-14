---
name: mercury-design
description: Use this skill when designing for Mercury, a modern and sophisticated online banking platform for startups and scaling businesses. This skill covers a dark theme with a primary blue accent, set in the 'Geist' and 'Geist Mono' font families. It includes specific color tokens like '#5266eb' for primary and '#1e1e2a' for canvas, as well as rounded corners ranging from 'none' to 'pill'.
disable-model-invocation: true
packages:
  - name: "@fontsource-variable/geist"
    purpose: Self-hosted Geist variable sans — the brand typeface
    kind: dependency
    curated: true
  - name: "@fontsource-variable/geist-mono"
    purpose: Self-hosted Geist Mono variable — tabular figures only
    kind: dependency
    curated: true
  - name: clsx
    purpose: Tiny utility for conditionally joining class names
    kind: dependency
    curated: true
  - name: tailwind-merge
    purpose: Merge Tailwind classes without style conflicts
    kind: dependency
    curated: true
  - name: class-variance-authority
    purpose: Type-safe component style variants (CVA)
    kind: dependency
    curated: true
  - name: shadcn
    purpose: Accessible, unstyled UI primitives you copy into the project
    kind: setup
    curated: true
    command: pnpm dlx shadcn@latest add
---
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
    backgroundColor: "{colors.primary-bright}"
  button-secondary:
    backgroundColor: "{colors.accent-pale-blue}"
    color: "{colors.primary}"
    rounded: "{rounded.pill}"
    padding: "{spacing.sm} {spacing.lg}"
    typography: "{typography.button-md}"
    cursor: "pointer"
    border: "1px solid transparent"
  button-secondary-hover:
    backgroundColor: "{colors.on-primary}"
  input-text:
    backgroundColor: "rgba(39, 39, 53, 0.5)" # uses paper, but with transparency
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

## Visual Theme & Atmosphere
The Mercury design system projects an aura of cool, collected competence. It's a digital-native aesthetic for companies that are building the future, blending a dark, cinematic visual style with moments of vibrant, electric blue. The atmosphere is minimalist and focused, removing all unnecessary ornamentation to create a clear, confident, and professional user experience. This isn't a playful brand; it's a serious financial tool, and the design reflects that with its sharp typography, structured layouts, and a color palette that evokes stability and technological sophistication. The system is set entirely in `Geist` — a tight, slightly mechanical grotesk that reads as engineered rather than decorative. Headlines separate themselves from body text through scale, negative tracking, and a step up in weight, not through a second typeface. `Geist Mono` handles every figure, so money, dates and counts align down a column. The overall impression is one of a premium, intelligent, and highly capable platform.

**Key Characteristics:**
*   **Dark, Cinematic Palette:** The interface is built on a foundation of deep, dark surfaces like `{colors.canvas}` and `{colors.canvas-deep}`, creating a focused, low-light environment. Text is rendered in bright, clear tones like `{colors.ink}`.
*   **Vibrant Action Color:** The electric `{colors.primary}` is used with extreme prejudice for the most important calls-to-action, creating unmissable focal points against the dark background.
*   **Expressive Display Typography:** Headlines command attention through scale and tight tracking, using `{typography.display-xl}` for major statements. `Geist` at 65px with `-0.03em` letter-spacing sets a headline that feels drawn rather than defaulted, creating a strong typographic hierarchy without a second family.
*   **Tabular Figures:** Every number — balance, amount, date, count — is set in `Geist Mono` with `tabular-nums` via `{typography.numeric-md}`. In a financial product, figures are compared down a column; alignment is a functional requirement, not a stylistic flourish.
*   **Strictly Flat Design:** The interface is entirely flat. There are no shadows to create depth. Hierarchy and separation are achieved through color contrast (`{colors.paper}` on `{colors.canvas}`), spacing from the `{spacing.*}` scale, and typographic weight. All shadow tokens are set to `{shadows.none}`.
*   **Pill-Shaped Interactivity:** Key interactive elements like buttons and inputs feature a `{rounded.pill}` shape, a modern convention that signals interactivity and softens the otherwise structured design.
*   **Minimalist Interface:** The UI is uncluttered. Elements are given ample space to breathe, using generous values like `{spacing.lg}` and `{spacing.xl}` for padding and margins, reinforcing a sense of calm and control.
*   **Subtle, Deliberate Animation:** Motion is purposeful and restrained, using `{motion.duration-fast}` for immediate feedback on interactions and `{motion.ease-standard}` for smooth, professional state changes.

## Color Usage Rules
The Mercury color palette is intentionally small and disciplined to maintain a consistent, premium feel. An agent building UI in this style should rely almost exclusively on the core set of tokens. The primary working palette consists of `{colors.canvas}`, `{colors.paper}`, `{colors.ink}`, `{colors.ink-soft}`, and `{colors.primary}`. New colors should never be introduced; reuse of these core tokens is paramount.

*   **Primary Action Color:** `{colors.primary}` is the brand's most powerful color and must be used sparingly to retain its impact. Limit its use to one, or at most two, primary call-to-action buttons per screen view (e.g., "Open Account"). It may also be used for critical focus indicators on form fields. Do not use it for text, decorative elements, or secondary actions.
*   **Surface & Backgrounds:** The base of any layout is the dark `{colors.canvas}`. For global elements that need to recede, such as the main site footer, use the even darker `{colors.canvas-deep}`. When a component needs to be visually contained or separated from the main background, it must be placed on a surface using `{colors.paper}`. The cookie banner is a perfect example of this.
*   **Text Colors:** All primary headings and important text should use `{colors.ink}` for maximum readability against the dark surfaces. For secondary information, sub-headlines, helper text, and footer links, use the slightly dimmer `{colors.ink-soft}`. Text on a `{colors.primary}` background must always be `{colors.on-primary}`.
*   **Links:** Standard text links, such as those in the main navigation, use `{colors.link}`. They should change color on hover to `{colors.ink}` and often gain a `{colors.paper}` background for emphasis. Do not underline navigation links by default.
*   **Borders & Dividers:** The system is flat and largely borderless. When a subtle divider is required, use `{colors.hairline}`. For interactive states, like an active tab or focused input that needs a stronger outline, `{colors.hairline-strong}` can be used, but sparingly.
*   **Accent Colors:** The `{colors.accent-pale-blue}` token is reserved for secondary buttons, providing a lower-emphasis alternative to the primary CTA.
*   **Flatness is Law:** This is a flat design system. Emphasis and hierarchy are created through color, typography, and space, not elevation. Never apply a box-shadow to any element. All components that might have a shadow in other systems must explicitly use `{shadows.none}`.

## Typography Hierarchy
The Mercury brand is set in a **single sans family, `Geist`**, across every text role — headings, body copy, UI, buttons, and captions. Hierarchy comes from size, tracking, weight, and color, never from swapping typefaces. The only second family is **`Geist Mono`**, and it is reserved exclusively for figures. Introducing a third typeface — especially a serif for "editorial" headlines — is forbidden and would dilute the brand's typographic identity.

| Role | Token | Use |
| :--- | :--- | :--- |
| Display XL | `{typography.display-xl}` | The main page hero heading. Use once per page for maximum impact. |
| Display LG | `{typography.display-lg}` | Section headings for major content blocks. |
| Display MD | `{typography.display-md}` | Sub-section headings or large labels within components. |
| Body XL | `{typography.body-xl}` | Hero sub-headings and introductory paragraphs. |
| Body LG | `{typography.body-lg}` | Large body copy, pull quotes, or block quotes. |
| Body MD | `{typography.body-md}` | The default size for all paragraph text and standard UI elements like navigation links. |
| Body SM | `{typography.body-sm}` | Smaller, secondary text such as footer links or less important details. |
| Button MD | `{typography.button-md}` | The standard text style for all primary and secondary buttons. |
| Caption MD | `{typography.caption-md}` | The smallest text size, used for legal disclaimers, photo captions, or tertiary info. |
| Link MD | `{typography.link-md}` | The style for navigation links, matching the default body text size. |
| Numeric MD | `{typography.numeric-md}` | Any figure the user reads or compares: balances, amounts, dates, counts, file sizes. |
| Numeric SM | `{typography.numeric-sm}` | Figures inside dense tables and secondary metadata rows. |

**Typography Principles:**
1.  **One Sans, One Mono:** `Geist` for all text, `Geist Mono` for all figures. This rule is absolute — never add a third family, and never set prose in the mono.
2.  **Establish Clear Hierarchy:** Combine size and color to guide the user's eye. A `{typography.display-xl}` heading in `{colors.ink}` should be the most prominent text element.
3.  **Prioritize Readability:** All body copy (`{typography.body-md}`, `{typography.body-lg}`, etc.) maintains a generous line height of `1.5` to ensure comfortable reading on dark backgrounds.
4.  **Minimal Weight Variation:** The system favors changes in size, tracking, and color over font weight to create contrast. Body text is `{fontWeight: 400}`; display text and buttons step up only to `{fontWeight: 500}`. Never reach for 700+ — heavy weights read as loud, and this brand is not loud.
5.  **Tracking Tightens With Size:** Geist is drawn for negative tracking at display sizes. Apply `-0.03em` at `{typography.display-xl}`, easing to `0` by `{typography.body-lg}`. Never apply positive letter-spacing; wide-tracked uppercase labels are banned (see Principle 6).
6.  **No All-Caps:** Text should be set in sentence case or title case as appropriate. Avoid using `text-transform: uppercase` as it conflicts with the restrained nature of the typeface.

## Component Patterns
Components in the Mercury system are minimalist, functional, and built on the core token set. They prioritize clarity and ease of use, with subtle animations providing feedback without being distracting.

**Buttons**
Primary and secondary buttons are the main interactive elements for significant user actions. They are always rendered with a `{rounded.pill}` shape.
*   `button-primary`: The primary call-to-action. It uses a solid `{colors.primary}` background with `{colors.on-primary}` text. On hover, the background brightens to `{colors.primary-bright}` over `{motion.duration-fast}`. It should be used for the single most important action on a page. The cursor must be `pointer`.
*   `button-secondary`: Used for important, but not primary, actions like "Launch Demo". It has a `{colors.accent-pale-blue}` background with `{colors.primary}` text. This creates a visually lighter button. On hover, its background changes to `{colors.on-primary}` to provide clear feedback. The transition uses `{motion.duration-fast}` and `cursor: pointer` is required.

**Input Fields**
Text inputs are designed to be subtle yet clear.
*   `input-text`: The email input in the hero is a prime example. It has a translucent `{colors.paper}` background and a `{rounded.pill}` shape to match the buttons. It uses `{typography.body-md}` for text entry. By default, it has no visible border. The cursor must be `text`.
*   On focus, the `input-text-focus` state is activated. A `1px` border appears in the `{colors.primary}` color. This change provides a clear, but not distracting, indication of the active field. No box-shadow is used for focus; the border color shift is the only indicator.

**Navigation Links**
Navigation is clean and text-based.
*   `nav-link`: These are used in the main header. They consist of simple text styled with `{typography.link-md}` and colored `{colors.link}`. They have generous padding of `{spacing.xs}` and `{spacing.md}` to create large, easy-to-click targets. On hover, the text color changes to `{colors.ink}` and a `{colors.paper}` background fades in over `{motion.duration-fast}`. All navigation links must use `cursor: pointer`.

**Cards**
Cards are the standard container for grouping related content.
*   `card`: A card is a simple rectangle with a `{colors.paper}` background and `{rounded.lg}` corners. This allows it to stand out against the main `{colors.canvas}` background without resorting to shadows. Padding inside a card should be generous, typically `{spacing.lg}`. This pattern is exemplified by the cookie consent banner.

## Layout & Spacing
The Mercury layout is governed by a strict, rhythmic spacing scale that ensures consistency and visual harmony. The scale is based on a 4px and 8px grid system, and all padding, margins, and gaps between elements must use a `{spacing.*}` token. Arbitrary pixel values are forbidden.

*   **Rhythmic Scale:** The scale ranges from `{spacing.xxs}` (4px) for micro-adjustments within components to `{spacing.section}` (72px) for separating major page sections. Common values like `{spacing.md}` (16px) and `{spacing.lg}` (24px) are used for component padding and inter-element spacing.
*   **Grid System:** The main content resides in a centered column with a maximum width to ensure readability on large displays. Within this column, layouts are often simple single or two-column grids. On smaller viewports, these grids stack vertically. Gaps in the grid must use tokens from the spacing scale, typically `{spacing.xl}` or `{spacing.xxl}`.
*   **Sectional Rhythm:** Pages are composed of horizontal sections stacked vertically. Each section is separated by a consistent margin of `{spacing.section}`. This clear separation helps users parse the page structure and creates a calm, ordered flow. The hero area is typically the largest section, followed by content blocks of varying heights.
*   **Whitespace is Active:** The design uses negative space generously. Do not crowd elements. Ample space around typography and UI controls is crucial for the clean, premium aesthetic. Padding within components like cards (`{spacing.lg}`) and inputs (`{spacing.sm} {spacing.lg}`) should feel spacious.

## Do's and Don'ts

**Do's**
1.  **Do** build all user interfaces from the core color palette: `{colors.canvas}`, `{colors.paper}`, `{colors.ink}`, `{colors.ink-soft}`, and `{colors.primary}`.
2.  **Do** set everything in `Geist`, reserving `Geist Mono` for figures via the `numeric-*` tokens. Self-host both with `@fontsource-variable/geist` — never `<link>` to `fonts.googleapis.com` in production.
3.  **Do** use only tokens from the `{spacing.*}` scale for all padding, margins, and layout gaps to maintain a consistent rhythm.
4.  **Do** ensure every single clickable element—buttons, links, tabs—has its cursor set to `pointer`. Text inputs must use `cursor: text`.
5.  **Do** use `{colors.primary}` exclusively for the most important call-to-action on a screen to maximize its visual power.
6.  **Do** create separation and hierarchy using color (`{colors.paper}` on `{colors.canvas}`) and space (`{spacing.section}`), not shadows.
7.  **Do** make all interactive state changes (hovers, focus) transition smoothly using `{motion.duration-fast}` and `{motion.ease-standard}`.
8.  **Do** ensure all touch targets meet a minimum size of 44x44px, using padding tokens like `{spacing.sm}` and `{spacing.md}` to increase hit areas.

**Don'ts**
1.  **Don't** ever add a box-shadow to any element. The design system is strictly flat. Always reference `{shadows.none}` if a shadow property is needed.
2.  **Don't** ever leave the browser-default arrow cursor on a clickable element like a link, button, or tab.
3.  **Don't** introduce new colors that are not already defined in the `{colors.*}` token set. Reuse beats invention.
4.  **Don't** introduce a second sans or a serif for headlines, and don't set prose, labels, or buttons in `Geist Mono`. The mono is for figures only.
5.  **Don't** use arbitrary values for spacing or sizing. If a token doesn't exist in the `{spacing.*}` or `{rounded.*}` scales, choose the closest one.
6.  **Don't** use `{colors.primary}` for decorative purposes, secondary text, or more than two CTAs in the same viewport.
7.  **Don't** underline navigation links or text links by default; reserve underlines for hover states on secondary links (like in the footer).
8.  **Don't** create visually noisy interfaces. The aesthetic is minimalist; when in doubt, add more whitespace using `{spacing.*}` tokens.

## Responsive Behavior
The Mercury design system is fully responsive, ensuring a seamless experience from large desktops down to mobile devices. Layouts fluidly adapt by simplifying, stacking, and reflowing content.

| Breakpoint | Range | Behavior |
| :--- | :--- | :--- |
| Mobile | <480px | Single-column layout. Main navigation collapses into a hamburger menu. Hero text (`{typography.display-xl}`) scales down significantly. Grids stack vertically. Spacing tokens may map to smaller values. |
| Mobile-Large | 480–767px | Primarily single-column. Increased font sizes and spacing compared to mobile. Some simple two-column layouts for secondary content may appear. |
| Tablet | 768–1023px | Content width increases. Two-column grids become more common. The main navigation may still be collapsed. Hero text is larger. Touch targets remain a high priority. |
| Desktop | 1024–1279px | The standard desktop experience. The main navigation is fully visible horizontally. The main content area is constrained to a maximum width for readability. |
| Desktop-Large | ≥1280px | The layout remains constrained in the center, with generous margins on either side. The abstract background graphics may become more expansive. No significant layout changes from Desktop. |

**Touch Targets:**
All interactive elements must have a minimum touch target size of 44x44px on mobile and tablet breakpoints. This is achieved by applying sufficient padding (e.g., `{spacing.sm}` vertically and `{spacing.md}` horizontally) to links and buttons, even if the visible icon or text is smaller.

**Component Behavior:**
*   **Navigation:** The primary navigation bar (`nav-link` components) collapses into a hamburger-icon-triggered menu on `Tablet` and smaller breakpoints.
*   **Hero Section:** The `{typography.display-xl}` text scales down gracefully with the viewport width. The CTA buttons (`button-primary`, `button-secondary`) may stack vertically on the smallest `Mobile` screens.
*   **Grids:** Any multi-column grid layout must stack into a single, ordered column on `Mobile-Large` and smaller breakpoints. The order of stacked content should maintain a logical reading flow.

## Iteration Guide
When building or iterating on a UI component in the Mercury style, follow these steps to ensure consistency and brand alignment.

1.  **Establish the Surface:** Begin by defining your component's background. Is it part of the main page flow (`{colors.canvas}`) or is it a contained module that needs separation (`{colors.paper}`)?
2.  **Set the Typographic Hierarchy:** Choose the correct typography tokens for your text. Use `{typography.display-lg}` or `{typography.display-md}` for titles and `{typography.body-md}` for content. It is all `Geist` — separate the levels with size, negative tracking, and a 400→500 weight step, not a different typeface. Route every figure through `{typography.numeric-md}`. Color text with `{colors.ink}` or `{colors.ink-soft}`.
3.  **Define the Rhythm and Spacing:** Use the `{spacing.*}` scale exclusively to set all padding and margins. Start with `{spacing.lg}` for internal padding and `{spacing.xl}` for spacing between elements, and adjust from there. Do not use custom pixel values.
4.  **Identify and Style the Primary Action:** Find the most important action within your component and apply the `button-primary` style. Use `{colors.primary}` as the background and ensure it has `cursor: pointer`. If there are secondary actions, use the `button-secondary` pattern.
5.  **Implement Interactive States:** For every interactive element (buttons, links, inputs), define a hover and focus state. Hovers should provide clear visual feedback (e.g., `backgroundColor: {colors.primary-bright}`) and all state changes must be animated over `{motion.duration-fast}`. Focus states on inputs must use a `{colors.primary}` border.
6.  **Adhere to the Flat Design:** Verify that no element uses a box-shadow. All elevation and grouping must be achieved with color and space. Reference `{shadows.none}` explicitly where needed.
7.  **Check for Cursors:** Manually check that every single link, button, and other clickable element has `cursor: pointer`. Ensure all text fields have `cursor: text`.
8.  **Responsive Pass:** View your component at each of the defined breakpoints (Mobile, Tablet, Desktop). Ensure layouts stack correctly, text remains readable, and touch targets are sufficiently large on smaller screens.
9.  **Final Review Against Rules:** Before completing, read through the "Do's and Don'ts" section. Check your work against each rule, especially those concerning color usage, typography, spacing, and flatness.

## Suggested Packages

Packages that help implement this skill well. Install them with your package manager (examples use pnpm).

- **@fontsource-variable/geist** — Self-hosted Geist variable sans, the brand typeface. `pnpm add @fontsource-variable/geist`
- **@fontsource-variable/geist-mono** — Self-hosted Geist Mono variable, for tabular figures. `pnpm add @fontsource-variable/geist-mono`
- **clsx** — Tiny utility for conditionally joining class names. `pnpm add clsx`
- **tailwind-merge** — Merge Tailwind classes without style conflicts. `pnpm add tailwind-merge`
- **class-variance-authority** — Type-safe component style variants (CVA). `pnpm add class-variance-authority`
- **shadcn** — Accessible, unstyled UI primitives you copy into the project. `pnpm dlx shadcn@latest add`
