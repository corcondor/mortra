from worker.backend.construction_block_proof_dag import (
    certify_construction_block_proof_dag,
)


def test_midpoint_goal_is_closed_by_replayed_block_and_separator_dag() -> None:
    result = certify_construction_block_proof_dag(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b",
    )

    assert result.status == "proved"
    assert result.exact_replay
    assert result.root.proved and result.root.replayed
    assert result.construction_nodes
    assert result.root.parent_node_ids
    assert result.all_local_certificates_replayed


def test_unrelated_free_point_goal_is_not_promoted() -> None:
    result = certify_construction_block_proof_dag(
        "a b c = triangle a b c; d = free d ? coll a b d",
        terminal_max_pairs=64,
    )

    assert result.status == "open"
    assert not result.exact_replay
    assert result.root.replayed
    assert not result.root.proved


def test_construction_dependencies_are_explicit_and_problem_independent() -> None:
    result = certify_construction_block_proof_dag(
        "a b c = triangle a b c; m = midpoint m a b; "
        "n = midpoint n m c ? coll m n c",
    )

    midpoint_nodes = [
        node
        for node in result.construction_nodes
        if "midpoint" in node.construction_vocabulary
    ]
    assert len(midpoint_nodes) == 2
    assert midpoint_nodes[0].node_id in midpoint_nodes[1].parent_node_ids
    assert len(midpoint_nodes[1].parent_node_ids) == 2
    assert len(result.certificate_sha256) == 64


def test_local_goal_certificate_is_a_root_parent_when_available() -> None:
    result = certify_construction_block_proof_dag(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b",
    )

    local_goal_nodes = [node for node in result.separator_nodes if node.goal_proved]
    if local_goal_nodes:
        assert all(
            node.node_id in result.root.parent_node_ids for node in local_goal_nodes
        )


def test_local_polynomial_lemmas_carry_replayed_typed_relations() -> None:
    result = certify_construction_block_proof_dag(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b",
    )

    certificates = tuple(
        certificate
        for node in (*result.local_elimination_nodes, *result.separator_nodes)
        for certificate in node.typed_relation_certificates
    ) + result.root.typed_relation_certificates
    assert certificates
    assert any(item.predicate == "coll" for item in certificates)
    assert all(item.exact_replay for item in certificates)


def test_open_typed_relations_condition_elimination_without_becoming_facts() -> None:
    result = certify_construction_block_proof_dag(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b",
        guidance_relations=(("cong", ("a", "m", "m", "b")),),
    )

    assert result.elimination_ordering_strategy == "obligation_conditioned"
    assert result.guidance_relations == ("cong(a,m,m,b)",)
    assert len(result.guidance_polynomials) == 1
    assert result.exact_replay


def test_coherent_and_branches_enable_normal_form_residual_control() -> None:
    relation = ("cong", ("a", "m", "m", "b"))
    result = certify_construction_block_proof_dag(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b",
        guidance_relations=(relation,),
        guidance_relation_branches=((relation,),),
    )

    assert result.elimination_ordering_strategy == "residual_conditioned"
    assert result.guidance_relation_branches == (("cong(a,m,m,b)",),)
    assert len(result.guidance_polynomial_branches) == 1
    assert result.exact_replay
