from scripts.experiment_terminal_factor_cover_singular import strict_factor_cover


def test_strict_factor_cover_requires_every_replayed_branch() -> None:
    assert strict_factor_cover(
        {0: {"strictly_accepted": True}, 1: {"strictly_accepted": True}},
        2,
    )
    assert not strict_factor_cover({0: {"strictly_accepted": True}}, 2)
    assert not strict_factor_cover(
        {0: {"strictly_accepted": True}, 1: {"strictly_accepted": False}},
        2,
    )


def test_probe_only_branch_cannot_enter_strict_cover() -> None:
    assert not strict_factor_cover(
        {
            0: {
                "probe": {"status": "computed", "member": True},
                "certificate": None,
                "strictly_accepted": False,
            }
        },
        1,
    )
