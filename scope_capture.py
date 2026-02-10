#!/usr/bin/env python3
"""
RigolScopeCapture - Capture screen images and waveform data from
Rigol DHO800/DHO900 series oscilloscopes.

Connects to a Rigol DHO804 (or compatible DHO800/DHO900 series) oscilloscope
via VISA (USB or LAN), sets the desired time scale, automatically adjusts
memory depth, captures the screen image (PNG), and downloads raw waveform
data to CSV.

Reference: Rigol DHO800/DHO900 Programming Guide
  https://www.batterfly.com/PDF/RIGOL/dho800/DHO800-Series_programmingguide_EN.pdf
"""

import argparse
import csv
import datetime
import os
import sys
import time

try:
    import pyvisa
except ImportError:
    print("Error: pyvisa is required. Install with: pip install pyvisa pyvisa-py")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    np = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Number of horizontal divisions on DHO800/DHO900 series
NUM_DIVISIONS = 10

# Maximum sample rate for DHO804 (1.25 GSa/s single channel)
MAX_SAMPLE_RATE = 1.25e9

# Available memory depth presets (points) for DHO800 series
MEMORY_DEPTHS = [1000, 10000, 100000, 1000000, 10000000]

# Valid time/div values in seconds (1-2-5 sequence)
VALID_TIMESCALES = [
    1e-9, 2e-9, 5e-9,
    10e-9, 20e-9, 50e-9,
    100e-9, 200e-9, 500e-9,
    1e-6, 2e-6, 5e-6,
    10e-6, 20e-6, 50e-6,
    100e-6, 200e-6, 500e-6,
    1e-3, 2e-3, 5e-3,
    10e-3, 20e-3, 50e-3,
    100e-3, 200e-3, 500e-3,
    1.0, 2.0, 5.0, 10.0,
]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def parse_timescale(value_str):
    """Parse a human-readable time string into seconds.

    Accepted formats: ``100ms``, ``1s``, ``5us``, ``200ns``, or a plain
    number (interpreted as seconds).
    """
    value_str = value_str.strip().lower()

    suffixes = {
        "ns": 1e-9,
        "us": 1e-6,
        "ms": 1e-3,
        "s": 1.0,
    }

    for suffix, multiplier in sorted(suffixes.items(), key=lambda x: -len(x[0])):
        if value_str.endswith(suffix):
            try:
                number = float(value_str[: -len(suffix)])
                return number * multiplier
            except ValueError:
                raise ValueError(f"Invalid time scale value: {value_str}")

    # Plain number – assume seconds
    try:
        return float(value_str)
    except ValueError:
        raise ValueError(
            f"Invalid time scale: '{value_str}'. "
            "Use format like '100ms', '1s', '5us', '200ns'"
        )


def format_timescale(seconds):
    """Return a compact human-readable representation of *seconds*."""
    if seconds >= 1.0:
        val = seconds
        unit = "s"
    elif seconds >= 1e-3:
        val = seconds * 1e3
        unit = "ms"
    elif seconds >= 1e-6:
        val = seconds * 1e6
        unit = "us"
    else:
        val = seconds * 1e9
        unit = "ns"

    if val == int(val):
        return f"{int(val)}{unit}"
    return f"{val:g}{unit}"


def find_nearest_timescale(seconds):
    """Snap *seconds* to the closest valid 1-2-5 scope timescale."""
    return min(VALID_TIMESCALES, key=lambda x: abs(x - seconds))


def choose_memory_depth(total_time_s):
    """Pick the largest memory depth whose sample rate stays within limits.

    ``sample_rate = depth / total_time`` must not exceed
    :data:`MAX_SAMPLE_RATE`.
    """
    best = MEMORY_DEPTHS[0]
    for depth in MEMORY_DEPTHS:
        if depth / total_time_s <= MAX_SAMPLE_RATE:
            best = depth
    return best


def parse_preamble(preamble_str):
    """Parse the ``:WAVeform:PREamble?`` response into a dictionary."""
    parts = preamble_str.strip().split(",")
    if len(parts) < 10:
        raise ValueError(
            f"Malformed preamble: expected 10 fields, got {len(parts)}"
        )
    return {
        "format": int(parts[0]),         # 0=BYTE, 1=WORD, 2=ASCii
        "type": int(parts[1]),           # 0=NORMal, 1=MAXimum, 2=RAW
        "points": int(parts[2]),         # Number of data points
        "count": int(parts[3]),          # Always 1
        "xincrement": float(parts[4]),   # Time between adjacent points (s)
        "xorigin": float(parts[5]),      # Start time of first point (s)
        "xreference": float(parts[6]),   # Reference time (index)
        "yincrement": float(parts[7]),   # Voltage value per LSB (V)
        "yorigin": float(parts[8]),      # Voltage offset (V)
        "yreference": float(parts[9]),   # Reference voltage (counts)
    }


def strip_tmc_header(raw):
    """Remove the IEEE 488.2 definite-length block header from *raw* bytes.

    The header has the form ``#NXXXXXXX`` where *N* is the number of
    digits that follow and *XXXXXXX* is the byte-count.
    """
    if len(raw) < 2 or raw[0:1] != b"#":
        return raw
    n_digits = int(raw[1:2])
    if len(raw) < 2 + n_digits:
        return raw
    data_len = int(raw[2 : 2 + n_digits])
    return raw[2 + n_digits : 2 + n_digits + data_len]


# ---------------------------------------------------------------------------
# Scope interaction
# ---------------------------------------------------------------------------


def find_scope(resource_manager, visa_address=None):
    """Open a VISA connection to a Rigol DHO oscilloscope.

    If *visa_address* is given it is used directly.  Otherwise the bus is
    scanned and the first Rigol DHO instrument found is returned.
    """
    if visa_address:
        print(f"Connecting to: {visa_address}")
        scope = resource_manager.open_resource(visa_address)
        scope.timeout = 30000
        scope.chunk_size = 1024 * 1024
        idn = scope.query("*IDN?").strip()
        print(f"Connected: {idn}")
        return scope

    # Auto-discover
    print("Scanning for VISA instruments...")
    resources = resource_manager.list_resources()

    if not resources:
        print("No VISA instruments found.")
        print("Ensure the oscilloscope is connected via USB or LAN,")
        print("or specify the address with --visa-address.")
        return None

    print(f"Found {len(resources)} instrument(s):")
    for i, res in enumerate(resources):
        print(f"  [{i}] {res}")

    for res in resources:
        try:
            scope = resource_manager.open_resource(res)
            scope.timeout = 30000
            scope.chunk_size = 1024 * 1024
            idn = scope.query("*IDN?").strip()
            if "RIGOL" in idn.upper() and "DHO" in idn.upper():
                print(f"Found Rigol DHO scope: {idn}")
                return scope
            scope.close()
        except Exception:
            continue

    # Fall back to the single available resource
    if len(resources) == 1:
        scope = resource_manager.open_resource(resources[0])
        scope.timeout = 30000
        scope.chunk_size = 1024 * 1024
        idn = scope.query("*IDN?").strip()
        print(f"Using: {idn}")
        return scope

    print("\nNo Rigol DHO oscilloscope auto-detected.")
    print("Specify the address with --visa-address.")
    return None


def get_enabled_channels(scope):
    """Return a list of enabled channel numbers (1-4)."""
    enabled = []
    for ch in range(1, 5):
        try:
            state = scope.query(f":CHANnel{ch}:DISPlay?").strip()
            if state in ("1", "ON"):
                enabled.append(ch)
        except Exception:
            pass
    return enabled


def set_timescale(scope, time_per_div):
    """Set the time-base scale and return the actual value read back."""
    scope.write(f":TIMebase:MAIN:SCALe {time_per_div:.10e}")
    time.sleep(0.5)
    return float(scope.query(":TIMebase:MAIN:SCALe?").strip())


def set_memory_depth(scope, depth):
    """Set the acquisition memory depth and return the read-back value."""
    scope.write(f":ACQuire:MDEPth {depth}")
    time.sleep(0.5)
    return scope.query(":ACQuire:MDEPth?").strip()


def capture_screen(scope, filename):
    """Save the current display as a PNG image to *filename*."""
    print("Capturing screen image...")
    scope.write(":DISPlay:DATA?")
    raw = scope.read_raw()
    image_data = strip_tmc_header(raw)

    with open(filename, "wb") as f:
        f.write(image_data)

    print(f"Screen capture saved: {filename} ({len(image_data)} bytes)")


def read_waveform_data(scope, channel, mode="RAW"):
    """Download waveform data from *channel*.

    Returns ``(times, voltages, preamble_dict)``.
    """
    print(f"  Reading Channel {channel} waveform ({mode} mode)...")

    scope.write(f":WAVeform:SOURce CHANnel{channel}")
    scope.write(f":WAVeform:MODE {mode}")
    scope.write(":WAVeform:FORMat BYTE")

    preamble = parse_preamble(scope.query(":WAVeform:PREamble?"))
    num_points = preamble["points"]
    print(f"    Points to read: {num_points:,}")

    # Read in chunks – DHO800 series supports up to 250 000 points per read
    max_chunk = 250000
    all_data = bytearray()

    for start in range(1, num_points + 1, max_chunk):
        stop = min(start + max_chunk - 1, num_points)
        scope.write(f":WAVeform:STARt {start}")
        scope.write(f":WAVeform:STOP {stop}")
        scope.write(":WAVeform:DATA?")
        chunk = strip_tmc_header(scope.read_raw())
        all_data.extend(chunk)

        if num_points > max_chunk:
            pct = min(stop, num_points) / num_points * 100
            print(f"    Progress: {pct:.0f}% ({stop:,}/{num_points:,})")

    # Convert to physical units
    xi = preamble["xincrement"]
    xo = preamble["xorigin"]
    yi = preamble["yincrement"]
    yo = preamble["yorigin"]
    yr = preamble["yreference"]

    if np is not None:
        raw = np.frombuffer(bytes(all_data), dtype=np.uint8).astype(float)
        voltages = (raw - yo - yr) * yi
        times = np.arange(len(voltages)) * xi + xo
    else:
        voltages = [(b - yo - yr) * yi for b in all_data]
        times = [i * xi + xo for i in range(len(voltages))]

    span = times[-1] - times[0] if len(times) > 1 else 0
    print(f"    Captured {len(voltages):,} points, span: {format_timescale(span)}")

    return times, voltages, preamble


def save_csv(filename, channel_data):
    """Write captured waveform data to a CSV file.

    *channel_data* maps channel numbers to ``(times, voltages, preamble)``
    tuples.
    """
    print(f"Saving waveform data to: {filename}")
    first_ch = sorted(channel_data.keys())[0]
    times = channel_data[first_ch][0]

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["Time (s)"] + [
            f"Channel {ch} (V)" for ch in sorted(channel_data.keys())
        ]
        writer.writerow(header)

        for i in range(len(times)):
            if np is not None:
                row = [times[i]]
            else:
                row = [f"{times[i]:.12e}"]
            for ch in sorted(channel_data.keys()):
                v = channel_data[ch][1][i]
                row.append(v if np is not None else f"{v:.6e}")
            writer.writerow(row)

    print(f"CSV saved: {filename} ({len(times):,} data points)")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Capture screen images and waveform data from "
            "Rigol DHO800/DHO900 oscilloscopes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          Interactive mode, auto-detect scope
  %(prog)s --timescale 100ms        Set 100 ms/div time scale
  %(prog)s --timescale 1s --visa-address "TCPIP::192.168.1.100::INSTR"
  %(prog)s --timescale 5us --channels 1 2
  %(prog)s --timescale 200ms --output-dir ./captures
""",
    )
    parser.add_argument(
        "--visa-address",
        help=(
            "VISA resource string "
            '(e.g. "USB0::0x1AB1::0x044C::DHO8A...::INSTR" '
            'or "TCPIP::192.168.1.100::INSTR")'
        ),
    )
    parser.add_argument(
        "--timescale",
        help='Time per division (e.g. "100ms", "1s", "5us", "200ns")',
    )
    parser.add_argument(
        "--channels",
        type=int,
        nargs="+",
        help="Channel numbers to capture (default: all enabled channels)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output files (default: current directory)",
    )
    parser.add_argument(
        "--no-image",
        action="store_true",
        help="Skip screen image capture",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip CSV waveform data export",
    )
    args = parser.parse_args()

    # --- Time scale ---
    if args.timescale:
        time_per_div = parse_timescale(args.timescale)
    else:
        print("\nAvailable time scales (1-2-5 sequence):")
        print("  ns: 1, 2, 5, 10, 20, 50, 100, 200, 500")
        print("  us: 1, 2, 5, 10, 20, 50, 100, 200, 500")
        print("  ms: 1, 2, 5, 10, 20, 50, 100, 200, 500")
        print("   s: 1, 2, 5, 10")
        print()
        ts_input = input(
            "Enter desired time scale per division (e.g. 100ms, 1s, 5us): "
        ).strip()
        if not ts_input:
            print("No time scale entered. Exiting.")
            sys.exit(1)
        time_per_div = parse_timescale(ts_input)

    time_per_div = find_nearest_timescale(time_per_div)
    total_time = time_per_div * NUM_DIVISIONS

    print(f"\nTime scale:        {format_timescale(time_per_div)}/div")
    print(f"Total screen time: {format_timescale(total_time)} ({NUM_DIVISIONS} divisions)")

    mem_depth = choose_memory_depth(total_time)
    sample_rate = mem_depth / total_time
    print(f"Memory depth:      {mem_depth:,} points")
    print(f"Sample rate:       {sample_rate:,.0f} Sa/s")

    # --- Output directory ---
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- Connect ---
    rm = pyvisa.ResourceManager()
    scope = find_scope(rm, args.visa_address)
    if scope is None:
        sys.exit(1)

    try:
        print("\n--- Configuring Oscilloscope ---")
        actual_ts = set_timescale(scope, time_per_div)
        print(f"Time scale set to: {format_timescale(actual_ts)}/div")

        actual_md = set_memory_depth(scope, mem_depth)
        print(f"Memory depth set to: {actual_md}")

        time.sleep(1)  # let acquisition settle

        # --- Channels ---
        if args.channels:
            channels = args.channels
        else:
            channels = get_enabled_channels(scope)
            if not channels:
                print("No channels enabled – enabling Channel 1.")
                scope.write(":CHANnel1:DISPlay ON")
                channels = [1]

        print(f"Channels: {', '.join(f'CH{c}' for c in channels)}")

        # --- Screen capture ---
        if not args.no_image:
            img_path = os.path.join(
                args.output_dir, f"scope_capture_{timestamp}.png"
            )
            capture_screen(scope, img_path)

        # --- Waveform data ---
        if not args.no_csv:
            print("\n--- Capturing Waveform Data ---")
            scope.write(":STOP")
            time.sleep(0.5)

            channel_data = {}
            for ch in channels:
                t, v, p = read_waveform_data(scope, ch, mode="RAW")
                channel_data[ch] = (t, v, p)

            scope.write(":RUN")

            csv_path = os.path.join(
                args.output_dir, f"waveform_{timestamp}.csv"
            )
            save_csv(csv_path, channel_data)

        print("\n--- Capture Complete ---")
    finally:
        scope.close()
        rm.close()

    print("Done!")


if __name__ == "__main__":
    main()
