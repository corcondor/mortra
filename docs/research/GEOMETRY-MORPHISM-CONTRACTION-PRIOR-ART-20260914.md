# Certified Morphism Contraction: pre-implementation audit

## Decision

Internal-state hiding, macro preconditions, summarized effects, and hierarchical
refinement are not new research principles. This implementation is a scoped
integration experiment, not a new abstraction algorithm claim. The question is
whether exact, learned rational geometric constructions actually reduce later
search when their private intermediate points are hidden. No new mathematical
experiment was executed for this diagnosis. The results below are historical
Actions data, re-read on 2026-09-14, not a fresh reproduction.

## Frozen negative baseline

- Repository: corcondor/mortra.
- Branch: codex/geometry-contract-acquisition-20260914.
- Commit: 39ce48368639f3c508bdd611b06339aad893f342.
- [Actions 34818657880](https://github.com/corcondor/mortra/actions/runs/34818657880).
- [Artifact 10337532055](https://github.com/corcondor/mortra/actions/runs/34818657880/artifacts/10337532055).
- Scientific gate: FAIL; exact replay passed; zero false submitted proofs.
- The original four evaluation tasks, config, outputs, and report stay unchanged.
  Future executions of those tasks are regression only.

File SHA256 (byte hashes, distinct from canonical-JSON digests):

| File | SHA256 |
|---|---|
| configs/theory-geometry-contract-acquisition.json | 2b5e07bbde015438c324a846ec103a37d7ce21e9c3419fefbdb7d3cb53103cfa |
| docs/research/GEOMETRY-CONTRACT-ACQUISITION-20260914.md | 0d6066074812f10d9188938873506c1d98ac1c1707178f1b98022fde14779779 |
| output/geometry-contract-actions-34818657880/geometry-contracts/result.json | ae0a0ec024bfcf2bfafde435e3c1b151a17b5e62f487179f47fd40a3ec78daa1 |
| output/geometry-contract-actions-34818657880/geometry-contracts/comparisons.json | f07dcd68c183679bf33cf35bcaaf41311a7d6f9ca18db37d6185304680b442a5 |

## Read-only diagnosis

Source: `math_os_prototype/theory_geometry_acquisition.py`, methods
`RationalGeometryDomain.candidates`, `apply`, `is_goal`; and
`math_os_prototype/geometry_contracts.py::certify_body`, at the frozen commit.
Data: the artifact's `comparisons.json` and `result.json`.

1. The complete `enumerate` event arrays are byte-identical after JSON
   normalization between syntactic_macro and certified_morphism for each of the
   four tasks. Their expansions are [28,38,119,119], totaling 304. They use the
   same families, rank, visible objects and coordinates; certification changes
   the evaluation route, not the search graph in this sample.
2. P is checked inside `apply`, after binding enumeration/ranking and after
   charging the expansion. It is not used by `candidates`.
3. `apply` loops over every DAG step and adds every local output to
   `child['points']` and `child['terms']`, not just the final output.
4. `candidates` begins with `names=list(state['points'])`. All these locals
   participate in subsequent input tuples and the incidence graph. For an
   ordered arity-k acquired family with repeated arguments, N visible points
   permit N^k tuples before limits. This is a structural branching cause;
   the historical comparison alone does not isolate its causal effect.
5. Q is `guaranteed_relation=relations`, the concatenation of per-constructor
   relations; it still mentions internal locals. The rational witness is already
   input-only, but has not been compiled to an input/output summary relation.
6. The measured increases are below. Offered means returned candidate rows,
   summed across family/state enumeration calls, not unique tuples or attempts.
   Objects added is summed over successful child constructions, not live memory.

| Condition (four tasks) | Families | Offered | Expansions | Successful applications | Objects added | Goal identity checks | Solved |
|---|---:|---:|---:|---:|---:|---:|---:|
| primitive | 2 | 320 | 268 | 127 | 127 | 1416 | 2/4 |
| exposed syntactic macro | 5 | 434 | 304 | 174 | 299 | 1966 | 2/4 |
| exposed certified morphism | 5 | 434 | 304 | 174 | 299 | 1966 | 2/4 |

The ablation removed H0 but lost no solve, increased no expansion count, and
lengthened no proof. That negative result remains the official baseline.

## Targeted primary literature

Read coverage is explicit; inaccessible full text is not reported as read.
This is not a repetition of the preceding fifteen-paper audit.

| Work and primary source | Coverage this time | Relevant content |
|---|---|---|
| Richard Korf, *Macro-operators: A weak method for learning*, Artificial Intelligence 26, 35-77 (1985). [Columbia scan](https://mice.cs.columbia.edu/getTechreport.php?format=pdf&techreportID=973) | Publisher abstract; scan pp.36-37 visually read. Full scanned paper retrieved, not fully read/OCRed. | Macros restore earlier subgoals at completion even when internal steps violate them. Existing macros can be composed to acquire further macros. The overview distinguishes macro storage, learning cost and primitive solution length. |
| Richard Korf, *Planning as Search: A Quantitative Approach*, Artificial Intelligence 33, 65-88 (1987). [Publisher](https://www.sciencedirect.com/science/article/abs/pii/0004370287900518), [author bibliography](https://web.cs.ucla.edu/~korf/publications.html) | Primary abstract only; full article unavailable through retrieved links. | Quantitative treatment of subgoals, macros and abstraction, including a macro time-space tradeoff. No unexamined theorem from this article is used in the implementation. |
| Hauskrecht, Meuleau, Kaelbling, Dean, Boutilier, *Hierarchical Solution of Markov Decision Processes using Macro-actions*, UAI 1998, 220-229. [Author PDF](https://www.cs.toronto.edu/~cebly/Papers/macros.pdf) | Introduction and sections 2.2-2.4, especially Definition 4; indexed conclusion. | Adding macros without changing states can increase work. Restricting decisions to region boundaries hides internal states. Macro-model construction costs and suboptimality from restricted choices are explicit. This is stochastic discounted planning, not universal polynomial geometry. |
| Martin Kramer and Claus Unger, *Abstracting Operators for Hierarchical Planning*, AIPS 1992, 287-288. [Publisher](https://www.sciencedirect.com/science/chapter/edited-volume/abs/pii/B978008049944450046X), [1991 author report listing](https://www.fernuni-hagen.de/mi/forschung/berichte/berichte_1991.shtml) | Publisher summary; repository PDF blocked by security challenge. Report and proceedings versions not textually compared. | Abstract operator types are distinguished from fixed macros. Postconditions distinguish unavoidable effects from effects achievable by some refinement. |
| Clement, Durfee, Barrett, *Abstract Reasoning for Planning and Coordination*, JAIR 28, 453-515 (2007). [Journal HTML mirror](https://www.cs.cmu.edu/afs/cs/project/jair/pub/volume28/clement07a-html/1-page.html) | Introduction, model overview; section 3 summary-condition description and section 7 limitations via primary indexed text. | Summary information includes pre-, internal-, postconditions and must/may distinctions. Refinement must respect hidden interactions. Summarization may increase overhead when it does not reduce planning complexity. |

## Existing audit, brief comparison only

The following is carried forward from the preceding audit's X2/X4/X5/X6
reading records, not presented as newly completed full-paper reading.

- [AUXIL](https://www.jstage.jst.go.jp/article/jjsai/4/3/4_308/_pdf): learned
  auxiliary-construction patterns from proofs; not evidence for automatic
  exact elimination of hidden construction variables.
- [Twitch](https://link.springer.com/chapter/10.1007/978-3-032-32589-1_4): learned
  proof abstractions influencing later proof search. This prevents claiming
  proof-to-macro learning itself as new.
- [DreamCoder](https://www.neurosymbolic.org/papers/EllisWNSMHCST21.pdf): acquired
  parameterized libraries used for later synthesis; this is not by itself
  a certified geometric state-contraction theorem.
- [babble](https://arxiv.org/pdf/2212.04596), section 4.1: library learning
  modulo an equational theory. Shorter syntax is not fewer planner objects.

## Implementation boundary and testable difference

The engineering proposal, not a claim made by those papers, is:

1. Reuse MORTRA's learned construction bodies, rational witnesses and exact
   triangular uniqueness proofs. Derive Q by clearing output denominators.
2. Under P, prove `exists private. C <=> Q` by witness substitution, nonzero
   denominator coverage and uniqueness, over real input coordinates with QQ
   coefficients. Do not claim this equivalence outside P.
3. Infer DAG interfaces, keep external references public, hide only private
   values, and provide explicit paid refinement when hidden values are needed.
4. Use proved preconditions before capped candidate selection. Effect/type
   compatibility may rank candidates, never exclude a path just because its
   effect is not the final goal. Retain the primitive language.
5. Freeze a new mechanically generated specification cohort before evaluating
   contraction. Compare exposed and hidden states with acquisition, filtering,
   proof, replay and primitive-equivalent costs separated.

The known state-abstraction idea is not novel. The empirical question about
MORTRA's learned exact geometry remains open at this document's creation.
If hiding removes a solve or yields no search reduction, retain FAIL. Do not
add stratification, selector mechanisms, other domains or external provers.
