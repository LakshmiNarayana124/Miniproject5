
"""
IntelliWatch - Sensor Reader

Responsibilities:
1. Acquire vibration readings.
2. Acquire temperature readings.
3. Acquire electrical current readings.
4. Support simulation mode.
5. Return readings in a consistent format.

Business logic and anomaly detection belong in intelliwatch_brain.py.
"""

import random
import math
import time
from datetime import datetime, timezone

from sensor_config import (
    SENSOR_CONFIG,
    get_sensor_config
)


# ============================================================
# 1. READER CONFIGURATION
# ============================================================

SIMULATION_MODE = True

SIMULATION_SETTINGS = {

    "vibration": {
        "base_value": 0.15,
        "variation": 0.04
    },

    "temperature": {
        "base_value": 32.0,
        "variation": 1.5
    },

    "current": {
        "base_value": 2.0,
        "variation": 0.25
    }

}


# ============================================================
# 2. COMMON DATA FORMAT
# ============================================================

def create_reading(sensor_type, value, unit, metadata=None):
    """
    Creates a standard reading structure.

    All sensors return data in the same format.
    """

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "sensor_type": sensor_type,

        "sensor_name": SENSOR_CONFIG[sensor_type]["sensor_name"],

        "parameter": SENSOR_CONFIG[sensor_type]["parameter"],

        "value": value,

        "unit": unit,

        "quality": "GOOD",

        "metadata": metadata or {}
    }


# ============================================================
# 3. VIBRATION SENSOR - ADXL345
# ============================================================

def read_vibration():

    if SIMULATION_MODE:

        settings = SIMULATION_SETTINGS["vibration"]

        base = settings["base_value"]

        variation = settings["variation"]

        x = base + random.uniform(-variation, variation)

        y = base + random.uniform(-variation, variation)

        z = random.uniform(-variation, variation)

        magnitude = math.sqrt(
            x ** 2 + y ** 2 + z ** 2
        )

        return create_reading(
            sensor_type="vibration",

            value=round(magnitude, 4),

            unit="g",

            metadata={
                "x": round(x, 4),
                "y": round(y, 4),
                "z": round(z, 4),
                "measurement_type": "simulated_acceleration"
            }
        )

    raise NotImplementedError(
        "ADXL345 hardware reading is not configured yet."
    )


# ============================================================
# 4. TEMPERATURE SENSOR - DS18B20
# ============================================================

def read_temperature():

    if SIMULATION_MODE:

        settings = SIMULATION_SETTINGS["temperature"]

        temperature = (
            settings["base_value"]
            + random.uniform(
                -settings["variation"],
                settings["variation"]
            )
        )

        return create_reading(
            sensor_type="temperature",

            value=round(temperature, 2),

            unit="°C",

            metadata={
                "measurement_type": "simulated_temperature"
            }
        )

    raise NotImplementedError(
        "DS18B20 hardware reading is not configured yet."
    )


# ============================================================
# 5. CURRENT SENSOR - ACS712 + ADS1115
# ============================================================

def read_current():

    if SIMULATION_MODE:

        settings = SIMULATION_SETTINGS["current"]

        current = (
            settings["base_value"]
            + random.uniform(
                -settings["variation"],
                settings["variation"]
            )
        )

        return create_reading(
            sensor_type="current",

            value=round(abs(current), 3),

            unit="A",

            metadata={
                "measurement_type": "simulated_current"
            }
        )

    raise NotImplementedError(
        "ACS712 and ADS1115 hardware reading is not configured yet."
    )


# ============================================================
# 6. READ ALL SENSORS
# ============================================================

def read_all_sensors():
    """
    Collects readings from all three sensors.

    Each sensor is read independently.
    The results are returned together.
    """

    readings = {}

    sensor_readers = {
        "vibration": read_vibration,
        "temperature": read_temperature,
        "current": read_current
    }

    for sensor_type, reader in sensor_readers.items():

        try:

            readings[sensor_type] = reader()

        except Exception as error:

            readings[sensor_type] = {
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),

                "sensor_type": sensor_type,

                "sensor_name": SENSOR_CONFIG[
                    sensor_type
                ]["sensor_name"],

                "parameter": SENSOR_CONFIG[
                    sensor_type
                ]["parameter"],

                "value": None,

                "unit": SENSOR_CONFIG[
                    sensor_type
                ]["unit"],

                "quality": "ERROR",

                "error": str(error),

                "metadata": {}
            }

    return readings


# ============================================================
# 7. CONTINUOUS SENSOR READING
# ============================================================

def start_sensor_reading(interval=1, total_cycles=None):
    """
    Continuously reads all sensors.

    interval:
        Delay between complete sensor-reading cycles.

    total_cycles:
        Number of cycles to execute.
        None means continuous operation.
    """

    cycle = 0

    print("\nIntelliWatch Sensor Reader Started")

    print(
        "Mode:",
        "SIMULATION" if SIMULATION_MODE else "HARDWARE"
    )

    try:

        while total_cycles is None or cycle < total_cycles:

            readings = read_all_sensors()

            print("\n--------------------------------")

            print("Reading Cycle:", cycle + 1)

            for sensor_type, data in readings.items():

                print(
                    f"{data['parameter']}: "
                    f"{data['value']} {data['unit']} "
                    f"| {data['quality']}"
                )

            cycle += 1

            time.sleep(interval)

    except KeyboardInterrupt:

        print("\nSensor reading stopped by user.")


# ============================================================
# 8. TEST SENSOR READER
# ============================================================

if __name__ == "__main__":

    print("\n===================================")

    print("       INTELLIWATCH SENSOR TEST")

    print("===================================")

    # Read all sensors for five cycles.
    start_sensor_reading(
        interval=1,
        total_cycles=5
    )
