# MORTRA contributor protocol

## Product interface changes

Before changing MORTRA's public site or product workspace, read
`docs/design/MORTRA-HIG-DESIGN-PROTOCOL.md` and the linked current Apple Human
Interface Guidelines. Treat this as a required design review, not optional
inspiration.

- Preserve the mathematical task as the primary content. Navigation and
  controls form a separate, adaptive interaction layer.
- Prefer familiar controls, direct manipulation, contextual help, reversible
  actions, and visible feedback over explanatory copy.
- Liquid Glass is reserved for navigation and interactive controls. It must
  not reduce content contrast or become decorative surface noise.
- New visualizations must encode real MORTRA state. Do not render an arbitrary
  "AI network" when typed objects, morphisms, obligations, residuals, or
  certificates can be shown instead.
- Every frontend change must be checked in a real browser at desktop and mobile
  widths, with keyboard focus, reduced motion, overflow, and contrast reviewed.
