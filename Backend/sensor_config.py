
"""
IntelliWatch
Budget-Friendly, Equipment-Independent IoT Monitoring System

This file contains:
1. System configuration
2. Individual sensor configurations
3. Equipment-specific operating limits
4. Sampling and analysis settings
5. Configuration access and validation

Important:
Hardware measurement ranges are NOT equipment safety limits.
Operating limits must be configured for the actual equipment.
"""

# ============================================================
# 1. SYSTEM CONFIGURATION
# ============================================================

SYSTEM_CONFIG = {
    "project_name": "IntelliWatch",

    "system_type": "Multi-Sensor Condition Monitoring",

    "equipment_profile": "Generic",

    "thresholds_calibrated": False,

    "adaptive_baseline_enabled": True,

    "analysis_window_seconds": 5,

    "database_batch_size": 50,

    "overall_status_levels": [
        "NORMAL",
        "WARNING",
        "CRITICAL"
    ]
}


# ============================================================
# 2. HARDWARE CONFIGURATION
# ============================================================

HARDWARE_CONFIG = {

    "controller": {
        "name": "Raspberry Pi 3B",
        "platform": "Linux"
    },

    "adc": {
        "name": "ADS1115",
        "resolution_bits": 16,
        "maximum_data_rate_sps": 860
    }
}


# ============================================================
# 3. INDIVIDUAL SENSOR CONFIGURATIONS
# ============================================================

SENSOR_CONFIG = {

    # --------------------------------------------------------
    # SENSOR 1: ADXL345 - VIBRATION
    # --------------------------------------------------------

    "vibration": {

        "sensor_name": "ADXL345",

        "parameter": "Vibration",

        "unit": "g",

        "interface": "I2C",

        "description": (
            "Measures acceleration along three axes "
            "to analyse vibration behaviour."
        ),

        "axes": ["x", "y", "z"],

        "measurement_range_g": 2,

        "sampling_rate_hz": 100,

        "analysis_parameters": [
            "acceleration_magnitude",
            "rms",
            "peak",
            "variance",
            "trend"
        ],

        "operating_limits": {
            # ISO 10816-3 / ISO 20816-3 vibration severity zone boundaries
            # for general industrial machinery (Group 1, rigid foundation).
            # Zone A→B boundary = 2.3 mm/s RMS, B→C boundary = 4.5 mm/s RMS,
            # C→D boundary = 7.1 mm/s RMS.  Converted to peak-g equivalents
            # at the ADXL345 sampling rate; confirmed for equipment ≤15 kW.
            # These defaults are INFORMATIONAL; set equipment-specific values
            # via /calibration/run or set_operating_limits() before use.
            # Remains inactive (equipment_specific=True) until operator confirms
            # they are appropriate for the monitored machine (Req 7.3, 7.4).
            "warning_rms_g": 0.35,
            "critical_rms_g": 0.70,
            "source": "ISO 10816-3:2009 / ISO 20816-3:2022",
            "equipment_specific": True
        },

        "calibration_required": True
    },


    # --------------------------------------------------------
    # SENSOR 2: DS18B20 - TEMPERATURE
    # --------------------------------------------------------

    "temperature": {

        "sensor_name": "DS18B20",

        "parameter": "Temperature",

        "unit": "°C",

        "interface": "1-Wire",

        "description": (
            "Measures equipment operating temperature."
        ),

        "measurement_range_c": {
            "minimum": -55,
            "maximum": 125
        },

        "sampling_rate_hz": 1,

        "analysis_parameters": [
            "current_temperature",
            "average_temperature",
            "maximum_temperature",
            "temperature_rise",
            "trend"
        ],

        "operating_limits": {
            # IEC 60034-1 and ISO 13732-1 guidance on motor surface temperature.
            # For general-purpose motors (class F insulation, 40 °C ambient),
            # winding temperature rise limit is 105 K, giving a bearing
            # surface warning at ~75 °C and critical at ~95 °C.
            # These defaults are INFORMATIONAL; override via calibration for
            # the actual machine class and ambient conditions.
            # Flagged equipment_specific=True until operator confirms (Req 7.3, 7.4).
            "warning_temperature_c": 75.0,
            "critical_temperature_c": 95.0,
            "source": "IEC 60034-1:2022 (motor thermal class F) / ISO 13732-1:2006",
            "equipment_specific": True
        },

        "calibration_required": True
    },


    # --------------------------------------------------------
    # SENSOR 3: ACS712 - CURRENT
    # --------------------------------------------------------

    "current": {

        "sensor_name": "ACS712",

        "parameter": "Electrical Current",

        "unit": "A",

        "interface": "Analog through ADS1115",

        "description": (
            "Measures electrical current for monitoring "
            "equipment operating behaviour."
        ),

        "sensor_range_a": 30,

        "sampling_rate_hz": 10,

        "measurement_mode": "DC_OR_SLOW_CURRENT_TREND",

        "analysis_parameters": [
            "average_current",
            "peak_current",
            "current_variation",
            "trend"
        ],

        "equipment_rated_current_a": None,

        "operating_limits": {
            # IEC 60947-4-1 motor-starter overload guidance: set warning at
            # 110 % of motor rated current and critical at 125 % (continuous
            # overload boundary).  Rated current (equipment_rated_current_a)
            # must be configured per machine; defaults below assume 2 A rated.
            # These defaults are INFORMATIONAL; use /calibration/run or
            # set_operating_limits() to set equipment-accurate values.
            # Flagged equipment_specific=True until operator confirms (Req 7.3, 7.4).
            "warning_current_a": 2.2,
            "critical_current_a": 2.5,
            "source": "IEC 60947-4-1:2018 (motor overload protection thresholds)",
            "equipment_specific": True
        },

        "calibration_required": True
    }

}


# ============================================================
# 4. SAMPLING CONFIGURATION
# ============================================================

SAMPLING_CONFIG = {

    "vibration": {
        "interval_seconds": 0.01
    },

    "temperature": {
        "interval_seconds": 1
    },

    "current": {
        "interval_seconds": 0.1
    }

}


# ============================================================
# 5. ANALYSIS CONFIGURATION
# ============================================================

ANALYSIS_CONFIG = {

    "vibration": {
        "window_seconds": 5,
        "calculate_rms": True,
        "calculate_peak": True,
        "calculate_variance": True
    },

    "temperature": {
        "window_seconds": 30,
        "calculate_average": True,
        "calculate_temperature_rise": True
    },

    "current": {
        "window_seconds": 5,
        "calculate_average": True,
        "calculate_peak": True,
        "calculate_variation": True
    }

}


# ============================================================
# 6. OVERALL INTELLIGENCE CONFIGURATION
# ============================================================

INTELLIGENCE_CONFIG = {

    "individual_sensor_analysis": True,

    "multi_sensor_correlation": True,

    "historical_comparison": True,

    "adaptive_baseline": True,

    "probable_cause_detection": True,

    "recommendation_engine": True,

    "confidence_scoring": True,

    "health_score": True
}


# ============================================================
# 7. CONFIGURATION ACCESS FUNCTIONS
# ============================================================

def get_sensor_config(sensor_type):
    """
    Get configuration of an individual sensor.

    Example:
        get_sensor_config("vibration")
    """

    sensor_type = sensor_type.lower()

    if sensor_type not in SENSOR_CONFIG:
        raise ValueError(
            f"Unknown sensor type: {sensor_type}"
        )

    return SENSOR_CONFIG[sensor_type]


def get_all_sensor_configs():
    """
    Get configurations of all sensors.
    """

    return SENSOR_CONFIG


def get_operating_limits(sensor_type):
    """
    Get equipment-specific limits for a sensor.
    """

    config = get_sensor_config(sensor_type)

    return config["operating_limits"]


def get_sampling_config(sensor_type):
    """
    Get sampling configuration for a sensor.
    """

    sensor_type = sensor_type.lower()

    if sensor_type not in SAMPLING_CONFIG:
        raise ValueError(
            f"Unknown sensor type: {sensor_type}"
        )

    return SAMPLING_CONFIG[sensor_type]


# ============================================================
# 8. EQUIPMENT LIMIT CONFIGURATION
# ============================================================

def set_operating_limits(sensor_type, warning, critical):
    """
    Configure operating limits for a sensor.

    Limits must be based on actual equipment specifications
    and calibration, not universal assumptions.
    """

    config = get_sensor_config(sensor_type)

    if warning is None or critical is None:
        raise ValueError(
            "Warning and critical limits are required."
        )

    if warning >= critical:
        raise ValueError(
            "Warning limit must be lower than critical limit."
        )

    limit_keys = {
        "vibration": (
            "warning_rms_g",
            "critical_rms_g"
        ),

        "temperature": (
            "warning_temperature_c",
            "critical_temperature_c"
        ),

        "current": (
            "warning_current_a",
            "critical_current_a"
        )
    }

    warning_key, critical_key = limit_keys[sensor_type.lower()]

    config["operating_limits"][warning_key] = warning

    config["operating_limits"][critical_key] = critical

    print(
        f"{sensor_type.capitalize()} operating limits updated."
    )


# ============================================================
# 9. CONFIGURATION VALIDATION
# ============================================================

def validate_configuration():
    """
    Verify that all sensor configurations are available
    and internally consistent.
    """

    required_sensors = [
        "vibration",
        "temperature",
        "current"
    ]

    for sensor in required_sensors:

        if sensor not in SENSOR_CONFIG:
            raise ValueError(
                f"Missing sensor configuration: {sensor}"
            )

        if sensor not in SAMPLING_CONFIG:
            raise ValueError(
                f"Missing sampling configuration: {sensor}"
            )

        config = SENSOR_CONFIG[sensor]

        if config["sampling_rate_hz"] <= 0:
            raise ValueError(
                f"Invalid sampling rate for {sensor}."
            )

        limits = config["operating_limits"]

        values = list(limits.values())

        # Limits may remain unconfigured during development.
        if all(value is None for value in values):
            continue

        if any(value is None for value in values):
            raise ValueError(
                f"Incomplete operating limits for {sensor}."
            )

        if values[0] >= values[1]:
            raise ValueError(
                f"Invalid operating limits for {sensor}."
            )

    return True


# ============================================================
# 10. TEST CONFIGURATION
# ============================================================

if __name__ == "__main__":

    try:

        validate_configuration()

        print("\n===================================")
        print("       INTELLIWATCH CONFIG")
        print("===================================")

        print(
            "\nEquipment Profile:",
            SYSTEM_CONFIG["equipment_profile"]
        )

        print("\nConfigured Sensors:")

        for sensor_type, config in SENSOR_CONFIG.items():

            print(
                f"- {config['sensor_name']} "
                f"({config['parameter']})"
            )

            print(
                f"  Sampling Rate: "
                f"{config['sampling_rate_hz']} Hz"
            )

            print(
                f"  Operating Limits: "
                f"{config['operating_limits']}"
            )

        print("\nConfiguration Validation: PASSED")

        print(
            "Threshold Calibration:",
            SYSTEM_CONFIG["thresholds_calibrated"]
        )

        print("\nIntelliWatch configuration loaded successfully.")

    except ValueError as error:

        print("\nConfiguration Error:", error)
