"""Read-only CED source-span feasibility and evidence-contract checks.

This file DOES NOT train or test an existing GeoCPU checkpoint. Neural smoke
checks use randomly initialized toy weights only. Run from a copy of the
2026-10-26 source snapshot containing numpy_grand.py and long_native_draft.py:
    python -m unittest -v test_span_readout_preflight.py
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import math
import unittest

try:
    import numpy as np
    from numpy_grand import GrandConfig, NumpyGrand
    from long_native_draft import LongNativeDraft
    NATIVE_AVAILABLE = True
except ImportError:
    NATIVE_AVAILABLE = False


@dataclass(frozen=True)
class SourceSpan:
    doc_id: str
    source_sha256: str
    start: int  # inclusive Unicode code-point offset, NOT token/byte offset
    end: int  # exclusive Unicode code-point offset


def copy_verified(text: str, doc_id: str, span: SourceSpan) -> str:
    if span.doc_id != doc_id:
        raise ValueError('source document mismatch')
    if sha256(text.encode('utf-8')).hexdigest() != span.source_sha256:
        raise ValueError('source text changed')
    if not (0 <= span.start < span.end <= len(text)):
        raise ValueError('invalid source span')
    return text[span.start:span.end]


def annotate(text: str, answer: str, doc_id: str, *, occurrence: int = 0) -> SourceSpan:
    """Fixture utility only; never serves as a learned answer locator."""
    if not answer:
        raise ValueError('empty answer cannot be annotated')
    found = -1
    for _ in range(occurrence + 1):
        found = text.find(answer, found + 1)
        if found < 0:
            raise ValueError('answer does not appear at requested occurrence')
    return SourceSpan(doc_id, sha256(text.encode('utf-8')).hexdigest(),
                      found, found + len(answer))


def select_or_abstain(text: str, doc_id: str, span: SourceSpan | None,
                      span_logit: float, null_logit: float, margin: float = 0.0) -> str | None:
    """Post-selector contract; this is NOT a calibrated trained selector."""
    if not all(math.isfinite(v) for v in (span_logit, null_logit, margin)):
        raise ValueError('non-finite scores')
    if span is None or span_logit <= null_logit + margin:
        return None
    return copy_verified(text, doc_id, span)


def toy_weights(config: GrandConfig) -> dict[str, np.ndarray]:
    """Random weights for API/shape test. NEVER pretrained model parameters."""
    rng = np.random.default_rng(17)
    weights = {}
    for name, shape in NumpyGrand.expected_shapes(config).items():
        if name.endswith('.weight') and ('norm.' in name or name == 'final_norm.weight'):
            value = np.ones(shape, np.float32)
        elif 'log_decay' in name:
            value = np.full(shape, -0.02, np.float32)
        elif 'gate' in name:
            value = np.zeros(shape, np.float32)
        else:
            value = rng.normal(0, 0.02, size=shape).astype(np.float32)
        weights[name] = value
    return weights


class EvidenceContractTests(unittest.TestCase):
    def test_unicode_and_provenance(self):
        source = '今日のラウエ実験では銅を用いた。'
        span = annotate(source, '銅', 'laue-001')
        self.assertEqual(copy_verified(source, 'laue-001', span), '銅')
        self.assertEqual(span.end - span.start, 1)
        with self.assertRaises(ValueError):
            copy_verified(source.replace('銅', '鉄'), 'laue-001', span)
        with self.assertRaises(ValueError):
            copy_verified(source, 'different-document', span)
        with self.assertRaises(ValueError):
            copy_verified(source, 'laue-001',
                          SourceSpan('laue-001', span.source_sha256, -1, 1))

    def test_repeated_mentions_are_addressed_not_guessed(self):
        source = '銅は比較例。正解は鉄。銅は別の例。'
        spans = [annotate(source, '銅', 'd', occurrence=i) for i in (0, 1)]
        self.assertNotEqual(spans[0].start, spans[1].start)
        self.assertEqual([copy_verified(source, 'd', sp) for sp in spans], ['銅', '銅'])

    def test_order_swaps_require_relation_evidence(self):
        a = '本番の試料は銅でした。比較用試料は鉄でした。'
        b = '本番の試料は鉄でした。比較用試料は銅でした。'
        self.assertEqual(Counter(a), Counter(b))
        self.assertEqual(copy_verified(a, 'a', annotate(a, '銅', 'a')), '銅')
        self.assertEqual(copy_verified(b, 'b', annotate(b, '鉄', 'b')), '鉄')
        # Equal lossy bags with different answers prove no deterministic
        # readout of that bag can solve both. This says nothing about CED.

    def test_no_answer_not_hallucinated(self):
        source = '銅は比較用である。'
        with self.assertRaises(ValueError):
            annotate(source, '鉄', 'missing')
        self.assertIsNone(select_or_abstain(source, 'missing', None, -2., 0.))
        copper = annotate(source, '銅', 'missing')
        self.assertIsNone(select_or_abstain(source, 'missing', copper, 0.2, 0.4))
        self.assertEqual(select_or_abstain(source, 'missing', copper, 0.8, 0.4), '銅')


@unittest.skipUnless(NATIVE_AVAILABLE, "requires a separate read-only copy of native runtime and NumPy")
class NativeCodePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = GrandConfig(vocab_size=20, d_model=8, encoder_layers=1,
                                 decoder_layers=1, ffn_dim=16, heads=2,
                                 key_dim=4, value_dim=4, max_positions=16)
        cls.weights = toy_weights(cls.config)
        cls.base = NumpyGrand(cls.config, cls.weights, select_after=0)
        cls.long = LongNativeDraft(cls.config, cls.weights, max_context=32,
                                   query_chunk=4, select_after=0)

    def test_timeline_features_accessible_without_modifying_native(self):
        ids = np.array([[1, 3, 5, 7, 9]], np.int64)
        out = self.base.forward_output(ids)
        self.assertEqual(out.features.shape, (1, 5, 8))
        self.assertTrue(np.isfinite(out.features).all())
        self.assertTrue(all(not w.flags.writeable for w in self.base.weights.values()))

    def test_short_forward_is_exactly_original(self):
        ids = np.array([[1, 3, 5, 7, 9]], np.int64)
        a, b = self.base.forward_output(ids), self.long.forward_output(ids)
        np.testing.assert_array_equal(a.features, b.features)
        np.testing.assert_array_equal(a.logits, b.logits)

    def test_long_prompt_keeps_per_position_features(self):
        ids = (np.arange(22) % self.config.vocab_size).reshape(1, -1)
        out = self.long.prefill_prompt(ids)
        self.assertEqual(out.features.shape, (1, 22, 8))
        self.assertEqual(out.logits.shape, (1, 1, 20))
        self.assertTrue(np.isfinite(out.features).all())
        self.assertEqual(out.state.positions[0], 22)


if __name__ == '__main__':
    unittest.main()
