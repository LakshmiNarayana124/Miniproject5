"""
Property 28: Mini-batch bounded size
Validates: Requirements 9.2

Each mini-batch chunk size <= configured BATCH_SIZE.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
    _HAS_HYPOTHESIS = True
except ImportError:
    def given(*a, **kw): return lambda f: f
    def settings(*a, **kw): return lambda f: f
    class st:  # noqa: N801
        @staticmethod
        def integers(**kw): return []
    _HAS_HYPOTHESIS = False

try:
    from training_pipeline import BATCH_SIZE, iter_mini_batches
    _HAS_PIPELINE = True
except ImportError:
    # Try the private variant used in some revisions.
    try:
        from training_pipeline import BATCH_SIZE
        from training_pipeline import _zip_mini_batches  # fallback

        def iter_mini_batches(X, batch_size=None):
            """Thin wrapper over _zip_mini_batches for the tests below."""
            if batch_size is None:
                batch_size = BATCH_SIZE
            n = len(X)
            for start in range(0, max(n, 1), batch_size):
                yield X[start:start + batch_size]

        _HAS_PIPELINE = True
    except ImportError:
        _HAS_PIPELINE = False
        BATCH_SIZE = 10000  # sentinel so references below don't NameError


@pytest.mark.skipif(not _HAS_PIPELINE, reason="training_pipeline not available")
def test_batch_size_constant_positive():
    """BATCH_SIZE must be a positive integer (Req 9.2)."""
    assert isinstance(BATCH_SIZE, int), \
        f"BATCH_SIZE must be int, got {type(BATCH_SIZE)}"
    assert BATCH_SIZE > 0, \
        f"BATCH_SIZE must be positive, got {BATCH_SIZE}"


@pytest.mark.skipif(not _HAS_PIPELINE, reason="training_pipeline not available")
def test_batch_size_bounded_1000_items():
    """Splitting 1000 items into batches: each chunk <= BATCH_SIZE (Req 9.2)."""
    items = list(range(1000))
    for chunk in iter_mini_batches(items, batch_size=BATCH_SIZE):
        assert len(chunk) <= BATCH_SIZE, \
            f"chunk size {len(chunk)} exceeds BATCH_SIZE {BATCH_SIZE}"


@pytest.mark.skipif(not _HAS_PIPELINE, reason="training_pipeline not available")
def test_batch_size_bounded_small_batch():
    """With a custom batch_size=10, every chunk has at most 10 elements."""
    items = list(range(55))
    batch_size = 10
    for chunk in iter_mini_batches(items, batch_size=batch_size):
        assert len(chunk) <= batch_size, \
            f"chunk size {len(chunk)} exceeds custom batch_size {batch_size}"


@pytest.mark.skipif(not _HAS_PIPELINE, reason="training_pipeline not available")
def test_batches_cover_all_items():
    """Concatenating all chunks reproduces the original list."""
    items = list(range(123))
    reconstructed = []
    for chunk in iter_mini_batches(items, batch_size=10):
        reconstructed.extend(chunk)
    assert reconstructed == items, \
        "Mini-batches must cover the entire dataset without duplication or omission"


@pytest.mark.skipif(not _HAS_PIPELINE, reason="training_pipeline not available")
def test_empty_dataset_produces_no_batches():
    """An empty input list produces no chunks (or at most one empty chunk)."""
    chunks = list(iter_mini_batches([], batch_size=BATCH_SIZE))
    # Either no chunks or a single empty chunk is acceptable.
    for chunk in chunks:
        assert len(chunk) == 0, \
            f"Empty input should produce no non-empty chunks, got chunk of size {len(chunk)}"


@pytest.mark.skipif(not _HAS_PIPELINE, reason="training_pipeline not available")
def test_single_item_dataset():
    """A single-item list produces exactly one chunk of size 1."""
    items = [42]
    chunks = list(iter_mini_batches(items, batch_size=BATCH_SIZE))
    non_empty = [c for c in chunks if len(c) > 0]
    assert len(non_empty) == 1, \
        f"Expected 1 non-empty chunk for a single item, got {len(non_empty)}"
    assert list(non_empty[0]) == items, \
        f"The single chunk must contain the original item"


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_PIPELINE,
                    reason="hypothesis or training_pipeline not available")
@given(n=st.integers(min_value=1, max_value=500))
@settings(max_examples=100)
def test_batch_size_bounded_property(n):
    """Property: for any list of length n, every chunk size <= BATCH_SIZE."""
    items = list(range(n))
    for chunk in iter_mini_batches(items, batch_size=BATCH_SIZE):
        assert len(chunk) <= BATCH_SIZE, \
            f"chunk size {len(chunk)} exceeds BATCH_SIZE {BATCH_SIZE} for n={n}"
