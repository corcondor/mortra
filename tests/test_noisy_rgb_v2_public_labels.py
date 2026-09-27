import numpy as np
import pytest

from experiments.noisy_rgb_discovery.sensor import Sensor,make_game
from experiments.noisy_rgb_predictive_v2.public_labels import PublicLabels,labelled_game,LabelledSensor


def test_missing_label_is_not_same_and_terminal_is_not_invented():
    labels=PublicLabels()
    labels.add((),{'goal':False})
    assert labels.compare((),(0,))=='UNRESOLVED'
    labels.add((0,),{'goal':True})
    assert labels.compare((),(0,))=='DIFFERENT'
    assert 'terminal' not in labels.records[()]


def test_labels_are_only_sampled_endpoints_and_pixels_are_unchanged(tmp_path):
    labels=PublicLabels()
    seed=97027000
    original=Sensor(make_game(seed),(0,0),'transport-equivalence',tmp_path/'old')
    adapted=LabelledSensor(labelled_game(seed),(0,0),'transport-equivalence',tmp_path/'new',labels=labels)
    try:
        h=(0,1)
        assert np.array_equal(original.sample(h,0),adapted.sample(h,0))
        assert set(labels.records)=={h}
        assert original.actions==adapted.actions==2
        assert original.exposures==adapted.exposures==8
        with pytest.raises(AssertionError):
            adapted.game.raw_goal(adapted.game.start_raw)
        with pytest.raises(AssertionError):
            adapted.game.token_for(adapted.game.start_raw)
    finally:
        original.close()
        adapted.close()
