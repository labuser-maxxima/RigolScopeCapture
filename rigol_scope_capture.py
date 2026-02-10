#!/usr/bin/env python3
"""
Rigol DHO804 Oscilloscope Capture Tool

This script allows you to:
1. Set the time scale on a Rigol DHO804 oscilloscope
2. Automatically adjust memory depth to capture the full screen duration
3. Capture both screen image (PNG) and raw waveform data

Based on the DHO800/DHO900 Programming Guide.
"""

import pyvisa
import sys
import os
from datetime import datetime
import numpy as np


class RigolDHO804:
    """Class for communicating with Rigol DHO804 oscilloscope"""
    
    # Memory depth options for DHO800 series (in samples)
    # Based on DHO800 specs: up to 25 Mpts single channel
    MEMORY_DEPTH_OPTIONS = [
        10000,      # 10K
        100000,     # 100K
        1000000,    # 1M
        10000000,   # 10M
        25000000,   # 25M (max for DHO800 series)
    ]
    
    # Max sample rate: 1.25 GS/s for single channel
    MAX_SAMPLE_RATE = 1.25e9
    
    # Horizontal divisions on screen
    HORIZONTAL_DIVISIONS = 10
    
    def __init__(self, resource_name=None):
        """
        Initialize connection to the oscilloscope
        
        Args:
            resource_name: VISA resource name (e.g., 'USB0::0x1AB1::0x0515::DHO8A...')
                          If None, will try to auto-detect
        """
        self.rm = pyvisa.ResourceManager()
        
        if resource_name is None:
            # Try to auto-detect Rigol DHO800 series
            resources = self.rm.list_resources()
            for resource in resources:
                if 'RIGOL' in resource.upper() or 'DHO' in resource.upper():
                    resource_name = resource
                    break
            
            if resource_name is None:
                print("Available VISA resources:")
                for resource in resources:
                    print(f"  - {resource}")
                raise ValueError("Could not auto-detect Rigol oscilloscope. Please specify resource_name.")
        
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = 10000  # 10 second timeout
        
        # Verify connection
        idn = self.inst.query('*IDN?')
        print(f"Connected to: {idn.strip()}")
    
    def set_timescale(self, time_per_div):
        """
        Set the horizontal time scale
        
        Args:
            time_per_div: Time per division in seconds (e.g., 0.001 for 1ms/div)
        """
        self.inst.write(f':TIMebase:SCALe {time_per_div}')
        # Verify the setting
        actual = float(self.inst.query(':TIMebase:SCALe?'))
        print(f"Time scale set to: {actual} s/div")
        return actual
    
    def calculate_required_memory_depth(self, time_per_div, sample_rate=None):
        """
        Calculate required memory depth for the given time scale
        
        Args:
            time_per_div: Time per division in seconds
            sample_rate: Desired sample rate (if None, uses max sample rate)
        
        Returns:
            Tuple of (memory_depth, actual_sample_rate)
        """
        # Total time on screen
        total_time = time_per_div * self.HORIZONTAL_DIVISIONS
        
        # If no sample rate specified, try to use max sample rate
        if sample_rate is None:
            sample_rate = self.MAX_SAMPLE_RATE
        
        # Calculate required memory depth
        required_depth = int(total_time * sample_rate)
        
        # Find the smallest memory depth option that fits our needs
        selected_depth = None
        for depth in self.MEMORY_DEPTH_OPTIONS:
            if depth >= required_depth:
                selected_depth = depth
                break
        
        if selected_depth is None:
            # If required depth exceeds max, use max and reduce sample rate
            selected_depth = self.MEMORY_DEPTH_OPTIONS[-1]
            actual_sample_rate = selected_depth / total_time
            print(f"Warning: Required depth exceeds maximum. Reducing sample rate.")
        else:
            actual_sample_rate = sample_rate
        
        return selected_depth, actual_sample_rate
    
    def set_memory_depth(self, depth):
        """
        Set the memory depth
        
        Args:
            depth: Memory depth in samples
        """
        # Convert to appropriate format for SCPI command
        if depth >= 1000000:
            depth_str = f"{depth/1000000:.0f}M"
        elif depth >= 1000:
            depth_str = f"{depth/1000:.0f}K"
        else:
            depth_str = str(depth)
        
        self.inst.write(f':ACQuire:MDEPth {depth_str}')
        
        # Verify the setting
        actual = self.inst.query(':ACQuire:MDEPth?').strip()
        print(f"Memory depth set to: {actual}")
        return actual
    
    def capture_screenshot(self, filename=None):
        """
        Capture oscilloscope screen as PNG image
        
        Args:
            filename: Output filename (if None, generates timestamp-based name)
        
        Returns:
            Filename where screenshot was saved
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scope_screenshot_{timestamp}.png"
        
        # Request display data in PNG format
        self.inst.write(':DISP:DATA?')
        
        # Read the binary data
        # The response includes a header, need to parse it
        raw_data = self.inst.read_raw()
        
        # Remove SCPI header (typically starts with '#' followed by length info)
        # Format: #<digit><length><data>
        # where <digit> tells how many digits in <length>
        if raw_data[0:1] == b'#':
            header_length_digits = int(chr(raw_data[1]))
            header_length = 2 + header_length_digits
            image_data = raw_data[header_length:-1]  # -1 to remove trailing newline
        else:
            image_data = raw_data
        
        # Save to file
        with open(filename, 'wb') as f:
            f.write(image_data)
        
        print(f"Screenshot saved to: {filename}")
        return filename
    
    def capture_waveform(self, channel=1, filename=None):
        """
        Capture raw waveform data from specified channel
        
        Args:
            channel: Channel number (1-4)
            filename: Output filename for CSV (if None, generates timestamp-based name)
        
        Returns:
            Tuple of (time_array, voltage_array, filename)
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"waveform_ch{channel}_{timestamp}.csv"
        
        # Stop acquisition for consistent data
        self.inst.write(':STOP')
        
        # Configure waveform source and format
        self.inst.write(f':WAV:SOUR CHAN{channel}')
        self.inst.write(':WAV:MODE NORM')
        self.inst.write(':WAV:FORM BYTE')
        
        # Get waveform preamble for scaling information
        preamble = self.inst.query(':WAV:PRE?')
        preamble_parts = preamble.split(',')
        
        # Parse preamble
        # Format: <format>,<type>,<points>,<count>,<xincrement>,<xorigin>,<xreference>,<yincrement>,<yorigin>,<yreference>
        points = int(preamble_parts[2])
        x_increment = float(preamble_parts[4])
        x_origin = float(preamble_parts[5])
        x_reference = float(preamble_parts[6])
        y_increment = float(preamble_parts[7])
        y_origin = float(preamble_parts[8])
        y_reference = float(preamble_parts[9])
        
        # Get the waveform data
        self.inst.write(':WAV:DATA?')
        raw_data = self.inst.read_raw()
        
        # Remove SCPI header
        if raw_data[0:1] == b'#':
            header_length_digits = int(chr(raw_data[1]))
            header_length = 2 + header_length_digits
            wave_data = raw_data[header_length:-1]
        else:
            wave_data = raw_data
        
        # Convert to numpy array
        data_array = np.frombuffer(wave_data, dtype=np.uint8)
        
        # Scale the data to get actual voltage values
        voltage_array = ((data_array - y_reference) * y_increment) + y_origin
        
        # Generate time array
        time_array = ((np.arange(len(data_array)) - x_reference) * x_increment) + x_origin
        
        # Save to CSV
        with open(filename, 'w') as f:
            f.write("Time (s),Voltage (V)\n")
            for t, v in zip(time_array, voltage_array):
                f.write(f"{t},{v}\n")
        
        print(f"Waveform data saved to: {filename}")
        print(f"  Points captured: {len(data_array)}")
        print(f"  Time range: {time_array[0]:.6e} to {time_array[-1]:.6e} s")
        print(f"  Voltage range: {voltage_array.min():.3f} to {voltage_array.max():.3f} V")
        
        # Resume acquisition
        self.inst.write(':RUN')
        
        return time_array, voltage_array, filename
    
    def close(self):
        """Close the connection to the oscilloscope"""
        self.inst.close()
        self.rm.close()


def parse_time_input(time_str):
    """
    Parse user input for time scale
    
    Args:
        time_str: String like '1ms', '10us', '5s', etc.
    
    Returns:
        Time in seconds
    """
    time_str = time_str.strip().lower()
    
    # Extract number and unit
    import re
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


def main():
    """Main function"""
    print("=" * 60)
    print("Rigol DHO804 Oscilloscope Capture Tool")
    print("=" * 60)
    print()
    
    # Connect to oscilloscope
    print("Connecting to oscilloscope...")
    try:
        scope = RigolDHO804()
    except Exception as e:
        print(f"Error connecting to oscilloscope: {e}")
        print("\nMake sure:")
        print("  1. The oscilloscope is powered on")
        print("  2. It's connected via USB or LAN")
        print("  3. You have the proper VISA drivers installed")
        return 1
    
    print()
    
    # Get current time scale
    current_timescale = float(scope.inst.query(':TIMebase:SCALe?'))
    print(f"Current time scale: {current_timescale} s/div")
    print()
    
    # Ask user for desired time scale
    print("Enter desired time scale per division:")
    print("  Examples: 1ms, 10us, 5s, 100ns")
    print("  Or press Enter to keep current setting")
    time_input = input("Time/div: ").strip()
    
    if time_input:
        try:
            time_per_div = parse_time_input(time_input)
        except ValueError as e:
            print(f"Error: {e}")
            scope.close()
            return 1
        
        print()
        print(f"Setting time scale to {time_per_div} s/div...")
        
        # Calculate and set memory depth
        mem_depth, sample_rate = scope.calculate_required_memory_depth(time_per_div)
        print(f"Calculated memory depth: {mem_depth} samples")
        print(f"Expected sample rate: {sample_rate/1e6:.2f} MS/s")
        print()
        
        # Apply settings
        scope.set_timescale(time_per_div)
        scope.set_memory_depth(mem_depth)
    else:
        print("Keeping current time scale settings")
    
    print()
    print("-" * 60)
    
    # Capture screenshot
    print("Capturing screenshot...")
    screenshot_file = scope.capture_screenshot()
    
    print()
    
    # Capture waveforms for all active channels
    print("Capturing waveform data...")
    
    # Check which channels are enabled
    # For simplicity, we'll capture channel 1
    # In a full implementation, you'd query which channels are active
    print("Capturing Channel 1...")
    time_data, voltage_data, waveform_file = scope.capture_waveform(channel=1)
    
    print()
    print("-" * 60)
    print("Capture complete!")
    print(f"  Screenshot: {screenshot_file}")
    print(f"  Waveform:   {waveform_file}")
    print("-" * 60)
    
    # Close connection
    scope.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
