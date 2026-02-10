#!/usr/bin/env python3
"""
Unit tests for RigolScopeCapture

These tests verify core functionality without requiring actual hardware.
"""

import unittest
import sys
import re


def parse_time_input(time_str):
    """
    Parse user input for time scale (standalone version for testing)
    
    Args:
        time_str: String like '1ms', '10us', '5s', etc.
    
    Returns:
        Time in seconds
    """
    time_str = time_str.strip().lower()
    
    # Extract number and unit
    match = re.match(r'([0-9.]+)\s*([a-z]+)', time_str)
    
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
    
    value = float(match.group(1))
    unit = match.group(2)
    
    # Convert to seconds
    multipliers = {
        's': 1.0,
        'ms': 1e-3,
        'us': 1e-6,
        'μs': 1e-6,
        'ns': 1e-9,
    }
    
    if unit not in multipliers:
        raise ValueError(f"Unknown time unit: {unit}. Use s, ms, us, or ns")
    
    return value * multipliers[unit]


def calculate_required_memory_depth(time_per_div, sample_rate=None, max_sample_rate=1.25e9):
    """
    Calculate required memory depth for the given time scale (standalone version for testing)
    
    Args:
        time_per_div: Time per division in seconds
        sample_rate: Desired sample rate (if None, uses max sample rate)
        max_sample_rate: Maximum sample rate of the oscilloscope
    
    Returns:
        Tuple of (memory_depth, actual_sample_rate)
    """
    MEMORY_DEPTH_OPTIONS = [10000, 100000, 1000000, 10000000, 25000000]
    HORIZONTAL_DIVISIONS = 10
    
    # Total time on screen
    total_time = time_per_div * HORIZONTAL_DIVISIONS
    
    # If no sample rate specified, try to use max sample rate
    if sample_rate is None:
        sample_rate = max_sample_rate
    
    # Calculate required memory depth
    required_depth = int(total_time * sample_rate)
    
    # Find the smallest memory depth option that fits our needs
    selected_depth = None
    for depth in MEMORY_DEPTH_OPTIONS:
        if depth >= required_depth:
            selected_depth = depth
            break
    
    if selected_depth is None:
        # If required depth exceeds max, use max and reduce sample rate
        selected_depth = MEMORY_DEPTH_OPTIONS[-1]
        actual_sample_rate = selected_depth / total_time
    else:
        actual_sample_rate = sample_rate
    
    return selected_depth, actual_sample_rate


class TestTimeParser(unittest.TestCase):
    """Test time input parsing"""
    
    def test_parse_seconds(self):
        """Test parsing seconds"""
        self.assertAlmostEqual(parse_time_input('1s'), 1.0)
        self.assertAlmostEqual(parse_time_input('5s'), 5.0)
        self.assertAlmostEqual(parse_time_input('0.5s'), 0.5)
    
    def test_parse_milliseconds(self):
        """Test parsing milliseconds"""
        self.assertAlmostEqual(parse_time_input('1ms'), 0.001)
        self.assertAlmostEqual(parse_time_input('10ms'), 0.01)
        self.assertAlmostEqual(parse_time_input('100ms'), 0.1)
    
    def test_parse_microseconds(self):
        """Test parsing microseconds"""
        self.assertAlmostEqual(parse_time_input('1us'), 1e-6)
        self.assertAlmostEqual(parse_time_input('10us'), 10e-6)
        self.assertAlmostEqual(parse_time_input('100us'), 100e-6)
    
    def test_parse_nanoseconds(self):
        """Test parsing nanoseconds"""
        self.assertAlmostEqual(parse_time_input('1ns'), 1e-9)
        self.assertAlmostEqual(parse_time_input('10ns'), 10e-9)
        self.assertAlmostEqual(parse_time_input('100ns'), 100e-9)
    
    def test_parse_with_spaces(self):
        """Test parsing with spaces"""
        self.assertAlmostEqual(parse_time_input('10 ms'), 0.01)
        self.assertAlmostEqual(parse_time_input('5 us'), 5e-6)
    
    def test_parse_case_insensitive(self):
        """Test case insensitivity"""
        self.assertAlmostEqual(parse_time_input('10MS'), 0.01)
        self.assertAlmostEqual(parse_time_input('5US'), 5e-6)
    
    def test_parse_invalid_format(self):
        """Test invalid format"""
        with self.assertRaises(ValueError):
            parse_time_input('invalid')
        with self.assertRaises(ValueError):
            parse_time_input('10')
        with self.assertRaises(ValueError):
            parse_time_input('ms10')
    
    def test_parse_invalid_unit(self):
        """Test invalid unit"""
        with self.assertRaises(ValueError):
            parse_time_input('10hz')
        with self.assertRaises(ValueError):
            parse_time_input('10minutes')


class TestMemoryDepthCalculation(unittest.TestCase):
    """Test memory depth calculation"""
    
    def test_small_timescale(self):
        """Test calculation for small time scale (1ms/div)"""
        time_per_div = 0.001  # 1ms
        mem_depth, sample_rate = calculate_required_memory_depth(time_per_div)
        
        # Total time: 10ms, at 1.25GS/s = 12.5M samples
        # Should select 25M memory depth
        self.assertEqual(mem_depth, 25000000)
        self.assertEqual(sample_rate, 1.25e9)
    
    def test_medium_timescale(self):
        """Test calculation for medium time scale (10ms/div)"""
        time_per_div = 0.01  # 10ms
        mem_depth, sample_rate = calculate_required_memory_depth(time_per_div)
        
        # Total time: 100ms, at 1.25GS/s = 125M samples
        # Should select 25M and reduce sample rate
        self.assertEqual(mem_depth, 25000000)
        # Sample rate should be reduced: 25M / 100ms = 250MS/s
        self.assertAlmostEqual(sample_rate, 250e6)
    
    def test_large_timescale(self):
        """Test calculation for large time scale (1s/div)"""
        time_per_div = 1.0  # 1s
        mem_depth, sample_rate = calculate_required_memory_depth(time_per_div)
        
        # Total time: 10s, at 1.25GS/s = 12.5G samples
        # Should select 25M and reduce sample rate significantly
        self.assertEqual(mem_depth, 25000000)
        # Sample rate: 25M / 10s = 2.5MS/s
        self.assertAlmostEqual(sample_rate, 2.5e6)
    
    def test_exact_fit(self):
        """Test when memory depth exactly fits"""
        # 1M samples at 1MS/s = 1 second total
        # Time per div = 0.1s (100ms) -> total 1s
        time_per_div = 0.1
        sample_rate = 1e6
        mem_depth, actual_sample_rate = calculate_required_memory_depth(time_per_div, sample_rate)
        
        self.assertEqual(mem_depth, 1000000)
        self.assertEqual(actual_sample_rate, sample_rate)
    
    def test_very_fast_timescale(self):
        """Test very fast time scale (100ns/div)"""
        time_per_div = 100e-9  # 100ns
        mem_depth, sample_rate = calculate_required_memory_depth(time_per_div)
        
        # Total time: 1us, at 1.25GS/s = 1250 samples
        # Should select 10K memory depth
        self.assertEqual(mem_depth, 10000)
        self.assertEqual(sample_rate, 1.25e9)


class TestMemoryDepthLogic(unittest.TestCase):
    """Test memory depth selection logic"""
    
    def test_all_timescales(self):
        """Test various time scales to ensure proper memory selection"""
        test_cases = [
            # (time_per_div, expected_min_depth)
            (1e-9, 10000),      # 1ns/div -> 10ns total
            (1e-6, 10000),      # 1us/div -> 10us total
            (1e-3, 100000),     # 1ms/div -> 10ms total
            (0.01, 25000000),   # 10ms/div -> 100ms total (exceeds max)
            (0.1, 25000000),    # 100ms/div -> 1s total (exceeds max)
            (1.0, 25000000),    # 1s/div -> 10s total (exceeds max)
        ]
        
        for time_per_div, expected_min_depth in test_cases:
            mem_depth, _ = calculate_required_memory_depth(time_per_div)
            self.assertGreaterEqual(mem_depth, expected_min_depth,
                f"Failed for {time_per_div}s/div")


def main():
    """Run unit tests"""
    # Run tests
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
