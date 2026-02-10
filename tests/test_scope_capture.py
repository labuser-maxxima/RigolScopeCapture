"""Unit tests for scope_capture helper functions."""

import csv
import os
import sys
import tempfile
from unittest import mock

import pytest

# Ensure the repo root is on sys.path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scope_capture  # noqa: E402


# ---------------------------------------------------------------------------
# parse_timescale
# ---------------------------------------------------------------------------

class TestParseTimescale:
    def test_nanoseconds(self):
        assert scope_capture.parse_timescale("200ns") == pytest.approx(200e-9)

    def test_microseconds(self):
        assert scope_capture.parse_timescale("5us") == pytest.approx(5e-6)

    def test_milliseconds(self):
        assert scope_capture.parse_timescale("100ms") == pytest.approx(100e-3)

    def test_seconds(self):
        assert scope_capture.parse_timescale("1s") == pytest.approx(1.0)

    def test_plain_number(self):
        assert scope_capture.parse_timescale("0.001") == pytest.approx(1e-3)

    def test_whitespace(self):
        assert scope_capture.parse_timescale("  10ms  ") == pytest.approx(10e-3)

    def test_case_insensitive(self):
        assert scope_capture.parse_timescale("100MS") == pytest.approx(100e-3)
        assert scope_capture.parse_timescale("5US") == pytest.approx(5e-6)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            scope_capture.parse_timescale("abc")

    def test_invalid_number_raises(self):
        with pytest.raises(ValueError):
            scope_capture.parse_timescale("xxms")


# ---------------------------------------------------------------------------
# format_timescale
# ---------------------------------------------------------------------------

class TestFormatTimescale:
    def test_seconds(self):
        assert scope_capture.format_timescale(1.0) == "1s"
        assert scope_capture.format_timescale(5.0) == "5s"

    def test_milliseconds(self):
        assert scope_capture.format_timescale(100e-3) == "100ms"
        assert scope_capture.format_timescale(1e-3) == "1ms"

    def test_microseconds(self):
        assert scope_capture.format_timescale(5e-6) == "5us"

    def test_nanoseconds(self):
        assert scope_capture.format_timescale(200e-9) == "200ns"


# ---------------------------------------------------------------------------
# find_nearest_timescale
# ---------------------------------------------------------------------------

class TestFindNearestTimescale:
    def test_exact_match(self):
        assert scope_capture.find_nearest_timescale(100e-3) == pytest.approx(100e-3)

    def test_nearest_snap(self):
        # 120ms should snap to 100ms (closer than 200ms)
        assert scope_capture.find_nearest_timescale(120e-3) == pytest.approx(100e-3)

    def test_snap_up(self):
        # 160ms should snap to 200ms
        assert scope_capture.find_nearest_timescale(160e-3) == pytest.approx(200e-3)


# ---------------------------------------------------------------------------
# choose_memory_depth
# ---------------------------------------------------------------------------

class TestChooseMemoryDepth:
    def test_one_second(self):
        # total_time = 1s → all depths fit; pick the largest
        depth = scope_capture.choose_memory_depth(1.0)
        assert depth == 10_000_000

    def test_ten_seconds(self):
        depth = scope_capture.choose_memory_depth(10.0)
        assert depth == 10_000_000

    def test_very_short_time(self):
        # total_time = 10ns → even 1000 / 10e-9 = 1e11 > 1.25e9
        # Only the smallest depth if none fit → falls through to first
        depth = scope_capture.choose_memory_depth(10e-9)
        assert depth in scope_capture.MEMORY_DEPTHS

    def test_medium_time(self):
        # total_time = 10ms → 10M / 0.01 = 1e9 ≤ 1.25e9 → pick 10M
        depth = scope_capture.choose_memory_depth(10e-3)
        assert depth == 10_000_000

    def test_small_time(self):
        # total_time = 50ns → 1000/50e-9 = 2e10 > max.  Nothing fits cleanly.
        depth = scope_capture.choose_memory_depth(50e-9)
        assert depth == scope_capture.MEMORY_DEPTHS[0]


# ---------------------------------------------------------------------------
# parse_preamble
# ---------------------------------------------------------------------------

class TestParsePreamble:
    SAMPLE = "0,2,1000,1,1.000000e-06,0.000000e+00,0,4.000000e-03,0,128"

    def test_fields(self):
        p = scope_capture.parse_preamble(self.SAMPLE)
        assert p["format"] == 0
        assert p["type"] == 2
        assert p["points"] == 1000
        assert p["count"] == 1
        assert p["xincrement"] == pytest.approx(1e-6)
        assert p["xorigin"] == pytest.approx(0.0)
        assert p["xreference"] == pytest.approx(0.0)
        assert p["yincrement"] == pytest.approx(4e-3)
        assert p["yorigin"] == pytest.approx(0.0)
        assert p["yreference"] == pytest.approx(128.0)


# ---------------------------------------------------------------------------
# strip_tmc_header
# ---------------------------------------------------------------------------

class TestStripTmcHeader:
    def test_with_header(self):
        # Build a TMC block: #3010<10 bytes of payload>
        payload = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"
        header = b"#3010"
        raw = header + payload
        assert scope_capture.strip_tmc_header(raw) == payload

    def test_without_header(self):
        data = b"\xff\xfe\xfd"
        assert scope_capture.strip_tmc_header(data) == data


# ---------------------------------------------------------------------------
# save_csv
# ---------------------------------------------------------------------------

class TestSaveCsv:
    def test_single_channel(self, tmp_path):
        times = [0.0, 1e-6, 2e-6]
        voltages = [0.1, 0.2, 0.3]
        preamble = {}
        channel_data = {1: (times, voltages, preamble)}

        csv_path = str(tmp_path / "test.csv")
        scope_capture.save_csv(csv_path, channel_data)

        with open(csv_path) as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["Time (s)", "Channel 1 (V)"]
            rows = list(reader)
            assert len(rows) == 3

    def test_multi_channel(self, tmp_path):
        times = [0.0, 1e-6]
        ch1_v = [0.1, 0.2]
        ch2_v = [0.3, 0.4]
        preamble = {}
        channel_data = {
            1: (times, ch1_v, preamble),
            2: (times, ch2_v, preamble),
        }

        csv_path = str(tmp_path / "test_multi.csv")
        scope_capture.save_csv(csv_path, channel_data)

        with open(csv_path) as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["Time (s)", "Channel 1 (V)", "Channel 2 (V)"]
            rows = list(reader)
            assert len(rows) == 2
