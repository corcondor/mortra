# MORTRA worlds v2

## Scope

Refresh the existing mortra.ai Next.js application. No new solver or research
mechanism. The user subsequently authorized production publication after
validation, superseding the original local-only instruction.

## Visual specification

- White, charcoal, restrained mint / coral / gold / blue game semantics.
- System sans-serif, zero letter spacing. H1 96px desktop / 64px mobile;
  section titles 34px / 26px. Body 14-15px.
- Sections are open full-width bands with a centered single content column.
- 112px desktop / 88px mobile section padding. Board at most 480px square.
- Before/after, evidence, process, and footer are vertical, not side-by-side.
- User's later whitespace/single-column instruction supersedes the earlier
  generated concept's multi-column comparisons and data tables.
- Initial/final selectors, 44px icon buttons, range control, native selects,
  keyboard-focusable board, optional motion, no auto-started replay.
- Game drawings are literal exported grid data. Do not substitute generated
  illustrations for actual experimental states.

## Data boundary

`web/public/mortra/runs` is the canonical export. The existing Next application
serves an identical generated mirror under `public/mortra/runs`. Prebuild
verifies SHA-256 hashes and synchronizes that mirror.

Manual play implements MicroGame.step only. It does not choose actions.
Recorded play displays stored Python states and actions. No browser
fixed-field solver is present in the new homepage execution path.

Historical product presentation is retained under research/archive. Suspect
earlier claims remain Research-only and are labelled AUDIT / EXPERIMENTAL.
