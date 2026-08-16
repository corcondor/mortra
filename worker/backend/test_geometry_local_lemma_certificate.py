from worker.backend.geometry_local_lemma_certificate import (
    external_homothety_boundary_certificates,
    external_homothety_tangent_certificate,
)


def test_external_homothety_certificate_replays_as_an_ideal_identity() -> None:
    certificate = external_homothety_tangent_certificate()
    assert certificate.replayed
    assert certificate.residual == "0"
    assert certificate.multipliers == ("nx", "ny", "r2", "-r1")
    assert len(certificate.certificate_sha256) == 64


def test_external_homothety_boundary_certificates_replay() -> None:
    collinear, ratio = external_homothety_boundary_certificates()
    assert collinear.replayed and ratio.replayed
    assert collinear.residual == ratio.residual == "0"
    assert "collinear" in collinear.theorem
    assert "ratio" in ratio.theorem
