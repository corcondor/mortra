# MORTRA interface protocol based on Apple HIG

Updated: 2026-08-31

This document is the required design gate for MORTRA product and public-site
work. Read the current Apple Human Interface Guidelines before implementation,
then use this protocol to turn them into MORTRA-specific decisions.

## Primary sources

- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Design principles](https://developer.apple.com/design/human-interface-guidelines/design-principles)
- [Layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- [Typography](https://developer.apple.com/design/human-interface-guidelines/typography)
- [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- [Feedback](https://developer.apple.com/design/human-interface-guidelines/feedback)
- [Motion](https://developer.apple.com/design/human-interface-guidelines/motion)
- [Pointing devices](https://developer.apple.com/design/human-interface-guidelines/pointing-devices)
- [Text fields](https://developer.apple.com/design/human-interface-guidelines/text-fields)
- [Menus](https://developer.apple.com/design/human-interface-guidelines/menus)
- [Onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding)
- [Offering help](https://developer.apple.com/design/human-interface-guidelines/offering-help)
- [Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)

## Product purpose

MORTRA helps a person express a mathematical problem, inspect how its typed
structure moves through proof engines, and receive a problem, proof, figure,
and certificate. The interface must reduce the distance between mathematical
intent and a verifiable result. It must not make the user learn MORTRA's
internal architecture before they can solve a problem.

## Interaction principles

1. **Agency**: a person can run, pause, resume, step, edit, reset, and recover.
   Long-running work keeps its visible job identity and status.
2. **Familiarity**: the advanced surface behaves like a high-quality terminal
   and editor. Commands use `/solve`, `/combine`, and `/draw`; standard pointer,
   keyboard, focus, copy, and disclosure behavior is preserved.
3. **Simplicity**: show one primary command, the source, its rendered
   mathematics, and the current state. Hide secondary commands until `/`, hover,
   focus, or a deliberate hold requests them.
4. **Feedback**: editing updates the TeX preview immediately; execution reports
   accepted input, phase, elapsed time, open obligations, result, and errors in
   the same context.
5. **Responsibility**: distinguish live execution, stored replay, and fallback
   data. Never portray a decorative animation as real inference.
6. **Flexibility**: mouse, keyboard, touch, narrow screens, reduced motion, and
   increased contrast must retain the complete workflow.
7. **Craft**: typography, optical alignment, focus states, animation timing, and
   mathematical notation are part of correctness.

## Visual hierarchy and material

- Mathematical source and rendered output are the content layer.
- Navigation, command controls, transient menus, and contextual help may use a
  single Liquid Glass interaction layer above the content.
- Glass adapts to the content beneath it, keeps a visible edge, and maintains
  readable contrast. Avoid stacked glass-on-glass surfaces.
- Use color to reinforce type or status, never as the only signal. Pair it with
  labels, shape, line treatment, or icons.
- Small interface text uses regular or medium weight. Monospace is reserved for
  source, commands, identifiers, hashes, and telemetry.

## Information geometry visualization

The exploration graph is not a generic neural-network metaphor. It represents
a typed proof state:

- a node has a semantic type, engine, confidence or verification status,
  residual, and frontier depth;
- an edge is a named morphism with a direction and preserved invariant;
- distance reflects representation or proof-state distance, not decoration;
- node radius may encode obligation mass; edge brightness may encode active
  transport; color identifies stable mathematical roles;
- the graph and terminal read from the same state so a highlighted command,
  node, trace line, and certificate step agree.

## Contextual command help

- Typing `/` opens a command list next to the prompt.
- Hover, keyboard focus, or a deliberate hold reveals a short, actionable
  description next to the command.
- Help remains optional, dismissible, and specific to the current action.
- A user can choose a command without memorizing syntax.
- Tooltips stay short; examples belong in the command detail panel.

## Required verification

Before merging a UI change:

1. Confirm the primary workflow works with mouse and keyboard.
2. Check desktop and mobile widths, including safe areas and text reflow.
3. Verify TeX input and preview, errors, loading, completion, and resume states.
4. Verify contextual help is available without obscuring the current task.
5. Check color contrast and that state is not communicated by color alone.
6. Enable reduced motion and confirm no information disappears.
7. Capture screenshots and inspect them against the active design concept.
