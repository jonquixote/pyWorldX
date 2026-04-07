"""Tests for stochastic state management."""

from __future__ import annotations

import numpy as np

from pyworldx.core.stochastic import StochasticState


class TestStochasticStateConstruction:
    def test_master_seed_stored(self) -> None:
        ss = StochasticState(master_seed=42)
        assert ss.master_seed == 42

    def test_initial_state_empty(self) -> None:
        ss = StochasticState(master_seed=0)
        assert ss.stream_seeds == {}
        assert ss.draws_used == {}


class TestGetStream:
    def test_returns_generator(self) -> None:
        ss = StochasticState(master_seed=42)
        gen = ss.get_stream("test_stream")
        assert isinstance(gen, np.random.Generator)

    def test_named_streams_deterministic(self) -> None:
        """Same name with same master seed produces the same output."""
        ss1 = StochasticState(master_seed=99)
        ss2 = StochasticState(master_seed=99)
        gen1 = ss1.get_stream("alpha")
        gen2 = ss2.get_stream("alpha")
        vals1 = gen1.random(10)
        vals2 = gen2.random(10)
        np.testing.assert_array_equal(vals1, vals2)

    def test_different_names_different_streams(self) -> None:
        ss = StochasticState(master_seed=42)
        gen_a = ss.get_stream("stream_a")
        gen_b = ss.get_stream("stream_b")
        vals_a = gen_a.random(10)
        vals_b = gen_b.random(10)
        assert not np.array_equal(vals_a, vals_b)

    def test_stream_seed_registered(self) -> None:
        ss = StochasticState(master_seed=7)
        ss.get_stream("my_stream")
        assert "my_stream" in ss.stream_seeds
        assert "my_stream" in ss.draws_used
        assert ss.draws_used["my_stream"] == 0


class TestRecordDraws:
    def test_tracks_usage(self) -> None:
        ss = StochasticState(master_seed=42)
        ss.get_stream("s1")
        ss.record_draws("s1", 5)
        assert ss.draws_used["s1"] == 5

    def test_accumulates(self) -> None:
        ss = StochasticState(master_seed=42)
        ss.get_stream("s1")
        ss.record_draws("s1", 3)
        ss.record_draws("s1", 7)
        assert ss.draws_used["s1"] == 10

    def test_record_without_prior_get_stream(self) -> None:
        ss = StochasticState(master_seed=42)
        ss.record_draws("unknown", 2)
        assert ss.draws_used["unknown"] == 2
