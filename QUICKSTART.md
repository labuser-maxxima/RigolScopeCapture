# Quick Start Guide for Rigol DHO804 Scope Capture

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install VISA drivers (if not already installed):
   - **Windows/Mac**: [NI-VISA](https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html)
   - **Linux**: Already handled by pyvisa-py

## Basic Usage

Run the main script:
```bash
python rigol_scope_capture.py
```

Follow the prompts:
1. Script connects to oscilloscope automatically
2. Shows current time scale setting
3. Enter desired time scale (e.g., `10ms`, `5us`, `1s`) or press Enter to keep current
4. Script automatically calculates and sets memory depth
5. Captures screenshot and waveform data
6. Saves files with timestamps

## Output Files

- `scope_screenshot_YYYYMMDD_HHMMSS.png` - Screenshot image
- `waveform_ch1_YYYYMMDD_HHMMSS.csv` - Waveform data (Time, Voltage)

## Time Scale Examples

| Input  | Meaning                    | Total Screen Time |
|--------|----------------------------|-------------------|
| `1s`   | 1 second per division      | 10 seconds        |
| `100ms`| 100 milliseconds per div   | 1 second          |
| `10ms` | 10 milliseconds per div    | 100 milliseconds  |
| `1ms`  | 1 millisecond per div      | 10 milliseconds   |
| `100us`| 100 microseconds per div   | 1 millisecond     |
| `10us` | 10 microseconds per div    | 100 microseconds  |
| `1us`  | 1 microsecond per div      | 10 microseconds   |
| `100ns`| 100 nanoseconds per div    | 1 microsecond     |

## How Memory Depth is Calculated

The script uses this formula:
```
Total Time = Time per Division × 10 divisions
Required Memory = Total Time × Sample Rate
```

Example for 10ms/div:
- Total time: 10ms × 10 = 100ms
- At max sample rate (1.25 GS/s): 100ms × 1.25×10⁹ = 125M samples
- Since DHO800 max is 25M, sample rate is reduced to 250 MS/s

## Programmatic Usage

See `examples.py` for detailed examples:
```bash
python examples.py
```

Or import the class in your own code:
```python
from rigol_scope_capture import RigolDHO804, parse_time_input

scope = RigolDHO804()
scope.set_timescale(parse_time_input('5ms'))
scope.capture_screenshot('my_capture.png')
scope.capture_waveform(channel=1, filename='my_waveform.csv')
scope.close()
```

## Testing

Run the unit tests:
```bash
python test_rigol_scope.py
```

## Troubleshooting

**Cannot find oscilloscope:**
- Check USB/network connection
- Verify oscilloscope is powered on
- Run `python -m pyvisa info` to see available resources

**Import errors:**
- Run `pip install -r requirements.txt`
- Check Python version (requires 3.7+)

**Memory depth errors:**
- Try a different time scale
- Check oscilloscope is not in AUTO mode
- Refer to oscilloscope manual for supported memory depths

## SCPI Commands Reference

The script uses these SCPI commands (from DHO800/DHO900 Programming Guide):

| Command                 | Purpose                    |
|-------------------------|----------------------------|
| `*IDN?`                 | Identify device            |
| `:TIMebase:SCALe <val>` | Set time scale             |
| `:TIMebase:SCALe?`      | Query time scale           |
| `:ACQuire:MDEPth <val>` | Set memory depth           |
| `:ACQuire:MDEPth?`      | Query memory depth         |
| `:DISP:DATA?`           | Get screenshot             |
| `:WAV:SOUR CHAN<n>`     | Select waveform channel    |
| `:WAV:PRE?`             | Get waveform scaling info  |
| `:WAV:DATA?`            | Get waveform data          |
| `:STOP`                 | Stop acquisition           |
| `:RUN`                  | Resume acquisition         |

## Support

For issues or questions, refer to:
- README.md for detailed documentation
- examples.py for usage examples
- [Rigol DHO800/DHO900 Programming Guide](https://download.rigol.com/en/Manual/Digital%20Oscilloscope/DHO900/DHO800900_ProgrammingGuide_EN.pdf)
