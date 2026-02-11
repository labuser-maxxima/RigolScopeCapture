# RigolScopeCapture

Capture screen images and raw waveform data from **Rigol DHO800/DHO900** series digital oscilloscopes (e.g. DHO804).

The tool connects to the scope via USB or LAN, asks for the desired time scale, **automatically sets memory depth** so the captured data spans the full on-screen duration, saves a PNG screenshot, and exports the waveform as a CSV file.

## Features

- **Interactive or CLI** – run with no arguments for guided prompts, or pass everything on the command line.
- **Automatic memory depth** – given a time/div setting and 10 divisions, the program picks the largest memory depth that keeps the sample rate within the scope's limits.
- **Screen capture** – saves the current display as a PNG image.
- **Raw waveform export** – downloads full-depth waveform data for every enabled channel and writes a time-stamped CSV.
- **Auto-discovery** – scans the VISA bus for a Rigol DHO oscilloscope, or accepts an explicit address.

## Requirements

- Python 3.8+
- A Rigol DHO800 or DHO900 series oscilloscope connected via USB or LAN

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

The `requirements.txt` pulls in:

| Package | Purpose |
|---------|---------|
| `pyvisa` | VISA instrument control |
| `pyvisa-py` | Pure-Python VISA backend (no NI-VISA needed) |
| `numpy` | Fast waveform data conversion |

> **Note:** For USB connections you may also need `pyusb` (`pip install pyusb`) and appropriate USB drivers/permissions.

## Quick Start

```bash
# Interactive – auto-detect the scope and prompt for time scale
python scope_capture.py

# Set 100 ms/div, connect over LAN
python scope_capture.py --timescale 100ms --visa-address "TCPIP::192.168.1.100::INSTR"

# Capture channels 1 & 2, save into ./captures
python scope_capture.py --timescale 5us --channels 1 2 --output-dir ./captures

# Only grab the screen image (skip CSV)
python scope_capture.py --timescale 1s --no-csv
```

## How It Works

1. **Set time scale** – the program writes `:TIMebase:MAIN:SCALe` to set the requested time/div (snapped to the nearest valid 1-2-5 value).
2. **Choose memory depth** – total on-screen time = time/div × 10 divisions. The largest available memory depth whose effective sample rate (depth ÷ total time) does not exceed 1.25 GSa/s is selected and sent via `:ACQuire:MDEPth`.
3. **Screen capture** – `:DISPlay:DATA?` returns a PNG of the current display.
4. **Waveform download** – the scope is stopped, then for each enabled channel the program reads RAW waveform data in 250 k-point chunks (`:WAVeform:DATA?`), converts bytes to voltage using the preamble (`:WAVeform:PREamble?`), and reassembles the full record.
5. **CSV export** – time and voltage columns are written to a CSV file; one column per channel.

## Command-Line Options

| Flag | Description |
|------|-------------|
| `--visa-address` | VISA resource string for the scope |
| `--timescale` | Time per division, e.g. `100ms`, `1s`, `5us` |
| `--channels` | Space-separated channel numbers (default: all enabled) |
| `--output-dir` | Directory for output files (default: `.`) |
| `--no-image` | Skip the PNG screen capture |
| `--no-csv` | Skip the CSV waveform export |

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Reference

- [Rigol DHO800/DHO900 Programming Guide (PDF)](https://www.batterfly.com/PDF/RIGOL/dho800/DHO800-Series_programmingguide_EN.pdf)