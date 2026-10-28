# GeoCPU / MORTRA: Evidence-addressed Binding readout (research preflight)

Date: 2026-10-28 (JST)  
Status: **PROPOSAL + CODE-PATH/CONTRACT TESTS; NOT A TRAINED-MODEL IMPROVEMENT**  
Scope: read-only investigation, no weight edits, no active-job changes, no GPU training.

## Decision and revision

The preceding *Learned Source-Span Readout* concept remains promising **only conditionally**. Before training a new decoder, test whether frozen per-position CED features contain recoverable question-conditioned evidence, and whether a low-rank reader exceeds strong lexical baselines. If the evidence is not recoverable, fall back to independently indexed original text; do **not** claim a readout head can recover information erased by compression.

Proposed single development path: **Evidence-addressed Binding** (source-verified, query-conditioned selection + optional exact copying + explicit abstention). This is not a novel fundamental network architecture: CopyNet, pointer-generator, dense retrievers, and extractive QA are predecessors. No results below are claimed for a trained new head.

## Verified archived evidence (not a new GPU/model evaluation)

- From the 2026-10-27 frozen CED likelihood archive: with both candidate facts present and their roles swapped, positive likelihood-direction shifts were **1/12** when the target came first and **10/12** when it came last; both orderings were consistently positive in **1/12**; both answers correctly selected by probability ranking in **0/12**. These are teacher-forced *relative likelihood* diagnostics on a hand-built sample, **not free-generation accuracy**.
- Re-ran the archived `check_report_integrity.py` on its saved per-case JSON: counters reproduced (first=1, last=10, both-order-positive=1; K=1/2/4: 1/2/2). This is a log-integrity recheck, not re-inference.
- A **copied 2026-10-26 NumPy source snapshot** exposes `NativeOutput.features` in `numpy_grand.py::forward_output`; `long_native_draft.py::prefill_prompt` retains per-prompt-position features. `model_adapter.py` currently consumes work state and native model logits, without a trained source-span selector.
- Separate CPU smoke checks with **random toy weights**, not the saved checkpoint, passed 7/7 assertions: per-position feature shapes/finite values, exact short-context parity, 22-symbol long-context feature retention, raw Unicode span offsets, provenance hash checks, repeated mentions, counterfactual order swapping, and a null-decision contract (grouped into seven tests).
- Therefore **connection feasibility** is demonstrated in the inspected source, **semantic decoding accuracy is not demonstrated**. The source snapshot may differ from any later running model; never infer that the recent Kaggle/AG Fused training has adopted this feature.

## Crucial theoretical falsifier: representation sufficiency

Let E be the frozen representation, q the question, and a(x,q) the correct source answer. If there exist x1,x2 with E(x1)=E(x2) and a(x1,q) != a(x2,q), then **no deterministic head** f(E(x),q) can answer both. This is a direct consequence of identical inputs to f. Character bags for two role-swapped Japanese sentences give a *toy illustration*; **they are not evidence that CED itself collides**.

Non-identical CED states are also insufficient evidence of usefulness: the relevant relation may not be linearly/efficiently decodable. Use a constrained linear/low-rank probe and **Hewitt–Liang selectivity controls** (shuffled relation labels, preserved entity statistics, held-out documents) before claiming the frozen encoder represents relations.

## Minimal architecture, only after that gate

For source positions i, the frozen features h_i in R^256 and question state q in R^256, define:

- u = W_q q; k_i^S = W_S h_i; k_i^E = W_E h_i, each in R^64
- s_i = u^T k_i^S / sqrt(64); e_j = u^T k_j^E / sqrt(64)
- choose the best valid (i,j), i <= j, span length <= L, or a learned **NULL**.
- Copy **only** using `(doc_id, SHA-256(raw_UTF8), start_codepoint, end_codepoint)` checked against the original immutable text. Do not mistake token indices or bytes for Unicode code-point offsets. Keep token-to-text alignment during serialization. If no supported span exists, abstain.
- Train a source span loss plus paired role-swap / hard-negative margin and NULL calibration on **document-disjoint** data. Do not train or change the protected CED base. Preserve existing normal-generation routing.
- For abstractive, multi-hop, mathematical or code answers, treat selected evidence as grounded input to a *separately evaluated* reasoning/execution path: a copied string is **not** a proof, calculation, or verified executable program.

Three 256x64 matrices use 49,152 weights, before small bias/NULL parameters; FP32 parameter, gradient and two Adam moments are about **0.75 MiB** for these matrices (4 * 49,152 * 4 bytes). Materializing 8,192 positions x 256 in FP16 requires 4 MiB, or 8 MiB in FP32, per sequence **per retained tensor**. This excludes encoder execution, intermediate activations and attention; total latency must be measured. An original 131,072-position FP16 feature tensor alone takes 64 MiB. Use coarse candidate retrieval before expensive per-token scoring.

## Stage-gated experimental plan

1. **Input/label audit**: assemble 400 held-out, document-disjoint real examples spanning physics experiment notes, math exposition, Python source/docstrings, and MORTRA environment logs; include 160 role-swap/order-balanced paired cases, impossible queries and multi-hop cases. Preserve original text + `doc_id`, SHA-256, exact Unicode offsets; log annotation ambiguity and overlap, data-source permission and split hashes.
2. **Frozen representation probe**: extract `[B,T,256]` features *without training the base*. Compare a rank-16/64 probe to (a) BM25 or character-ngram retrieval, (b) first/last mention, (c) frozen CED free-generation, and (d) source-locator oracle (upper bound, **not fair deployable baseline**). Shuffle labels as a selectivity control. Check role swaps, position quartiles and unknown entities separately.
3. **Only if decodable**: fit start/end and NULL heads; evaluate exact span EM/F1, evidence Recall@k, answerability FPR, paired counterfactual consistency, actual answer success and wall time. Evaluate equivalent compute budgets, with uncertainty via paired document-cluster bootstrap, using a fixed threshold selected exclusively on development data.
4. **Decision rule (precommitted)**: promote only if unseen-document answer EM improves by >=10 percentage points over the best practical matched baseline, the paired cluster-bootstrap 95% CI lower bound of the improvement is positive, unsafe/unsupported copying is zero, normal output is unchanged when disabled, and measured latency is within the deployment budget. If BM25 is as strong, if role-swap scores collapse, if the probe memorizes the shuffled-label control, or if NULL calibration fails, **reject and keep the original model**. A probe failure may mean either inadequate frozen representation *or* an insufficient probe; do not assert a universal impossibility from one test.

### Reproduce current (pre-model) CPU checks

The sibling `test_span_readout_preflight.py` uses Python + NumPy and **copies** of archived `numpy_grand.py` and `long_native_draft.py` placed in its import path:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v test_span_readout_preflight.py
```

With original source copies available, 7/7 tests passed on 2026-10-28 using seeded **random toy weights**. If the native source is unavailable, only independent evidence-contract checks run; no repository source or weight modification is required. The original saved 2026-10-27 diagnostic can be rechecked using `check_report_integrity.py` in the archived evidence zip, which checks counters without model inference.

### Primary literature: exactly what transfers, and what does not

1. Gu et al., **CopyNet**, ACL 2016 — conditional copying of source tokens, **not** evidence that CED has learned locations: https://aclanthology.org/P16-1154/
2. See et al., **Pointer-Generator**, ACL 2017 — copying with generation and coverage for summarization; coverage is **not** a semantics/faithfulness guarantee: https://aclanthology.org/P17-1099/
3. Karpukhin et al., **DPR**, EMNLP 2020 — learned dense retrievers with a strong BM25 comparator; large-model gains **do not transfer** to a 10M GeoCPU automatically: https://aclanthology.org/2020.emnlp-main.550/
4. Liu et al., **Lost in the Middle**, TACL 2024 — relevance-position effects justify position-orthogonal holdout sets: https://aclanthology.org/2024.tacl-1.9/
5. Jia & Liang, **Adversarial Reading Comprehension**, EMNLP 2017 — distractors can overturn QA; justify paired role swaps: https://aclanthology.org/D17-1215/
6. Rajpurkar et al., **SQuAD 2.0**, ACL 2018 — a NULL option is necessary and must be calibrated: https://aclanthology.org/P18-2124/
7. Hewitt & Liang, **Designing and Interpreting Probes with Control Tasks**, EMNLP 2019 — strong probes can learn labels without revealing frozen representations: https://aclanthology.org/D19-1275/
8. An et al., **Make Your LLM Fully Utilize the Context**, NeurIPS 2024 — long-context training should directly supervise evidence from arbitrary positions; not direct validation for GeoCPU: https://proceedings.neurips.cc/paper_files/paper/2024/hash/71c3451f6cd6a4f82bb822db25cea4fd-Abstract-Conference.html

## Non-claims and provenance

No new trained span reader exists in this record. No GPU training or additional run of the user's saved checkpoint occurred. No Kaggle active session, Google Drive original, Bot, CED weights, repository production code or deploy was changed. This note is research documentation with a **conditional** implementation recommendation and a separately testable contract.
