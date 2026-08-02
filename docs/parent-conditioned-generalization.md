# Parent-conditioned generalization

MathOS fusion is triggered only after the user checks at least two parent problems.
Those selected problems are immutable terminals of the search; unrelated database
problems and remembered family IDs are not substitute inputs.

## Pipeline

1. Lex each Japanese/TeX parent into commands, identifiers, numbers, relations,
   mathematical keywords, particles, and delimiters.
2. Build a bounded parse forest instead of committing to one surface attachment.
3. Elaborate definitions, quantifier order, bindings, references, and query type.
4. Lift each parent into a typed graph while retaining separate provenance.
5. Enumerate typed morphism compositions. Detected parent operators are themselves
   search edges, so the search is not limited to paths already stored in the Atlas.
6. Accept a fusion only when one construction consumes every parent and all backend
   proof obligations terminate successfully.
7. Persist unfinished search and resume it with increasing depth and state budgets.

## Invariants

- Two or more unique parent IDs and non-empty statements are required.
- Equal sorts from different parents remain distinct alternatives.
- A scalar codomain shared independently by parents is not fusion.
- Applying an operator contributed by one parent to a compatible object from another
  is a valid candidate, subject to type checks and verification.
- A verified problem must include all parent IDs, an executable roadmap, an exact
  answer, and an independent verification certificate.
- An unfinished search remains processing; it is neither a generated problem nor a
  successful result.

## Search bound

Each round has finite term depth and a finite state budget. Subsequent rounds increase
both, providing fair iterative deepening for representable finite constructions. This
is semi-complete, not a promise that every arbitrary mathematical input has a verified
fusion or that non-existence is decidable.
