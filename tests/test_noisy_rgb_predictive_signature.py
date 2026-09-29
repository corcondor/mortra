from experiments.noisy_rgb_predictive_signature.core import DirectPredictiveLearner
from experiments.noisy_rgb_version_space.core import SAME, DIFFERENT


class ExactEvidence:
    stages = (32,)

    def __init__(self, transitions, observations, start=0):
        self.transitions = transitions
        self.observations = observations
        self.start = start
        self.calls = []
        self.version = 0

    def at(self, history):
        state = self.start
        for action in history:
            state = self.transitions[state][action]
        return state

    def compare(self, h, r, e=(), stage=32):
        left = self.observations[self.at(tuple(h) + tuple(e))]
        right = self.observations[self.at(tuple(r) + tuple(e))]
        self.version += 1
        result = SAME if left == right else DIFFERENT
        row = dict(id=self.version, result=result, stage=stage,
                   pair=(tuple(h)+tuple(e), tuple(r)+tuple(e)))
        self.calls.append(row)
        return row


def test_direct_signature_builds_exact_small_quotient_without_provisional_nodes():
    transitions = [
        [2, 0],
        [1, 2],
        [0, 1],
    ]
    observations = ["A", "A", "B"]
    evidence = ExactEvidence(transitions, observations)
    rows = []
    learner = DirectPredictiveLearner(evidence, (0, 1), rows.append)
    model, status = learner.learn()

    assert status == "COMPLETED_ONE_STEP_QUOTIENT"
    assert len(model["reps"]) == 3
    assert not model["unresolved"]
    assert len(model["trans"]) == 6
    represented = [evidence.at(h) for h in model["reps"]]
    assert set(represented) == {0, 1, 2}
    for q, h in enumerate(model["reps"]):
        source = evidence.at(h)
        for action in (0, 1):
            target_q = model["trans"][q, action]
            assert evidence.at(model["reps"][target_q]) == transitions[source][action]
    assert not any(row["event"].startswith("provisional") for row in rows)


def test_open_world_unresolved_is_not_promoted_to_new_state():
    class UnresolvedEvidence:
        stages = (32,)
        def compare(self, *args, **kwargs):
            return dict(id=1, result="UNRESOLVED", stage=32)

    learner = DirectPredictiveLearner(UnresolvedEvidence(), (0, 1))
    assert learner.resolve((0,)) is None
    assert learner.reps == [()]
    assert (0,) in learner.unresolved


def test_active_probe_is_selected_by_separation_not_fixed_action_name():
    # Here action 0 separates the two aliased states.
    transitions_a = [[2, 0], [1, 2], [0, 1]]
    observations = ["A", "A", "B"]
    learner_a = DirectPredictiveLearner(ExactEvidence(transitions_a, observations), (0, 1))
    learner_a.reps = [(), (0, 1)]
    assert {learner_a.evidence.at(h) for h in learner_a.reps} == {0, 1}
    assert learner_a.choose_identification_probe({0, 1}, set(), 32) == 0

    # Relabel the actions so only action 1 separates. The selector must follow
    # the observed separation, not a baked-in "forward" action.
    transitions_b = [[0, 2], [2, 1], [1, 0]]
    learner_b = DirectPredictiveLearner(ExactEvidence(transitions_b, observations), (0, 1))
    learner_b.reps = [(), (1, 0)]
    assert {learner_b.evidence.at(h) for h in learner_b.reps} == {0, 1}
    assert learner_b.choose_identification_probe({0, 1}, set(), 32) == 1
