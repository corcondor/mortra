import sys
from types import FunctionType

import pytest

from experiments.autonomous_completion.probe import ForbiddenOracle, Observer, save


def invoke(observer, fn):
    previous = sys.getprofile()
    try:
        sys.setprofile(observer)
        return fn()
    finally:
        sys.setprofile(previous)


def test_oracle_body_is_never_executed():
    calls = []
    def forbidden():
        calls.append("body")
    observer = Observer({"oracle": forbidden}, {})
    with pytest.raises(ForbiddenOracle):
        invoke(observer, forbidden)
    assert calls == []
    assert observer.events[0]["body_executed"] is False


def test_alias_and_same_code_function_are_also_blocked():
    def forbidden():
        raise AssertionError("must not run")
    alias = FunctionType(forbidden.__code__, forbidden.__globals__)
    observer = Observer({"oracle": forbidden}, {})
    with pytest.raises(ForbiddenOracle):
        invoke(observer, alias)


def test_generated_return_is_saved_without_changing_it():
    original = {"a": [1, 2]}
    def generate():
        return original
    saved = []
    observer = Observer({}, {"generate": generate}, lambda i, g: saved.append((i, g)))
    result = invoke(observer, generate)
    assert result is original
    assert saved == [(0, original)]
    assert saved[0][1] is not original
    assert observer.calls == {"generate": 1}


def test_cannot_overwrite_previous_evidence(tmp_path):
    path = tmp_path / "evidence.json"
    save(path, {"first": True})
    with pytest.raises(FileExistsError):
        save(path, {"replacement": True})


def test_real_oracle_blocked_before_reading_engine():
    from experiments.game_frontier_v11.world import oracle
    class UnreadableEngine:
        @property
        def initial(self):
            raise AssertionError("oracle body accessed world")
    observer = Observer({"v11.oracle": oracle}, {})
    with pytest.raises(ForbiddenOracle):
        invoke(observer, lambda: oracle(UnreadableEngine(), 1))


def test_exception_preserves_previous_profile():
    before = sys.getprofile()
    def forbidden():
        pass
    with pytest.raises(ForbiddenOracle):
        invoke(Observer({"oracle": forbidden}, {}), forbidden)
    assert sys.getprofile() is before
