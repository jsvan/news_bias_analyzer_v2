# Design

## Identity

Newsroom-wire-service instrument, not a SaaS dashboard. The site is a mirror for the global
information landscape: calm, evidentiary, restrained. It presents divergence; it never accuses.

Mood: newsroom light — bright, paper-white, editorial. Cool paper, not warm cream (the warm
cream/sand band is the AI-generated default; this palette is deliberately cool-neutral instead).

## Color

Strategy: **Restrained** base (product default) with one **Committed** surface — the four-archetype
data-color system (Hero / Victim / Villain / Threat), which is structural, not decorative: it is
literally the categories the power/moral quadrant measures.

All values authored in OKLCH; hex given for direct use in the MUI theme (MUI's internal color
utilities — `alpha()`, `decomposeColor()` — don't parse `oklch()`, so the theme palette uses hex).
Raw `oklch()` strings are fine in plain CSS / recharts SVG props, which bypass MUI's color math.

| Token | OKLCH (source of truth) | Hex (for MUI/JS) | Use |
|---|---|---|---|
| `paper` | oklch(0.975 0.004 250) | `#F6F7F9` | page background — cool off-white, not cream |
| `surface` | oklch(0.99 0.002 250) | `#FDFDFE` | card/panel background |
| `surface-sunken` | oklch(0.955 0.005 250) | `#EEF0F3` | toolbars, filter bars, second neutral layer |
| `ink` | oklch(0.20 0.012 260) | `#171A20` | primary text |
| `ink-muted` | oklch(0.42 0.014 260) | `#5B6270` | secondary text — verified ≥4.5:1 on `paper`/`surface` |
| `border` | oklch(0.88 0.006 250) | `#DEE1E6` | dividers, hairlines |
| `accent` (Telegraph teal) | oklch(0.42 0.086 199) | `#0E6E78` | links, primary actions, current selection — UI only, never data |
| `accent-hover` | oklch(0.36 0.086 199) | `#0A5960` | hover/active state of accent |
| `hero` (archetype: high power, high moral) | oklch(0.5 0.11 152) | `#1E7A4C` | Hero quadrant, positive divergence |
| `victim` (low power, high moral) | oklch(0.44 0.13 320) | `#7C3F8C` | Victim quadrant |
| `villain` (high power, low moral) | oklch(0.46 0.16 22) | `#AC2A3C` | Villain quadrant — deliberately oxblood/crimson, not flag-red |
| `threat` (low power, low moral) | oklch(0.58 0.13 65) | `#B06A0E` | Threat quadrant |

**No red/blue pair anywhere carries a "sides" meaning.** The four archetype colors are a 4-way
semantic system (power × moral), never a 2-way left/right one. Cross-source and cross-country
comparisons use a rotating categorical palette assigned by first-appearance order — never a fixed
country→color map (the old `USA=red / UK=blue` table read as a partisan-flag mapping and is
removed). Categorical sequence: teal `#0E6E78`, amber `#B06A0E`, plum `#7C3F8C`, forest `#1E7A4C`,
slate-blue `#3C5A78`, terracotta `#B0522F`, olive `#6E7A1E`, rose `#9C4066`, indigo `#463C8C`,
graphite `#5B6270` — repeat/lighten past 10.

## Typography

Display/body contrast pair (justified: the front-door hero earns brand-quality craft; the dashboard
itself stays product-register with the sans doing all the work).

- **Display — Newsreader** (variable, italic + optical-size + weight axes; built to read as
  newsprint rather than as generic "elegant editorial" — deliberately not Fraunces/Playfair, which
  have become the default AI-generated-editorial serif). Masthead wordmark, hero headline, the
  section dividers between major dashboard views. Never in buttons, labels, or data.
- **UI/body — IBM Plex Sans.** Everything else: nav, cards, labels, paragraphs, tooltips.
- **Data — IBM Plex Mono**, tabular figures. Every numeric readout (power/moral scores, percentiles,
  mention counts, p-values) — the mono treatment is what makes the UI read as an instrument, not a
  content site.

Fixed rem scale (product register — no fluid clamp() except the one hero headline):

| Token | Size | Use |
|---|---|---|
| `text-xs` | 0.75rem / 12px | captions, chip labels |
| `text-sm` | 0.875rem / 14px | secondary body, filters |
| `text-base` | 1rem / 16px | body |
| `text-md` | 1.125rem / 18px | card subtitles |
| `text-lg` | 1.375rem / 22px | card/section headers |
| `text-xl` | 1.75rem / 28px | page title |
| `text-2xl` | 2.25rem / 36px | masthead wordmark |
| `text-hero` | clamp(2.25rem, 4vw + 1rem, 3.75rem) | front-door hero headline only — under the 6rem ceiling |

Letter-spacing on Fraunces display sizes: -0.015em (well above the -0.04em floor). Body: normal.
`text-wrap: balance` on all h1–h3; `text-wrap: pretty` on the hero paragraph.

## Layout

- Masthead header (new) replaces the bare `<h4>` title row: wordmark in Fraunces, a one-line
  standing subhead, utility icons (refresh/export) right-aligned.
- Section navigation (the six dashboard views) restyled as an editorial underline nav, not filled
  MUI pill tabs — thin bottom rule, active state is a heavier underline + ink color, not a filled
  background.
- Second neutral layer (`surface-sunken`) for filter bars/toolbars, distinguishing them from content
  cards on `surface`.
- Dense data (Entity Summary, Notable Entities) moves from repeated identical card grids to a
  row-list treatment: rank, archetype-color dot, name, type tag, power/moral in mono, mention count
  — denser, avoids the identical-card-grid pattern, fits product register's density permission.
- Responsive: MUI Grid breakpoints stay (structural collapse), no fluid-layout tricks.

## Components

- **No side-stripe borders.** The existing `borderLeft: 4px solid <archetype color>` pattern on
  "Notable Entities" / "Entity Summary" / newspaper-topic cards is banned outright — replaced by a
  small leading archetype-color dot + full 1px `border` token, or removed in favor of the row-list
  above.
- Cards: 10px radius, 1px `border` hairline, no elevation shadow at rest — a 1px border reads more
  "instrument" than a drop shadow. A subtle shadow only appears on hover for genuinely interactive
  cards (newspaper chips, clickable summary rows).
- Chips/pills: full radius, used for filters and archetype/country tags — never for primary actions.
- Buttons: 6px radius (not the bubbly MUI default), accent teal fill for primary, ink outline for
  secondary.
- Every interactive element gets default/hover/focus/active/disabled states from the accent and
  ink-muted tokens — no ad hoc one-off colors.
- Loading: skeletons for chart/card content, not center-page spinners buried mid-layout (the
  full-page spinner on first load is fine; in-place refreshes get inline skeletons).

## Motion

- 150–200ms, ease-out-quart, on hover/selection/tab-underline transitions.
- One deliberate load sequence: the front-door hero fades/rises in on mount (respects
  `prefers-reduced-motion`: crossfade only, no rise).
- No orchestrated per-section reveal-on-scroll choreography — this is a tool, not a scroll story.

## Accessibility

WCAG AA. `ink-muted` (#5B6270) checked at ≥4.5:1 against both `paper` (#F6F7F9) and `surface`
(#FDFDFE). All four archetype colors checked at ≥3:1 against `paper` for use as chart fill (large
graphical elements) and ≥4.5:1 where used as text (mono score readouts use `ink`, not archetype
color, for exactly this reason — color marks the category via a dot/badge, text stays high-contrast
ink). `prefers-reduced-motion` respected everywhere motion appears.

## Assets — documented absence

No logo mark exists. The masthead uses a typographic wordmark (Fraunces) instead of an image logo —
no asset dependency. Favicon is currently the default Vite SVG placeholder; replaced with a small
authored SVG mark (a four-point compass/quadrant glyph echoing the power/moral axes) — code, not a
sourced asset. No photography or illustration is used anywhere; the hero's visual anchor is a live
miniature of the real power/moral quadrant chart, built from actual snapshot data, not a stock image
or placeholder graphic. If a real brand mark is designed later, it drops into the masthead in place
of the wordmark with no layout change.
