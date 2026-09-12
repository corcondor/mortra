# MORTRA Contributor Protocol

## Read these first

Before touching the representation-acquisition line of work, read in this order:

1. `docs/handoff/MORTRA-20260912.md` — what runs today, the entry points and
   their call graph, the environment, the test command and what its count
   covers, the latest normal run with its costs separated by condition, what is
   proved against what is only finite-checked, the known defects, the withdrawn
   claims, and the literature table (which marks every reference as not yet
   retrieved).
2. `NEXT.md` — the next development item: building the closure directly from a
   task's evaluated quantity instead of enumerating the whole candidate grammar.
   It is not implemented; do not edit it to say otherwise.

Neither file is a transcript, and neither should be pasted into this one.

## Research objective and roles

MORTRA must generate questions, discover intermediate lemmas, and prove results by composing its existing reusable vocabulary. Codex implements general search machinery, reads literature, diagnoses failures, and evaluates difficulty. Codex must not write the target question, target-specific lemma, answer, or witness and count its verification as MORTRA's problem-generation ability.

The core research path is source-neutral generator discovery: jointly choose a typed generator system, its finite or finitely represented action alphabet, an observation, and a short public question, then derive and independently replay its proof. An alphabet may have any cardinality justified by the source domain; the four-letter DNA analogy is not a constraint. Origami, geometry, arithmetic, analysis, probability, ARC, modular/\(\pi\), and finite-group experiments are source adapters and transfer evaluations. A capability claim requires generator/question co-selection, exact proof, public-statement reduction, and shorter-proof search on the same saved run, followed by a held-out source-domain evaluation.

- Start from current code and saved experiments. Do not rebuild capabilities that already exist.
- For autonomous problem research, read .agents/skills/mortra-autonomous-research/SKILL.md.
- The user's full problem corpus is comparison/evaluation material, not a source of target answers for generation.
- Treat the user's 90-problem corpus as a biased evaluation sample. Do not infer a universal domain prior, preferred alphabet size, or target conclusion distribution from it.
- Allow long generator compositions and adaptive search depth. Record effective dependency depth and representation changes separately from raw word length, because a long word may collapse to a short normal form.
- Keep statements short and natural while allowing long internal exploration. Do not equate construction count, trace length, or a long coordinate calculation with intrinsic difficulty.
- Do not equate a short final proof with an easy problem. Record surface simplicity, representation changes, key-lemma discoverability, and proof complexity separately. Key-lemma discoverability remains unmeasured until a blind solve experiment; reject a short proof as easy only when there is separate evidence that its key lemma is visible from the public statement.
- Count structural families separately from statement variants, seeds, and coefficient changes.
- Judge candidates using actual shorter-proof searches, condition removal, structural comparison, and high-school solution review.
- Treat a route found by a blind solver as training feedback: generalize and certify it on the full typed state space before reuse, rerank every compatible candidate, and evaluate the reranked candidate on a fresh blind cohort.
- Correctness, autonomy, structural novelty, exam quality, and measured solver difficulty are separate results. An unmeasured dimension is a required next experiment, not a reason to stop.
- When generation fails, analyze the shared bottleneck and relevant primary literature. Fix the search, representation, or verification mechanism; do not insert a handcrafted problem to fill the book.
- Preserve rejected candidates, failures, and source provenance. Present accepted problems separately from exploratory output.

## Creative formula standard

A formula is not new merely because its printed coefficients are new. Before promotion, quotient exact identities by index dilation or shift, parameter permutation, variable rescaling, algebraic pullback, scalar normalization, and composition with a known identity whenever those transformations can be certified. A formula that becomes a known formula after one of these transformations is a rediscovery or a new interpretation, not a new analytic formula.

Formula discovery must start from an autonomously selected exact object or period, not from a requested constant such as \(\pi\). MORTRA must derive the conjecture and its indispensable lemma graph from the same source-neutral run. Promotion requires an exact proof, an independently generated second proof route, a completed structural-equivalence audit, and a post-discovery literature audit. A candidate reaches the creative-new-standard review only when it also introduces a certified representation bridge and produces exact consequences outside the source instance. Surface surprise or human appeal is then evaluated separately; it is never inferred from a large coefficient, long generator word, or failed database lookup.

For finite-state lattice actions, prefer the general route from the exact Laurent resolvent to invariant coordinates, a certified Picard--Fuchs operator, arithmetic fingerprints, and only then special values. Do not optimize the source search for \(1/\pi\). Search for exceptional periods; allow \(1/\pi\), \(1/\pi^2\), \(L\)-values, zeta values, gamma values, or a previously unnamed invariant to emerge as consequences.

## Practical research path

The shared route begins with a source adapter that emits typed actions, exact observations, and provenance. Source-independent search then performs quotienting, invariant discovery, consequence extraction, proof search, statement reduction, novelty comparison, and blind difficulty evaluation. A source-specific adapter must not prescribe a target conclusion or helper lemma.

Every theorem-to-problem conversion must name an explicit source adapter. An unknown source domain is an error; it must never fall back to origami wording or origami scoring. Keep the certified theorem record and typed problem representation common, while keeping only construction parsing and public-language rendering in the adapter.

The existing goal-free geometry path is scripts/run_geometry_traceback_discovery.py. It composes MORTRA point constructors and uses Newclid/ncdgen for geometric construction and deduction. It selects conclusions after deduction. It is an integrated external prover, not a MORTRA-only kernel.

Use scripts/verify_geometry_traceback_discovery.py for independent symbolic replay, scripts/replay_geometry_traceback_candidates.py for auxiliary ablation, and scripts/build_geometry_feedback_book.py for checked presentation. Inspect their current schemas and limits before execution.

Specialized adaptive_* modules and lattice_metric_discovery.py may contain human-selected question families. Do not present them as goal-free autonomous discovery without an input/source audit.

## Product interface changes

Before changing MORTRA's public site or product workspace, read docs/design/MORTRA-HIG-DESIGN-PROTOCOL.md and its current Apple Human Interface Guidelines references.

- Mathematical content remains primary. Navigation is a separate adaptive interaction layer.
- Use familiar controls, direct manipulation, reversible actions, and visible feedback.
- Reserve Liquid Glass for navigation and controls; preserve content contrast.
- Visualizations must encode actual typed objects, morphisms, proof obligations, residuals, or certificates, not decorative fake networks.
- Test frontend changes in a real browser at desktop/mobile widths, including focus, reduced motion, overflow, and contrast.

## Delivery

Keep source, run configuration, all candidate outcomes, verification, and difficulty assessment together. Show problem statements without answer-revealing titles. Keep solutions separate. Original manuscripts, unrelated files, and production state remain unchanged unless requested.
