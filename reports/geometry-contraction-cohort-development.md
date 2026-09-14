# Cohort generator development, before mechanism evaluation

The first generator invocation on 2026-09-14 was interrupted before it wrote
either frozen file. It requested distinct training/evaluation specifications
with two input points at depth one/two while excluding the previous cohort.
That grammar has insufficient distinct specifications for the requested slots.
No solver or contraction evaluation was run. The generator was corrected to
alternate three/four inputs and fail after 100 duplicate draws. Capacity four
and 256 input tuples per family were fixed before any mechanism evaluation.
This is generator development, not MORTRA capability evidence. No old task,
seed, budget, report or artifact was modified.

The successful freeze produced 12 training and 8 evaluation specifications:
canonical config digest 2ccd039890159983d3a8fde478ccdf2090eb2919e9cdb060a1c427956d98010a;
evaluator-witness digest 63bda7df8ca7c522e9c40d3fe619035ee3d3180f6d3d92e7fba1a3dda72f60f7.
Erratum recorded before mechanism evaluation: the protocol's rejection prose
mentions initial-point outputs, but the implemented generator only rejects
duplicate specifications. Initial-point outputs can therefore remain as easy
tasks. Keep the frozen tasks unchanged and report this limitation rather than
selectively replacing tasks after inspection. Depth is generating-program
depth, not certified minimal solution depth. The solver never receives it.
