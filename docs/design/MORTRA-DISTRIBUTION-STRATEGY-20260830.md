# MORTRA Distribution Strategy

Date: 2026-08-30
Scope: official website, X, GitHub, Vercel previews, research releases

## Objective

MORTRA should be understood in one pass as an executable mathematics system, then give a visitor an immediate path to:

1. see one striking mathematical result;
2. try the product;
3. inspect the proof, figure, and certificate;
4. verify the code and research record on GitHub.

The system is not marketed by abstract claims. It is marketed by a visible mathematical object, a working interaction, and a reproducible artifact.

## Baseline diagnosis

At the start of this pass, the product, website, X account, and GitHub repository described different stages of the project.

- The website already uses `mortra.ai` and the current MORTRA 1 result ledger.
- The official X account uses the right name and slogan, but has not yet accumulated a recognizable visual identity or publishing rhythm.
- The GitHub repository initially presented the former `sakumon-station` product description and the legacy `mortra.vercel.app` address.
- GitHub had no topics and no social preview, so a shared repository link did not explain why the work matters.
- The README began with setup. A first-time visitor therefore met implementation details before seeing the product, evidence, or research purpose.

GitHub traffic on 2026-08-30 was 4 views from 2 unique visitors over the available 14-day window, with no recorded external referrers. Clone counts were much larger, but without referrers they must not be treated as human acquisition; CI and automated work can dominate that number.

## One identity

### Primary mark: Incidence weave

Use Figure 6, `Incidence weave`, from `MORTRA-cross-domain-geometry-basis-20260830.pdf` as the primary mark.

- Source semantic hash: `e6523b41e3883cc66f665f09930d10ae27c980d30a7c79f175e73277e23017cb`
- The same verified semantic figure is used for the avatar, header, site icon, Open Graph card, and GitHub social preview.
- Only crop, line weight, color, and typography change between surfaces.
- No logo-specific geometric primitive was added.

This mark is stronger than the legacy proof bars because it remains visibly mathematical, has a clear circular silhouette, is distinct in a feed, and directly demonstrates MORTRA's thesis: a small geometry vocabulary can produce a complex, reusable structure.

The proof bars remain a secondary visual language for proof ledgers, benchmark rows, and progress views. They are not the account avatar.

### Brand palette

| Role | Color |
|---|---|
| Background | `#071A2C` |
| Primary line/text | `#DDF8FF` |
| Structural line | `#50B9D8` |
| Muted construction | `#287A9B` |
| Active/verified accent | `#50E3C2` |

Use solid fields and geometry. Do not add decorative gradients, generic AI imagery, glowing spheres, or stock laboratory imagery.

## Channel roles

### X: discovery and conversation

Official account: `@MORTRA_AI`

Use the official account for finished mathematical artifacts and research milestones. Use the founder account for context, opinion, development narrative, and quote-posting the official result. Do not post the same text from both accounts.

The official profile should communicate only three things:

- MORTRA is an executable mathematics system.
- It returns proofs, figures, and replayable certificates.
- The product is available at `mortra.ai`.

Recommended profile specification:

| Field | Value |
|---|---|
| Display name | `MORTRA` |
| Account | `@MORTRA_AI` |
| Bio | `Executable mathematics. Problems, proofs, figures, and replayable certificates from one mathematical structure.` |
| Website | `https://mortra.ai` |
| Avatar | `brand/social/mortra-avatar-x-400.png` |
| Header | `brand/social/mortra-x-header-1500x500.png` |

Do not use `No LLM in the path` as the profile's closing sales claim. It describes an implementation constraint rather than the product benefit, and the linked research pages are the correct place to explain the symbolic execution boundary.

The pinned post should be a short visual demonstration, not a manifesto. The first frame must show the mathematical object; the last frame must show the problem, proof route, and `Try MORTRA` link.

### Website on Vercel: conversion

`mortra.ai` is the canonical destination. Its job is to turn interest into use.

Primary journey:

`landing -> Try MORTRA -> submit -> proof/figure appears -> inspect route -> share or open research`

Every public result or research post should link to a concrete page, not to a generic homepage when a more relevant destination exists. Vercel preview deployments are for visual and interaction QA; only verified pages are promoted to production.

### GitHub: evidence, discovery, and trust

GitHub is a public research surface, not only source storage.

It should provide:

- an immediate product description and `Try MORTRA` link;
- the current verified result ledger;
- reproduction commands close to each claim;
- research notes and machine-readable artifacts;
- releases that correspond to public milestones;
- a citation file;
- topics that place MORTRA in mathematical reasoning and formal methods searches.

The public repository is `corcondor/mortra`. GitHub redirects the former repository URL, and `release/mortra-1-beta` is the default branch and Vercel production branch.

### Instagram: visual archive

Use only when a result benefits from motion, stepwise construction, or a diagram sequence. It is secondary to X until the official account has a stable publishing cadence.

## Content system

Each public item must belong to one of four repeatable formats.

### 1. One problem, one proof

- problem statement in the first visual;
- one decisive construction or morphism per frame;
- final proof certificate and exact answer;
- link to the interactive result.

### 2. One structure, many representations

Show the same semantic object as a proof diagram, construction drawing, architectural linework, and generative art. `Incidence weave` is the launch example because the semantic hash is preserved across render policies.

### 3. Measured result

Use one comparable number and one sentence explaining what was measured. Current public figures must be read from `lib/mortra/i18n.ts`, not copied into independent marketing files.

- audited geometry cohort: `89 / 89`;
- replayed exact identities: `357 / 357`;
- software/circuit equivalence inputs: `2,000,000 / 2,000,000`.

### 4. Research release

State the question, method, result, and next falsifiable question. Attach the code, data, figure, and certificate. Avoid diary-style updates that do not contain a result or a useful failure.

## Launch sequence

### Identity day

1. Change the official X avatar to `brand/social/mortra-avatar-x-400.png`.
2. Change the X header to `brand/social/mortra-x-header-1500x500.png`.
3. Use the same mark for the site icon and social card.
4. Upload `brand/social/mortra-github-social-preview-1280x640.png` as the repository social preview.
5. Update the GitHub description, homepage, topics, and README.

### Launch post

Publish a 10-20 second construction sequence of `Incidence weave`:

`two free points -> 17-fold orbit -> lines -> midpoints -> perpendiculars -> intersections -> parallels -> circles`

Copy should explain that the image was generated from the same finite geometry operations used by the reasoning system. Link to the relevant research article with:

`?utm_source=x&utm_medium=social&utm_campaign=mortra1_launch&utm_content=incidence_weave`

### Following seven days

- Day 2: one problem, one proof.
- Day 4: current benchmark result with a direct reproduction link.
- Day 6: one structure, three renderings.
- Day 7: short research note describing what the next experiment must falsify.

After launch, prefer three substantial X posts per week and one longer research release per week over daily filler.

## Measurement

### Acquisition

- X impressions, profile visits, link clicks, and follows per post;
- GitHub unique visitors, external referrers, stars, and human issue/discussion activity;
- search impressions for `MORTRA`, `symbolic mathematics`, `geometry prover`, and their Japanese equivalents.

### Activation

- `try_viewed`;
- `problem_submitted`;
- `artifact_completed`;
- `proof_route_opened`;
- `figure_opened`;
- `result_shared`.

### Quality

- completion rate from submit to displayed artifact;
- median time to first visible intermediate result;
- proof replay success rate;
- share rate for completed artifacts.

Do not optimize for impressions alone. The primary launch metric is the number of visitors who submit a problem and receive a complete, inspectable result.

## Editorial rules

- Lead with the object or result, not with background explanation.
- Use exact mathematical language and ordinary Japanese or English.
- Do not use generic AI phrases such as "revolutionary", "unlock", or "the future of".
- Do not market internal plumbing as a benefit. Explain what the user can inspect or do.
- Do not post an unverified score.
- Do not turn honest methodology into defensive copy. Methodology belongs on the linked research page.
- Every benchmark claim must point to a frozen cohort and reproducible artifact.
- Every visual proof must remain legible on a phone before publication.

## Immediate implementation boundary

This pass changes the visual identity, social assets, website/GitHub links, repository metadata, README, attribution plan, repository name, default branch, and production deployment. The avatar/header pair has been reviewed together; the official X profile remains untouched only because the available OAuth credentials authenticate the personal account rather than `@MORTRA_AI`.

## Implementation status on 2026-08-30

| Surface | Status | Evidence / next boundary |
|---|---|---|
| Brand asset set | Complete | Generated from semantic hash `e6523b41e3883cc66f665f09930d10ae27c980d30a7c79f175e73277e23017cb`; 12 outputs recorded in `brand/social/manifest.json`. |
| Website identity | Live in production | Favicon, Apple icon, navigation mark, Open Graph card, Twitter card, GitHub link, and official X link are implemented at `mortra.ai`. |
| Desktop/mobile QA | Complete | Both viewports return 200, render the 32 px mark, preserve the GitHub path, and have no horizontal overflow or page errors. |
| GitHub metadata | Live | Repository renamed to `corcondor/mortra`; description, `mortra.ai` homepage, eight research/discovery topics, and the default branch are updated. |
| GitHub README/assets | Live on default branch | Brand assets, README, website links, citation metadata, and this strategy are published from `release/mortra-1-beta`; unrelated research changes are not included. |
| GitHub social preview | Asset complete | GitHub does not expose this upload in the repository REST API; upload `brand/social/mortra-github-social-preview-1280x640.png` in repository settings. |
| Official X profile | Assets complete, account update pending | Repository OAuth currently authenticates personal account `@corcondol`, not `@MORTRA_AI`; obtain official-account authorization before changing profile media. |
| Vercel production | Live | Deployment `dpl_8PXdwvtP3V6wpXJJJ53EWoQN1pdo` is `READY` and `PROMOTED`; aliases include `mortra.ai` and `www.mortra.ai`. |
