"""External metrics: no truth, goal, or result enters a learner through here."""
from collections import Counter


def partition_quality(assignments, true_classes):
    """Compare two partitions on exactly the same recorded history occurrences.

    true_classes are the evaluator's observation-preserving predictive quotient
    restricted to this carrier. Equality here is NOT full-world recovery.
    """
    assignments, true_classes = tuple(assignments), tuple(true_classes)
    if len(assignments) != len(true_classes):
        raise ValueError("Partitions must have the same evaluation carrier")
    choose2 = lambda counts: sum(n * (n - 1) // 2 for n in counts)
    same_model = choose2(Counter(assignments).values())
    same_true = choose2(Counter(true_classes).values())
    both = choose2(Counter(zip(assignments, true_classes)).values())
    merged, split = same_model - both, same_true - both
    pairs = len(assignments) * (len(assignments) - 1) // 2
    return {
        "carrier": "identical held-out history occurrences; not unobserved world states",
        "occurrences": len(assignments), "pairs": pairs,
        "exact_partition_equality": merged == 0 and split == 0 if assignments else None,
        "over_merge_pairs": merged, "over_merge_denominator": same_model,
        "over_merge_rate": merged / same_model if same_model else None,
        "over_split_pairs": split, "over_split_denominator": same_true,
        "over_split_rate": split / same_true if same_true else None,
        "predictive_violation_pairs": merged,
        "predictive_violation_scope": "same diagnostic as over-merge against all-future true classes; not independent evidence",
        "partition_agreement": 1 - (merged + split) / pairs if pairs else None,
    }
