# Temporal selection: fresh Linux result

Code `d545d2915ae434194e213bf110c69f0ece6e37a4` in corcondor/mortra.
GitHub Actions [34800481257](https://github.com/corcondor/mortra/actions/runs/34800481257) succeeded.
[Artifact 10331607328](https://github.com/corcondor/mortra/actions/runs/34800481257/artifacts/10331607328),
13,280,919 bytes; digest `57d653d41625d341e3b43f96fb6078bb1e1f27aa2708deedda9c40a2f175b824`.
This is fresh CI evidence, not the previous Windows development run.

Q-directed 351-test reproduction, acquisition, stored reuse and refusal passed.
Theory guards and DSL/semantic/corpus/temporal tests passed. The latter two
groups total 159 tests, reported separately from the existing 351 suite.

## Mechanism

11,000 unique experiences were observed, with 36 archived operations and six
active at completion. All four conditions correctly executed all 11,000 inputs.
There are 96 future evidence records and 42 selection changes. Every future
record is strictly later than acquisition, acquisition source IDs are excluded,
and selections obey the information cutoff. External queries left the complete
saved state unchanged. The separate adaptive producer generated 27 events
showing the selected operation mask reaching normal synthesis.

The producer finishes its current batch, so its full count is 11,323; only the
predeclared prefix of 11,000 is used for prequential measurement. This is not
323 unreported evaluation inputs. The bounded observer stops with the explicit
experience-budget reason. Acquired mathematics remains archived.

## Benefit and limits

On internal value-goal probes:

| Condition | Correct / 11 | Search applications | Query seconds |
| --- | ---: | ---: | ---: |
| All archived operations | 9 | 635 | 7.787 |
| Acquisition-only selection | 6 | 990 | 7.761 |
| Temporal selection | 8 | 566 | 7.423 |
| Initial DSL | 7 | 951 | 7.375 |

Counts include failed searches. Per-task common-success comparisons remain in
the artifact. At experience 7,000, removing selected recurrence
`T-recurrence-9d574f327350330e` increased candidates from 22 to 108, with both
answers correct. That is a demonstrated localized search benefit, not universal
superiority of the selected active set. Other removals had no benefit or saved
a few candidate checks; the negative ablations are retained.

On experiences 10,001..11,000, temporal program descriptions use 589,544 bits
against initial 648,728. Adding the 58,544-bit active library leaves only
640 bits of net description saving on this window. Do NOT report the raw
59,184-bit program saving as the net gain. Work is worse: 520,590 versus
504,561 counted operations. Time is also worse: 1.824 versus 0.891 seconds
(C-fixed: 1.940 seconds). Thus smaller descriptions did not imply cheaper
overall processing. C did remove much of A's overhead (A: 732,958 work,
3.851 seconds), but did not beat initial computation here.

Previously seen regression cohort, 48 tasks: all 18, acquisition 18,
temporal 20, initial 20 correct. Reserved external seed 920914, 24 tasks:
all 11, acquisition 11, temporal 10, initial 10 correct. External generalization
improvement is NOT demonstrated. These results were not used to tune selection.

## Costs and interpretation

Complete experiment: 640.108 seconds. The internal observer consumed 165.665
seconds, including 37.772 seconds for internal search comparisons. Shadow
execution used 60,085 work events; acquisition measurement used 270,094.
These are charged measurements, not free online learning. Timings are nested;
do not add observer time twice through the parent corpus-feedback cost.

Temporal state uses 1,039,173 canonical bytes, active sample 349,371,
execution history 12,209,565, retained acquisition sources 52,411. The archive
is not the active vocabulary. Mathematical semantic-abstraction depth remains
unmeasured; syntactic call depth remains one and is not substituted for it.

Conclusion: causal future utility, bounded active selection and actual generator
use work in this declared finite scope. Some selected knowledge helps particular
later searches. Consistently lower total cost or better fresh generalization
has not been shown. Primitive count is not identified as the cause.
