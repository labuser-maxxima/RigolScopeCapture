#!/usr/bin/env python3
"""
Example script demonstrating programmatic usage of the RigolDHO804 class.

This script shows how to use the RigolDHO804 class in your own code
to automate oscilloscope capture tasks.
"""

from rigol_scope_capture import RigolDHO804, parse_time_input
import sys


def example_basic_capture():
    """Example: Basic screenshot and waveform capture"""
    print("Example 1: Basic Capture")
    print("-" * 50)
    
    # Connect to oscilloscope
    scope = RigolDHO804()
    
    # Capture with current settings
    screenshot_file = scope.capture_screenshot('example_screenshot.png')
    time_data, voltage_data, waveform_file = scope.capture_waveform(
        channel=1, 
        filename='example_waveform.csv'
    )
    
    print(f"Captured {len(time_data)} points")
    
    # Clean up
    scope.close()
    print()


def example_custom_timescale():
    """Example: Set custom time scale and capture"""
    print("Example 2: Custom Time Scale")
    print("-" * 50)
    
    # Connect to oscilloscope
    scope = RigolDHO804()
    
    # Set time scale to 5ms/div
    time_per_div = parse_time_input('5ms')
    print(f"Setting time scale to {time_per_div} s/div")
    
    scope.set_timescale(time_per_div)
    
    # Calculate and set memory depth
    mem_depth, sample_rate = scope.calculate_required_memory_depth(time_per_div)
    print(f"Required memory depth: {mem_depth} samples")
    print(f"Sample rate: {sample_rate/1e6:.2f} MS/s")
    
    scope.set_memory_depth(mem_depth)
    
    # Capture data
    scope.capture_screenshot('example_5ms.png')
    scope.capture_waveform(channel=1, filename='example_5ms.csv')
    
    # Clean up
    scope.close()
    print()


def example_multiple_timescales():
    """Example: Capture at multiple time scales"""
    print("Example 3: Multiple Time Scales")
    print("-" * 50)
    
    # Connect to oscilloscope
    scope = RigolDHO804()
    
    # Define time scales to capture
    time_scales = ['1ms', '10ms', '100ms']
    
    for time_str in time_scales:
        time_per_div = parse_time_input(time_str)
        print(f"\nCapturing at {time_str}/div...")
        
        # Set time scale
        scope.set_timescale(time_per_div)
        
        # Calculate and set memory depth
        mem_depth, sample_rate = scope.calculate_required_memory_depth(time_per_div)
        scope.set_memory_depth(mem_depth)
        
        # Capture with descriptive filenames
        scope.capture_screenshot(f'example_{time_str}.png')
        scope.capture_waveform(channel=1, filename=f'example_{time_str}.csv')
        
        print(f"  Captured at {sample_rate/1e6:.2f} MS/s with {mem_depth} samples")
    
    # Clean up
    scope.close()
    print()


def example_analyze_waveform():
    """Example: Capture and analyze waveform data"""
    print("Example 4: Waveform Analysis")
    print("-" * 50)
    
    import numpy as np
    
    # Connect to oscilloscope
    scope = RigolDHO804()
    
    # Capture waveform
    time_data, voltage_data, filename = scope.capture_waveform(channel=1)
    
    # Perform simple analysis
    print(f"\nWaveform Statistics:")
    print(f"  Points: {len(voltage_data)}")
    print(f"  Mean voltage: {np.mean(voltage_data):.3f} V")
    print(f"  Std deviation: {np.std(voltage_data):.3f} V")
    print(f"  Min voltage: {np.min(voltage_data):.3f} V")
    print(f"  Max voltage: {np.max(voltage_data):.3f} V")
    print(f"  Peak-to-peak: {np.ptp(voltage_data):.3f} V")
    
    # Clean up
    scope.close()
    print()


def main():
    """Run all examples"""
    print("=" * 60)
    print("Rigol DHO804 - Programmatic Usage Examples")
    print("=" * 60)
    print()
    
    try:
        # Run each example
        example_basic_capture()
        example_custom_timescale()
        example_multiple_timescales()
        example_analyze_waveform()
        
        print("=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure:")
        print("  1. The oscilloscope is connected and powered on")
        print("  2. VISA drivers are properly installed")
        print("  3. You have the required Python packages installed")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
