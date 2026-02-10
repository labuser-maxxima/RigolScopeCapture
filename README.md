# RigolScopeCapture

A Python tool for capturing screenshots and waveform data from Rigol DHO804 oscilloscopes with automatic time scale and memory depth configuration.

## Features

- 🎯 **Interactive Time Scale Selection**: Ask user for desired time scale and automatically configure the oscilloscope
- 📊 **Automatic Memory Depth Calculation**: Intelligently calculates and sets the optimal memory depth to capture the full screen duration
- 📸 **Screenshot Capture**: Save oscilloscope display as PNG images
- 📈 **Raw Waveform Data**: Export actual waveform data to CSV files with proper time and voltage scaling
- 🔌 **Auto-Detection**: Automatically detects connected Rigol oscilloscopes via USB or LAN

## Based on DHO800/DHO900 Programming Guide

This implementation follows the official Rigol DHO800/DHO900 Programming Guide specifications for:
- Time scale settings (`:TIMebase:SCALe`)
- Memory depth configuration (`:ACQuire:MDEPth`)
- Screenshot capture (`:DISP:DATA?`)
- Waveform data acquisition (`:WAV:DATA?`)

## Requirements

- Python 3.7 or higher
- Rigol DHO804 (or other DHO800/DHO900 series) oscilloscope
- USB or LAN connection to the oscilloscope
- VISA drivers (NI-VISA or similar)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/labuser-maxxima/RigolScopeCapture.git
cd RigolScopeCapture
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Make sure you have VISA drivers installed:
   - **Windows/Mac**: Install [NI-VISA](https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html)
   - **Linux**: PyVISA-py (already included in requirements.txt) provides a pure-Python backend

## Usage

### Basic Usage

Simply run the script:
```bash
python rigol_scope_capture.py
```

The script will:
1. Auto-detect and connect to your Rigol oscilloscope
2. Show the current time scale setting
3. Ask you for the desired time scale (or press Enter to keep current)
4. Automatically calculate and set the appropriate memory depth
5. Capture both a screenshot and waveform data
6. Save files with timestamps

### Example Session

```
============================================================
Rigol DHO804 Oscilloscope Capture Tool
============================================================

Connecting to oscilloscope...
Connected to: RIGOL TECHNOLOGIES,DHO804,DHO8A...,00.01.02

Current time scale: 0.001 s/div

Enter desired time scale per division:
  Examples: 1ms, 10us, 5s, 100ns
  Or press Enter to keep current setting
Time/div: 10ms

Setting time scale to 0.01 s/div...
Calculated memory depth: 1000000 samples
Expected sample rate: 1000.00 MS/s

Time scale set to: 0.01 s/div
Memory depth set to: 1M

------------------------------------------------------------
Capturing screenshot...
Screenshot saved to: scope_screenshot_20260210_150530.png

Capturing waveform data...
Capturing Channel 1...
Waveform data saved to: waveform_ch1_20260210_150530.csv
  Points captured: 1000000
  Time range: -5.000000e-02 to 5.000000e-02 s
  Voltage range: -1.234 to 3.456 V

------------------------------------------------------------
Capture complete!
  Screenshot: scope_screenshot_20260210_150530.png
  Waveform:   waveform_ch1_20260210_150530.csv
------------------------------------------------------------
```

### Time Scale Input Formats

The script accepts various time scale formats:
- `1s` - 1 second per division
- `10ms` - 10 milliseconds per division
- `100us` or `100μs` - 100 microseconds per division
- `50ns` - 50 nanoseconds per division

## How It Works

### Memory Depth Calculation

The script uses the following formula to determine the required memory depth:

```
Total Time = Time/Div × 10 divisions
Required Memory Depth = Total Time × Sample Rate
```

For example, with a time scale of 10ms/div:
- Total time on screen = 10ms × 10 = 100ms
- At maximum sample rate (1.25 GS/s) = 100ms × 1.25×10⁹ = 125M samples
- The script selects the smallest available memory depth ≥ required (25M max for DHO800)

### Memory Depth Options

The DHO800 series supports the following memory depth settings:
- 10K (10,000 samples)
- 100K (100,000 samples)
- 1M (1,000,000 samples)
- 10M (10,000,000 samples)
- 25M (25,000,000 samples) - maximum for DHO800

### Sample Rate Adjustment

If the required memory depth exceeds the maximum (25M), the script automatically reduces the sample rate to fit within available memory while still capturing the full time window.

## Output Files

### Screenshot Files
- Format: PNG image
- Naming: `scope_screenshot_YYYYMMDD_HHMMSS.png`
- Content: Exact representation of oscilloscope display

### Waveform Files
- Format: CSV (comma-separated values)
- Naming: `waveform_ch1_YYYYMMDD_HHMMSS.csv`
- Columns: Time (s), Voltage (V)
- Content: Raw waveform data with proper scaling applied

## Troubleshooting

### Cannot connect to oscilloscope
- Verify the oscilloscope is powered on and connected
- Check USB cable or network connection
- Make sure VISA drivers are properly installed
- Try running `pyvisa-info` to see available resources

### Memory depth errors
- Some memory depths may not be available depending on oscilloscope settings
- Try different time scales
- Check oscilloscope manual for supported memory depths in your configuration

### Waveform data appears incorrect
- Ensure the oscilloscope has a stable signal before capture
- Check that the channel is properly enabled and configured
- Verify trigger settings on the oscilloscope

## Advanced Usage

### Programmatic Usage

You can use the `RigolDHO804` class in your own scripts:

```python
from rigol_scope_capture import RigolDHO804, parse_time_input

# Connect to oscilloscope
scope = RigolDHO804()

# Set time scale to 5ms/div
time_per_div = parse_time_input('5ms')
scope.set_timescale(time_per_div)

# Calculate and set memory depth
mem_depth, sample_rate = scope.calculate_required_memory_depth(time_per_div)
scope.set_memory_depth(mem_depth)

# Capture data
scope.capture_screenshot('my_screenshot.png')
time_data, voltage_data, filename = scope.capture_waveform(channel=1, filename='my_waveform.csv')

# Close connection
scope.close()
```

## Technical Details

### SCPI Commands Used

- `*IDN?` - Identify device
- `:TIMebase:SCALe <value>` - Set time scale
- `:TIMebase:SCALe?` - Query time scale
- `:ACQuire:MDEPth <value>` - Set memory depth
- `:ACQuire:MDEPth?` - Query memory depth
- `:DISP:DATA?` - Get display screenshot
- `:WAV:SOUR CHAN<n>` - Set waveform source
- `:WAV:MODE NORM` - Set waveform mode
- `:WAV:FORM BYTE` - Set waveform format
- `:WAV:PRE?` - Get waveform preamble (scaling info)
- `:WAV:DATA?` - Get waveform data
- `:STOP` - Stop acquisition
- `:RUN` - Resume acquisition

## References

- [Rigol DHO800/DHO900 Programming Guide](https://download.rigol.com/en/Manual/Digital%20Oscilloscope/DHO900/DHO800900_ProgrammingGuide_EN.pdf)
- [PyVISA Documentation](https://pyvisa.readthedocs.io/)

## License

This project is open source and available for use.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.