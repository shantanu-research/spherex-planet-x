---
name: SPHEREx Sky Flipbook
description: A NASA-mission-page landing in the Space Apps deep blue palette; hairlines and tables carry structure, yellow marks action only.
colors:
  void: "#07173F"
  panel: "#0A1E4E"
  panel-2: "#0D2659"
  bar-deep: "#04102E"
  line: "#22407A"
  line-strong: "#3D5E9E"
  text: "#DCE5F5"
  text-strong: "#FFFFFF"
  muted: "#B3C2DE"
  accent: "#EAFE07"
  link: "#7CC0FF"
  blue: "#0960E1"
  red: "#FF6A3D"
  sim-red: "#8F2A0D"
typography:
  display:
    fontFamily: "Fira Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(40px, 6.4vw, 84px)"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Fira Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(28px, 3.6vw, 46px)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Fira Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Overpass, Segoe UI, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Overpass, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  button:
    fontFamily: "Fira Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1
rounded:
  sm: "4px"
  full: "50%"
spacing:
  hairline-cell: "24px"
  grid-gap: "20px"
  actions-gap: "14px"
  gutter: "clamp(20px, 5vw, 72px)"
  max: "1240px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.void}"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "12px 24px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.text-strong}"
    textColor: "{colors.void}"
  button-ghost:
    textColor: "{colors.text-strong}"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "12px 24px"
    height: "48px"
  button-ghost-hover:
    backgroundColor: "{colors.panel}"
  notice-bar:
    backgroundColor: "{colors.bar-deep}"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    padding: "9px 20px"
  site-header:
    backgroundColor: "{colors.void}"
    textColor: "{colors.text-strong}"
    padding: "12px 20px"
  chip:
    textColor: "{colors.text-strong}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
    height: "44px"
  chip-hover:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.text-strong}"
  team-card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    padding: "26px 24px 24px"
  flag-simulated:
    backgroundColor: "{colors.sim-red}"
    textColor: "{colors.text-strong}"
    padding: "4px 10px"
  site-footer:
    backgroundColor: "{colors.bar-deep}"
    textColor: "{colors.muted}"
    padding: "56px 20px 32px"
---

# Design System: SPHEREx Sky Flipbook

## Overview

**Creative North Star: "The Mission Page"**

A NASA mission page in the Space Apps palette: utility bar, header, hero with a captioned real image, a plain facts table, prose bands, a story list and a mega footer. Structure comes from hairline rules and tables on a deep blue ground. Surfaces are flat. The real SPHEREx blink is the only image and it leads the first screen.

Density is calm and editorial: long measure capped at 68ch, generous band padding (clamp 56-104px), content centered in a 1240px column. Yellow is reserved for action and focus so it reads as "click here" wherever it appears.

**Key Characteristics:**
- Deep blue ground with two panel steps and two hairline strengths
- Neon yellow only for primary action, focus ring, active nav underline
- Tables, dividers and text columns instead of cards for structure
- Fira Sans display over Overpass body
- No shadows; one authored motion (sections rise in once)

## Colors

A single-hue navy field with white and pale-blue text, one yellow action color, one blue interaction color, and a dark red used for one flag.

### Primary
- **Action Yellow** (accent): primary button fill, the 3px focus outline, skip-link fill, active nav underline on hover. Nothing else.

### Secondary
- **Link Sky** (link): inline links, track "who" line, member track line.
- **Interaction Blue** (blue): chip hover fill and text selection background.

### Tertiary
- **Simulated Rust** (sim-red): fill of the "Simulated" tag only, with white text. A darker value than `red`.

### Neutral
- **Void Navy** (void): page ground, hero, closing, header (at 94% alpha), button text on yellow.
- **Panel Navy** (panel), **Raised Panel** (panel-2): alternate bands and team cards; panel-2 is the list-row hover.
- **Bar Deep** (bar-deep): notice bar and footer, darker than the ground.
- **Hairline** (line), **Strong Hairline** (line-strong): row and cell dividers; strong hairline opens each table or list and outlines frames, tags and ghost buttons.
- **Text** (text), **Strong Text** (text-strong), **Muted** (muted): body, headings and key values, captions and secondary copy.

`red` (#FF6A3D) is declared in `:root` but not used by any rule in landing.css.

### Named Rules
**The Yellow Is Action Rule.** Yellow marks the primary action, focus and active-nav only. It never decorates headings, borders or data.

**The Hairline Opens Rule.** Every table or list begins with a strong hairline and separates rows with a regular hairline.

## Typography

**Display Font:** Fira Sans (with Segoe UI, system-ui, sans-serif)
**Body Font:** Overpass (with Segoe UI, system-ui, sans-serif)
**Label/Mono Font:** Fira Code is loaded and declared as `--mono` but no rule in landing.css uses it.

**Character:** Humanist and technical, in the NASA mission-page register. Heavy weight is saved for the hero.

### Hierarchy
- **Display** (900, clamp 40-84px, 1, -0.03em): the single hero h1.
- **Headline** (700, clamp 28-46px, 1.1, -0.02em, max 22ch): band and closing h2.
- **Title** (700, 20-22px, 1.2-1.25): track h3, member h3, test-field name, principle term (21px).
- **Body** (400, 17px; 16px below 620px, 1.6): prose capped at 68ch. Lead paragraph is clamp 18-21px in strong text.
- **Label** (400-600, 13-15px): notice bar (13px), captions and tags (14px), footer links (15px), chips (600, 15px).

### Named Rules
**The Muted Support Rule.** Supporting copy (captions, band intros, legal) uses Muted; claims and key values use Strong Text.

## Layout

One centered column (max 1240px) inside a responsive gutter (clamp 20-72px). Hero is a two-column grid (1.15fr / 0.85fr) with the figure right-aligned at max 520px. Facts and tracks are four equal columns divided by left hairlines with 24px cell padding; team is four columns with 20px gap; idea and limits are 1.1fr / 0.9fr two-column grids. Test-field rows are a four-part grid: name (15rem), reason, tag, "Open".

Breakpoints: at 1040px hero, idea and limits collapse to one column, facts, tracks and team go to two, nav wraps below the brand and scrolls horizontally, field "Open" hides. At 620px everything goes to one column and hero and closing buttons go full width. Sticky header, scroll-padding-top 84px.

## Elevation & Depth

Flat. No box-shadows exist in the stylesheet. Depth is tonal: Void ground, Panel alternate bands, Raised Panel on row hover. The sticky header uses 94% alpha with a 10px backdrop blur over a hairline bottom border.

### Named Rules
**The No-Shadow Rule.** Separate with a hairline or a tonal step, never with a shadow.

## Shapes

Square and ruled. Buttons and chips use a 4px radius; the figure frame, tags, team cards, rows and facts are square. Only the brand patch and member avatars are circles (50%). The hero image sits in a 1px strong-hairline frame on black with 8px padding, pixelated rendering preserved.

## Components

### Notice Bar
Full-width Bar Deep strip above the header, 13px Muted text with a Strong Text 600 lead phrase, hairline bottom border.

### Header
Sticky, Void at 94%, flex row: brand (patch 48px circle plus 19px 700 name), five section links (15px, 2px yellow underline on hover), small primary button.

### Buttons
- **Shape:** 4px radius, 48px min height, 2px border, 700 Fira Sans 16px, optional 18px arrow icon that slides 4px on hover.
- **Primary:** yellow fill, Void text; hover turns white.
- **Ghost:** 2px strong-hairline border, white text; hover brightens border and fills Panel.
- **Small:** 42px min height, 10px 18px padding, 15px.

### Hero Figure
Real-data GIF in a hairline frame with a 14px Muted caption; lead words in Strong Text 600.

### Facts Table
Definition list in four cells under a strong top hairline; 14px Muted term over a 17px 500 Fira Sans Strong Text value.

### Principles List
Definition list of rows with a 7.5rem 700 21px term column and Text-colored description, hairline between rows.

### Tracks Columns
Ordered list in four text columns divided by hairlines (not cards); 20px title, 16px Link Sky "who" line, 16px body.

### Test-Field Rows
Each row is a whole-row link on a Panel band: 22px name, 16px reason, 14px outlined tag, "Open" label (underlined on hover). Row hover is Raised Panel. The Simulated tag swaps to Simulated Rust fill.

### Team Cards
Panel fill, 1px hairline, square. 68px circular avatar with initials, 22px name, 14px Link Sky track, 16px blurb, then chips for LinkedIn and Email (44px, 4px radius, Blue fill on hover, inline SVG icons).

### Limits
Prose column beside a hairline list with 16px row padding.

### Closing
Left-aligned headline, primary plus ghost buttons, 14px Muted note.

### Footer
Bar Deep, strong top hairline, three-column grid (brand and logo, Project links, Data and sources) with 17px 700 column headings, then a 13px Muted legal line under a hairline.

## Do's and Don'ts

### Do:
- **Do** use Action Yellow only for primary actions, focus outline (3px, 3px offset) and active nav underline.
- **Do** build structure from hairlines, tables and text columns on the navy ground.
- **Do** keep the "Simulated" tag in Simulated Rust with white text.
- **Do** keep the first load content visible without JS and honor prefers-reduced-motion.

### Don't:
- **Don't** add box-shadows; the system is flat.
- **Don't** use cards for structure; team members are the only panelled items.
- **Don't** use yellow for decoration, headings or borders.

## Not canonized

Defects and drift present in the build, not rules for future surfaces: `--mono` and `--red` are declared but unused; the direction contract promised Fira Code for data values and a "Watch the walkthrough" button, neither exists in the build (it ships "Try a test field"). Literal `#04102E`, `#8F2A0D`, `#000` and `#07173F` appear in rules outside the `:root` tokens.
