from future_refinement_core import FutureRefinementCore

core = FutureRefinementCore(actions=("enter", "a", "b"))

for cue, outcome in (("cue0", "y"), ("cue1", "z")):
    core.begin(cue)
    core.observe("enter", "x")
    core.observe("a", "m")
    core.observe("b", outcome)

print("split events:")
for event in core.split_events:
    print(event)

print("summary:")
print(core.summary())

# Expected qualitative order:
# downstream contradiction at action 'b' is discovered first;
# that split changes the successor structure seen by action 'a';
# then the distinction propagates backward and 'a' is split.
