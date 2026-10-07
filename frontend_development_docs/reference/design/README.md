# Design references

These four screenshots of Harvey define how Strata should look and feel. Match their **layout, density, typography, hierarchy and restraint**. Do **not** copy Harvey's name, logo, "H" mark, fonts, illustrations or wording. Strata has its own wordmark and content. The written rules are in `frontend_spec.md` §17. If a screenshot and §17 disagree on a value, §17 wins; the screenshots win on overall feel.

## 01 — `01-dashboard-command-center.webp` → Overview, app shell
What to take:
- **Shell:**
  - a near-black sidebar with the wordmark top-left and search and bell icons beside it;
  - an icon-plus-label nav, with the active item as a slightly lighter rounded row;
  - muted section labels ("Apps", "Recents", "Spaces"), which map to our "Knowledge base", "Recents" and "Coming soon";
  - a person or company chip pinned to the bottom.
- **Page header:** a large serif title on the left. Secondary actions and one solid black primary button on the right; ours is the RunSelector plus page actions.
- **Info strip:** a full-width white card with a small monogram icon and one sentence. This becomes the Overview's actionable line.
- **Metric cards:**
  - a big serif number with a small green delta, and a caption under it;
  - small outlined select controls with chevrons at the top-right;
  - a footer legend and icon actions under a hairline divider.
- **Data marks:** dense hairline vertical bars, and dotted or hatched bars for comparison. This is the style for our funnel, noise and mini-bars, built in CSS only (§17.6).
- **Horizontal bars** ("Top power users"): a label on the left, a textured dark bar, and the value at the end. This is the model for our **funnel**.
- **Color discipline:** monochrome, with color reserved for meaning. A green delta shows positive, and a muted brown "Needs attention" maps to our muted amber "review".

## 02 — `02-agent-builder-split-view.webp` → What-if studio, document reader, icon rail
What to take:
- **Collapsed icon rail** sidebar (about 64px). The reader collapses to it automatically.
- **Split view:** a conversational or step list on the left and a document or editor surface on the right, with a hairline divider. This is the model for What-if (presets and section picker on the left, editor on the right) and for the reader plus findings rail.
- **Progress list** ("Processing 3 clarifying responses"): steps with completed bullets and a spinner on the current step. This is the model for the **StageStepper**.
- **Field rows** ("Schedule:", "Sources:", "+ Add source", "+ Add file"): label–value rows and muted "+ Add …" ghost actions. This is the exact pattern for `FutureCue` `inline-add` (§18).
- **Document typography:** a serif or neutral document body with comfortable line height and a restrained toolbar above it.
- **Header actions:** a document title with an edit affordance, and a black "Save" primary plus an overflow menu.

## 03 — `03-review-table.png` → Changes ledger, Impact matrix, Documents tables, vertical page
What to take:
- **Breadcrumb:** the parent in grey, a chevron, then the current page in ink.
- **Toolbar:** icon-plus-label ghost actions separated by thin vertical dividers ("Add files | Auto group | Column Builder | Manage columns"). Our real actions and future cues (e.g. "Add column", "Export") live here.
- **Table:**
  - a checkbox column and a row-number column;
  - headers with an icon, a label, and filter and sort icons;
  - column dividers;
  - cells that truncate with an ellipsis.
- **Group rows:** a light grey band with a folder icon, the group name in medium weight, "· 4 files" in grey, and a chevron. Use these for documents grouped by vertical and for findings grouped by verdict.
- **Status pills:** a soft tinted background with matching text and small radius (Disputed red, Resolved green, Indeterminate grey). This is exactly our VerdictPill and DocStatusPill style.

## 04 — `04-space-home-cards-tabs.png` → Documents board, vertical page, agency page, Regulations overview
What to take:
- **Header:** a small grey caption above a serif title ("Client matter #" → our run or vertical caption), a small square monogram, and a neutral tag chip ("External" → our "Simulated" or "Not monitored" tags).
- **Segmented tabs:** the active tab is a white pill and inactive tabs are grey text. Use them for agency "Rules in force / Activity", Radar tabs and Company tabs.
- **Sections:** a sans title, a grey one-line subtitle, and a "View all" link on the right.
- **Cards:** light, soft-cornered cards with a small icon in a square, a title, and a meta line ("214 files · 12"). This is the model for vertical cards, document cards and agency cards. The dashed variant of this card is the "Add agency" future cue.
- Ignore the faint header wash and the collaboration cursors ("Firm", "Client"). Strata uses no gradients, and has no multiplayer in v1.
