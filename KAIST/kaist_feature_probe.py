
import csv
import re
import zipfile
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from nptdms import TdmsFile


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

VIBRATION_ARCHIVE = BASE_DIR / "vibration.zip"
CURRENT_TEMP_ARCHIVE = BASE_DIR / "current,temp.zip"

OUTPUT_DIR = BASE_DIR / "features" / "batch"

WINDOW_SECONDS = 1
EXPECTED_EXPERIMENTS = 45

REQUIRED_TDMS_CHANNELS = (
    "temperature_a",
    "temperature_b",
    "current_u"
)

EXPECTED_TDMS_CHANNELS = {
    "temperature_a": ("Mod1", "ai0"),
    "temperature_b": ("Mod1", "ai1"),
    "current_u": ("Mod2", "ai0"),
    "current_v": ("Mod2", "ai2"),
    "current_w": ("Mod2", "ai3")
}


# ============================================================
# FILENAME MATCHING
# ============================================================

def normalise_filename(stem):

    return stem.lower().replace(
        "unbalalnce",
        "unbalance"
    )


def get_archive_files(archive, extension):

    result = {}

    for member in archive.namelist():

        path = Path(member)

        if path.suffix.lower() != extension:
            continue

        stem = path.stem
        key = normalise_filename(stem)

        if key in result:
            raise ValueError(
                f"Duplicate experiment key: {key}"
            )

        result[key] = {
            "member": member,
            "stem": stem
        }

    return result


def get_experiment_metadata(experiment):

    match = re.match(
        r"^(\d+)Nm_(.+)$",
        experiment,
        re.IGNORECASE
    )

    if not match:
        raise ValueError(
            f"Cannot identify experiment: {experiment}"
        )

    return int(match.group(1)), match.group(2)


# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_numeric_array(values, name, experiment):

    if values.size == 0:
        raise ValueError(
            f"{name} contains no samples: {experiment}"
        )

    if not np.all(np.isfinite(values)):
        raise ValueError(
            f"Non-finite samples found in {name}: {experiment}"
        )


def get_samples_per_window(sampling_interval, name):

    if (
        sampling_interval is None
        or not np.isfinite(sampling_interval)
        or sampling_interval <= 0
    ):
        raise ValueError(
            f"Invalid sampling interval for {name}"
        )

    # Sampling intervals can produce a fractional
    # number of samples per second.
    # Use the nearest whole sample count.
    samples = round(
        WINDOW_SECONDS / sampling_interval
    )

    if samples <= 0:
        raise ValueError(
            f"Invalid samples-per-window for {name}"
        )

    return samples


# ============================================================
# CSV OUTPUT
# ============================================================

def save_csv(filename, headers, rows, folder):

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = folder / filename

    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"    Saved: {output_path.name}")


# ============================================================
# VIBRATION FEATURE EXTRACTION
# ============================================================

def extract_vibration_features(
    archive,
    member,
    experiment
):

    print("\nProcessing vibration:", experiment)

    with archive.open(member) as file:

        mat_data = loadmat(
            file,
            struct_as_record=False,
            squeeze_me=True,
            variable_names=["Signal"]
        )

    if "Signal" not in mat_data:
        raise ValueError(
            f"Signal variable missing: {experiment}"
        )

    data = mat_data["Signal"]

    signal = np.asarray(
        data.y_values.values,
        dtype=np.float64
    )

    if signal.ndim != 2 or signal.shape[1] != 4:
        raise ValueError(
            f"Unexpected vibration shape: {signal.shape}"
        )

    validate_numeric_array(
        signal,
        "Vibration",
        experiment
    )

    sampling_interval = float(
        data.x_values.increment
    )

    samples_per_window = get_samples_per_window(
        sampling_interval,
        "Vibration"
    )

    total_windows = (
        len(signal) // samples_per_window
    )

    if total_windows == 0:
        raise ValueError(
            f"No complete vibration windows: {experiment}"
        )

    load_nm, condition = get_experiment_metadata(
        experiment
    )

    channel_names = [
        "housing_a_x",
        "housing_a_y",
        "housing_b_x",
        "housing_b_y"
    ]

    headers = [
        "experiment",
        "load_nm",
        "condition",
        "window_index",
        "relative_start_s"
    ]

    for channel in channel_names:

        headers.extend([
            f"{channel}_rms",
            f"{channel}_std",
            f"{channel}_peak"
        ])

    rows = []

    start_value = float(
        data.x_values.start_value
    )

    for index in range(total_windows):

        start = index * samples_per_window
        end = start + samples_per_window

        window = signal[start:end, :]

        row = [
            experiment,
            load_nm,
            condition,
            index,
            round(
                start_value + index * WINDOW_SECONDS,
                6
            )
        ]

        for channel_index in range(4):

            values = window[:, channel_index]

            rms = np.sqrt(
                np.mean(np.square(values))
            )

            std = np.std(values)

            peak = np.max(
                np.abs(values)
            )

            row.extend([
                float(rms),
                float(std),
                float(peak)
            ])

        rows.append(row)

    save_csv(
        f"{experiment}_vibration_features.csv",
        headers,
        rows,
        OUTPUT_DIR / "vibration"
    )

    print("    Vibration windows:", total_windows)

    if len(signal) % samples_per_window:

        print(
            "    Trailing incomplete vibration samples:",
            len(signal) % samples_per_window
        )

    del signal
    del data
    del mat_data
    del rows


# ============================================================
# TDMS CHANNEL IDENTIFICATION
# ============================================================

def identify_tdms_channels(group, experiment):

    channel_map = {
        name: None
        for name in EXPECTED_TDMS_CHANNELS
    }

    for channel in group.channels():

        channel_name = str(channel.name)

        for name, (module, channel_id) in (
            EXPECTED_TDMS_CHANNELS.items()
        ):

            expected_suffix = f"{module}/{channel_id}"

            if channel_name.endswith(expected_suffix):

                if channel_map[name] is not None:
                    raise ValueError(
                        f"Duplicate TDMS channel {name}: {experiment}"
                    )

                channel_map[name] = channel

                break

    return channel_map


# ============================================================
# TEMPERATURE AND CURRENT FEATURE EXTRACTION
# ============================================================

def extract_temperature_current_features(
    archive,
    member,
    experiment
):

    print(
        "\nProcessing temperature/current:",
        experiment
    )

    with archive.open(member) as file:

        tdms = TdmsFile.read(file)

    if "Log" not in tdms:

        raise ValueError(
            f"Log group missing: {experiment}"
        )

    group = tdms["Log"]

    matched_channels = identify_tdms_channels(
        group,
        experiment
    )

    channel_map = {}
    increments = {}

    # --------------------------------------------------------
    # Read channels and preserve missing channels.
    # --------------------------------------------------------

    for name, channel in matched_channels.items():

        if channel is None:

            channel_map[name] = np.array(
                [],
                dtype=np.float64
            )

            print(
                f"    WARNING: {name} channel not found."
            )

            continue

        values = np.asarray(
            channel[:],
            dtype=np.float64
        )

        channel_map[name] = values

        if len(values) == 0:

            print(
                f"    WARNING: {name} has zero samples."
            )

            continue

        validate_numeric_array(
            values,
            name,
            experiment
        )

        increment = channel.properties.get(
            "wf_increment"
        )

        if increment is None:

            raise ValueError(
                f"Missing sampling interval for "
                f"{name}: {experiment}"
            )

        increments[name] = float(increment)

    # --------------------------------------------------------
    # Require primary channels.
    # --------------------------------------------------------

    for name in REQUIRED_TDMS_CHANNELS:

        if len(channel_map[name]) == 0:

            raise ValueError(
                f"Required channel {name} is unavailable: "
                f"{experiment}"
            )

    # --------------------------------------------------------
    # Validate sampling intervals.
    # --------------------------------------------------------

    available_increments = list(
        increments.values()
    )

    reference_increment = available_increments[0]

    for name, increment in increments.items():

        if not np.isclose(
            increment,
            reference_increment,
            rtol=0,
            atol=1e-10
        ):

            raise ValueError(
                f"Sampling interval mismatch in "
                f"{experiment}: {name}"
            )

    samples_per_window = get_samples_per_window(
        reference_increment,
        "TDMS"
    )

    # --------------------------------------------------------
    # Determine usable duration.
    # --------------------------------------------------------

    available_channels = [
        name
        for name, values in channel_map.items()
        if len(values) > 0
    ]

    total_windows = min(
        len(channel_map[name]) // samples_per_window
        for name in available_channels
    )

    if total_windows == 0:

        raise ValueError(
            f"No complete TDMS windows: {experiment}"
        )

    load_nm, condition = get_experiment_metadata(
        experiment
    )

    # --------------------------------------------------------
    # Output structure.
    # --------------------------------------------------------

    headers = [
        "experiment",
        "load_nm",
        "condition",
        "window_index",
        "relative_start_s"
    ]

    for name in EXPECTED_TDMS_CHANNELS:

        headers.append(
            f"{name}_available"
        )

    headers.extend([

        "temperature_a_mean",
        "temperature_a_min",
        "temperature_a_max",

        "temperature_b_mean",
        "temperature_b_min",
        "temperature_b_max",

        # Consistent primary current feature.
        "current_u_rms",
        "current_u_mean",

        # Optional diagnostic features.
        "current_v_rms",
        "current_v_mean",

        "current_w_rms",
        "current_w_mean"
    ])

    rows = []

    # --------------------------------------------------------
    # Extract one-second windows.
    # --------------------------------------------------------

    for index in range(total_windows):

        start = index * samples_per_window
        end = start + samples_per_window

        row = [
            experiment,
            load_nm,
            condition,
            index,
            index * WINDOW_SECONDS
        ]

        # Availability flags.
        for name in EXPECTED_TDMS_CHANNELS:

            row.append(
                len(channel_map[name]) > 0
            )

        # Temperature features.
        for name in (
            "temperature_a",
            "temperature_b"
        ):

            values = channel_map[name][start:end]

            if len(values) != samples_per_window:

                raise ValueError(
                    f"Incomplete temperature window: "
                    f"{name}, {experiment}, window {index}"
                )

            row.extend([
                float(np.mean(values)),
                float(np.min(values)),
                float(np.max(values))
            ])

        # Current phase features.
        for name in (
            "current_u",
            "current_v",
            "current_w"
        ):

            values = channel_map[name][start:end]

            if len(values) == samples_per_window:

                rms = np.sqrt(
                    np.mean(np.square(values))
                )

                mean = np.mean(values)

                row.extend([
                    float(rms),
                    float(mean)
                ])

            else:

                # Blank means unavailable, never zero.
                row.extend(["", ""])

        rows.append(row)

    save_csv(
        f"{experiment}_temperature_current_features.csv",
        headers,
        rows,
        OUTPUT_DIR / "temperature_current"
    )

    unavailable_channels = [
        name
        for name in EXPECTED_TDMS_CHANNELS
        if len(channel_map[name]) == 0
    ]

    print(
        "    Available channels:",
        ", ".join(available_channels)
    )

    print(
        "    Unavailable channels:",
        ", ".join(unavailable_channels) or "None"
    )

    print("    Usable windows:", total_windows)

    if "current_u" not in available_channels:

        raise ValueError(
            f"Primary current channel unavailable: {experiment}"
        )

    del channel_map
    del tdms
    del rows


# ============================================================
# MAIN BATCH PROCESSOR
# ============================================================

def main():

    print("=" * 65)
    print("INTELLIWATCH - KAIST BATCH FEATURE EXTRACTION")
    print("=" * 65)

    if not VIBRATION_ARCHIVE.exists():
        raise FileNotFoundError(VIBRATION_ARCHIVE)

    if not CURRENT_TEMP_ARCHIVE.exists():
        raise FileNotFoundError(CURRENT_TEMP_ARCHIVE)

    with zipfile.ZipFile(VIBRATION_ARCHIVE) as vibration_zip:

        with zipfile.ZipFile(CURRENT_TEMP_ARCHIVE) as tdms_zip:

            vibration_files = get_archive_files(
                vibration_zip,
                ".mat"
            )

            tdms_files = get_archive_files(
                tdms_zip,
                ".tdms"
            )

            print(
                "\nVibration recordings:",
                len(vibration_files)
            )

            print(
                "Temperature/current recordings:",
                len(tdms_files)
            )

            vibration_keys = set(vibration_files)
            tdms_keys = set(tdms_files)

            if vibration_keys != tdms_keys:

                raise ValueError(
                    f"Unmatched experiments: "
                    f"{vibration_keys ^ tdms_keys}"
                )

            if len(vibration_keys) != EXPECTED_EXPERIMENTS:

                raise ValueError(
                    f"Expected {EXPECTED_EXPERIMENTS} experiments, "
                    f"found {len(vibration_keys)}"
                )

            print(
                "\nAll experiment pairs matched successfully."
            )

            completed = 0
            missing_v_count = 0
            missing_w_count = 0

            for key in sorted(vibration_keys):

                vibration_member = (
                    vibration_files[key]["member"]
                )

                tdms_member = (
                    tdms_files[key]["member"]
                )

                experiment = tdms_files[key]["stem"]

                print("\n" + "-" * 65)

                print(
                    f"EXPERIMENT {completed + 1}/"
                    f"{EXPECTED_EXPERIMENTS}: {experiment}"
                )

                print("-" * 65)

                extract_vibration_features(
                    vibration_zip,
                    vibration_member,
                    experiment
                )

                extract_temperature_current_features(
                    tdms_zip,
                    tdms_member,
                    experiment
                )

                # Inspect original source channel availability.
                with tdms_zip.open(tdms_member) as source:

                    check_tdms = TdmsFile.read(source)

                check_channels = identify_tdms_channels(
                    check_tdms["Log"],
                    experiment
                )

                if (
                    check_channels["current_v"] is None
                    or len(check_channels["current_v"]) == 0
                ):

                    missing_v_count += 1

                if (
                    check_channels["current_w"] is None
                    or len(check_channels["current_w"]) == 0
                ):

                    missing_w_count += 1

                completed += 1

    print("\n" + "=" * 65)
    print("BATCH FEATURE EXTRACTION COMPLETED")
    print("=" * 65)

    print("Experiments processed:", completed)
    print("Vibration CSV files:", completed)
    print("Temperature/current CSV files:", completed)

    print("Missing Current V recordings:", missing_v_count)
    print("Missing Current W recordings:", missing_w_count)

    print("\nConsistent primary current feature: Current U RMS")

    print("Output directory:", OUTPUT_DIR)

    print(
        "\nNOTE: Current V/W are retained when available. "
        "Missing measurements are never fabricated."
    )

    print(
        "Cross-modal synchronization is not yet verified."
    )


if __name__ == "__main__":
    main()
