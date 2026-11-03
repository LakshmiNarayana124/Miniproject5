"""
INTELLIWATCH - ISO STANDARDS AND THRESHOLDS
Version: 1.0

Purpose:
1. Apply ISO 10816/20816 vibration severity zones to classify a vibration
   Monitoring_Parameter into Normal, Warning, and Critical bands
   (Requirement 7.1).
2. Structure Monitoring_Parameter acquisition, analysis, and recommendation
   following the ISO 17359 condition-monitoring guidance (Requirement 7.2).
3. Document, for each Monitoring_Parameter threshold, the recognized standard
   the threshold derives from, or flag it equipment-specific and inactive until
   operator confirmation (Requirements 7.3, 7.4).
4. Persist and load threshold definitions through the ``threshold_definitions``
   database table.

ISO 17359 workflow stages (documented guidance):
    detection -> analysis -> diagnosis -> prognosis -> post-remedial

The ``ConditionMonitoringWorkflow`` class exposes three phases that map onto
those stages:

    acquire(sensor_name, readings)    -> data acquisition  (detection)
    analyze(readings, features)      -> analysis          (analysis + diagnosis)
    recommend(status, causes)        -> recommendation    (prognosis + post-remedial)

Dependencies:
- ``database`` (``get_connection``, ``current_timestamp``) for threshold
  persistence.
- Python standard library only (``math``).

NOTE:
Threshold values follow ISO 10816-3:2009 velocity boundaries for typical
industrial machines (Group 2) as specified for this implementation:
    Zone A (Normal)   : 0     to 1.4 mm/s
    Zone B (Warning)   : 1.4   to 2.8 mm/s
    Zone C/D (Critical): above  2.8 mm/s
Acceleration thresholds follow ISO 20816-1:2016 guidance. Equipment-specific
thresholds that cannot be mapped to a recognized standard are flagged
``equipment_specific`` and remain inactive until an operator confirms them
(Requirement 7.4).
"""

import math
from typing import Any, Dict, List, Optional

from database import get_connection, current_timestamp


# ============================================================
# 1. ISO 10816 / ISO 20816 VIBRATION SEVERITY ZONES
# ============================================================

# Severity-zone label mapping (ISO 10816 / ISO 20816 zone letters).
# Zones C and D both map to the Critical system status.
SEVERITY_ZONES: Dict[str, str] = {
    "A": "normal",
    "B": "warning",
    "C": "critical",
    "D": "critical",
}

# Valid system-status strings returned by the classifiers.
SEVERITY_STATUSES = ("normal", "warning", "critical")

# Default ISO 10816-3 velocity thresholds (mm/s RMS).
# These are the Group 2 (15-300 kW) representative boundaries used by the
# default classifier, matching the values specified for this implementation.
ISO_10816_3_DEFAULT = {
    "normal_max": 1.4,            # Zone A upper bound (mm/s RMS)
    "warning_max": 2.8,           # Zone B upper bound (mm/s RMS)
    "source_standard": "ISO 10816-3:2009",
}

# ISO 10816-3 machine-group reference (documentation of the group basis).
# Group selection is based on rated power and mounting. The default classifier
# uses Group 2 representative boundaries; Group 1 (large machines) tolerates
# higher velocity magnitudes.
ISO_10816_3_GROUPS: Dict[int, Dict[str, Any]] = {
    1: {
        "description": "Large machines (rated power > 300 kW, 150-15000 r/min)",
        "normal_max": 2.8,
        "warning_max": 4.5,
        "source_standard": "ISO 10816-3:2009",
    },
    2: {
        "description": "Medium machines (15-300 kW, 150-15000 r/min)",
        "normal_max": 1.4,
        "warning_max": 2.8,
        "source_standard": "ISO 10816-3:2009",
    },
    3: {
        "description": "Small machines with separate drives (< 15 kW)",
        "normal_max": 1.4,
        "warning_max": 2.8,
        "source_standard": "ISO 10816-3:2009",
    },
    4: {
        "description": "Small machines with integrated drives (< 15 kW)",
        "normal_max": 1.4,
        "warning_max": 2.8,
        "source_standard": "ISO 10816-3:2009",
    },
}

# ISO 20816 acceleration thresholds (g RMS).
# ISO 20816-1:2016 generalizes machine vibration evaluation; these acceleration
# boundaries are used for high-frequency / bearing-condition monitoring where
# acceleration magnitude is the appropriate evaluation quantity.
ISO_20816_ACCELERATION = {
    "normal_max": 1.0,            # Zone A upper bound (g RMS)
    "warning_max": 2.0,           # Zone B upper bound (g RMS)
    "source_standard": "ISO 20816-1:2016",
}


def _validate_vibration_value(value: float, name: str) -> float:
    """Validate a vibration magnitude value before classification.

    Returns the value as a float, or raises ``ValueError`` when the value is
    ``None``, non-finite (``NaN``/``inf``), or negative (an invalid magnitude).
    """
    if value is None:
        raise ValueError(f"{name} must be a finite number, got None.")

    try:
        value = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number, got {value!r}.") \
            from error

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value!r}.")

    return value


def _classify_by_thresholds(
    value: float,
    normal_max: float,
    warning_max: float
) -> str:
    """Classify a magnitude into Normal/Warning/Critical using two boundaries.

    - ``value < normal_max``        -> ``"normal"``
    - ``normal_max <= value < warning_max`` -> ``"warning"``
    - ``value >= warning_max``      -> ``"critical"``
    """
    if value < normal_max:
        return "normal"
    if value < warning_max:
        return "warning"
    return "critical"


def classify_vibration_severity(rms_velocity_mm_s: float) -> str:
    """Classify a vibration velocity RMS value into an ISO 10816/20816 zone.

    Uses the default ISO 10816-3:2009 boundaries (Group 2 representative):
    Normal ends at 1.4 mm/s (Zone A), Warning spans 1.4-2.8 mm/s (Zone B),
    and Critical begins above 2.8 mm/s (Zones C/D).

    Parameters
    ----------
    rms_velocity_mm_s : float
        Vibration velocity RMS in mm/s (non-negative finite number).

    Returns
    -------
    str
        One of ``"normal"``, ``"warning"``, or ``"critical"``.

    Raises
    ------
    ValueError
        If the value is ``None``, non-finite, or negative.
    """
    value = _validate_vibration_value(rms_velocity_mm_s, "rms_velocity_mm_s")
    return _classify_by_thresholds(
        value,
        ISO_10816_3_DEFAULT["normal_max"],
        ISO_10816_3_DEFAULT["warning_max"],
    )


def classify_vibration_severity_for_group(
    rms_velocity_mm_s: float,
    machine_group: int = 2
) -> str:
    """Classify velocity RMS using ISO 10816-3 thresholds for a machine group.

    Parameters
    ----------
    rms_velocity_mm_s : float
        Vibration velocity RMS in mm/s (non-negative finite number).
    machine_group : int
        ISO 10816-3 machine group (1-4). Defaults to 2.

    Returns
    -------
    str
        One of ``"normal"``, ``"warning"``, or ``"critical"``.
    """
    if machine_group not in ISO_10816_3_GROUPS:
        raise ValueError(
            f"Unknown ISO 10816-3 machine group: {machine_group!r}. "
            f"Valid groups: {sorted(ISO_10816_3_GROUPS)}."
        )
    value = _validate_vibration_value(rms_velocity_mm_s, "rms_velocity_mm_s")
    group = ISO_10816_3_GROUPS[machine_group]
    return _classify_by_thresholds(
        value, group["normal_max"], group["warning_max"]
    )


def classify_vibration_severity_acceleration(
    rms_acceleration_g: float
) -> str:
    """Classify a vibration acceleration RMS value (ISO 20816) into a zone.

    Uses ISO 20816-1:2016 acceleration boundaries:
    Normal ends at 1.0 g (Zone A), Warning spans 1.0-2.0 g (Zone B), and
    Critical begins above 2.0 g (Zones C/D).

    Parameters
    ----------
    rms_acceleration_g : float
        Vibration acceleration RMS in g (non-negative finite number).

    Returns
    -------
    str
        One of ``"normal"``, ``"warning"``, or ``"critical"``.

    Raises
    ------
    ValueError
        If the value is ``None``, non-finite, or negative.
    """
    value = _validate_vibration_value(rms_acceleration_g, "rms_acceleration_g")
    return _classify_by_thresholds(
        value,
        ISO_20816_ACCELERATION["normal_max"],
        ISO_20816_ACCELERATION["warning_max"],
    )


def classify_vibration_zone(rms_velocity_mm_s: float) -> str:
    """Return the ISO 10816/20816 zone letter for a velocity value.

    Returns one of ``"A"``, ``"B"``, ``"C"``, ``"D"`` where Zone D is the
    region above the Group 1 critical boundary (4.5 mm/s) and Zone C spans the
    2.8-4.5 mm/s band.
    """
    value = _validate_vibration_value(rms_velocity_mm_s, "rms_velocity_mm_s")
    if value < ISO_10816_3_DEFAULT["normal_max"]:
        return "A"
    if value < ISO_10816_3_DEFAULT["warning_max"]:
        return "B"
    if value < ISO_10816_3_GROUPS[1]["warning_max"]:
        return "C"
    return "D"


# ============================================================
# 2. THRESHOLD SOURCE DOCUMENTATION
# ============================================================

# Every defined threshold carries a non-empty ``source_standard`` documenting
# the recognized standard it derives from (Requirement 7.3). Thresholds that
# cannot be mapped to a standard are flagged ``equipment_specific`` and kept
# inactive until operator confirmation (Requirement 7.4).
THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "vibration_velocity_rms": {
        "unit": "mm/s",
        "normal_max": ISO_10816_3_DEFAULT["normal_max"],
        "warning_max": ISO_10816_3_DEFAULT["warning_max"],
        "source_standard": ISO_10816_3_DEFAULT["source_standard"],
        "equipment_specific": False,
        "zones": {
            "A": {"label": "normal", "range": "0 to 1.4 mm/s"},
            "B": {"label": "warning", "range": "1.4 to 2.8 mm/s"},
            "C": {"label": "critical", "range": "2.8 to 4.5 mm/s"},
            "D": {"label": "critical", "range": "above 4.5 mm/s"},
        },
    },
    "vibration_acceleration_rms": {
        "unit": "g",
        "normal_max": ISO_20816_ACCELERATION["normal_max"],
        "warning_max": ISO_20816_ACCELERATION["warning_max"],
        "source_standard": ISO_20816_ACCELERATION["source_standard"],
        "equipment_specific": False,
        "zones": {
            "A": {"label": "normal", "range": "0 to 1.0 g"},
            "B": {"label": "warning", "range": "1.0 to 2.0 g"},
            "C": {"label": "critical", "range": "2.0 to 3.0 g"},
            "D": {"label": "critical", "range": "above 3.0 g"},
        },
    },
}


def get_threshold(parameter_name: str) -> Optional[Dict[str, Any]]:
    """Return a documented threshold definition by parameter name, or None."""
    return THRESHOLDS.get(parameter_name)


def threshold_source_standard(parameter_name: str) -> Optional[str]:
    """Return the documented source standard for a threshold (Requirement 7.3).

    Returns ``None`` when the parameter has no documented threshold, which
    callers should treat as an equipment-specific threshold requiring
    confirmation before activation (Requirement 7.4).
    """
    threshold = THRESHOLDS.get(parameter_name)
    if threshold is None:
        return None
    return threshold.get("source_standard")


def is_equipment_specific(parameter_name: str) -> bool:
    """Whether a threshold is equipment-specific (not standard-sourced)."""
    threshold = THRESHOLDS.get(parameter_name)
    if threshold is None:
        return True
    source = threshold.get("source_standard")
    return not (source and source.strip())


# ============================================================
# 3. ISO 17359 CONDITION MONITORING WORKFLOW
# ============================================================

# ISO 17359 condition-monitoring guidance stages, in order.
ISO_17359_STAGES = (
    "detection",       # data acquisition and initial detection
    "analysis",        # signal analysis and feature extraction
    "diagnosis",       # identify the fault / probable cause
    "prognosis",       # estimate remaining useful life / trend
    "post-remedial",   # verify the outcome after corrective action
)

# Mapping of the workflow phases onto the ISO 17359 stages.
ISO_17359_PHASE_MAPPING = {
    "acquire": ("detection",),
    "analyze": ("analysis", "diagnosis"),
    "recommend": ("prognosis", "post-remedial"),
}

# Status to remedial-action intent, mirroring the equipment-control mapping.
STATUS_TO_REMEDIAL = {
    "normal": "RUN",
    "warning": "DE_RATE",
    "critical": "SHUTDOWN",
}


def _finite_values(values: List[float]) -> List[float]:
    """Return only the finite, non-None elements of a numeric window."""
    return [v for v in values if v is not None and math.isfinite(v)]


class ConditionMonitoringWorkflow:
    """Structure monitoring data per ISO 17359 guidance (Requirement 7.2).

    The workflow runs three phases that map onto the ISO 17359 stages
    (detection -> analysis -> diagnosis -> prognosis -> post-remedial):

    - ``acquire(sensor_name, readings)``  : data acquisition (detection)
    - ``analyze(readings, features)``      : analysis + diagnosis
    - ``recommend(status, causes)``         : prognosis + post-remedial

    Each phase returns a record describing what was produced and appends the
    corresponding ISO 17359 stages to the workflow lifecycle.
    """

    def __init__(self) -> None:
        self.last_acquisition: Optional[Dict[str, Any]] = None
        self.last_analysis: Optional[Dict[str, Any]] = None
        self.stages_executed: List[str] = []

    # --------------------------------------------------------
    # PHASE 1: data acquisition (detection)
    # --------------------------------------------------------
    def acquire(
        self,
        sensor_name: str,
        readings: List[float]
    ) -> Dict[str, Any]:
        """Data acquisition phase.

        Records the source sensor and the raw readings for downstream
        analysis. Maps onto the ISO 17359 ``detection`` stage.

        Parameters
        ----------
        sensor_name : str
            Identifier of the sensor / channel that produced the readings.
        readings : list of float
            Raw sensor window samples.

        Returns
        -------
        dict
            Acquisition record carrying the sensor name, sample count, and a
            timestamp.
        """
        if not sensor_name:
            raise ValueError("sensor_name is required.")
        if readings is None:
            readings = []

        record = {
            "stage": "acquisition",
            "iso_stage": "detection",
            "sensor_name": sensor_name,
            "sample_count": len(readings),
            "available_samples": len(_finite_values(readings)),
            "timestamp": current_timestamp(),
        }
        self.last_acquisition = record
        self.stages_executed.append("detection")
        return record

    # --------------------------------------------------------
    # PHASE 2: analysis + diagnosis
    # --------------------------------------------------------
    def analyze(
        self,
        readings: List[float],
        features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analysis phase: feature extraction + severity classification.

        Uses precomputed ``features`` when provided; otherwise derives an
        acceleration RMS from the raw readings (assumed to be in g) and
        classifies it against the ISO 20816 acceleration thresholds. Maps onto
        the ISO 17359 ``analysis`` and ``diagnosis`` stages.

        Parameters
        ----------
        readings : list of float
            Raw sensor window samples (used when features are absent).
        features : dict, optional
            Precomputed monitoring parameters. Recognized keys:
            ``vibration_rms_mm_s`` (velocity, ISO 10816-3) and
            ``vibration_rms_g`` (acceleration, ISO 20816).

        Returns
        -------
        dict
            Analysis record carrying the classified ``status``, the
            classification method used, and the input features.
        """
        features = features or {}

        velocity = features.get("vibration_rms_mm_s")
        acceleration = features.get("vibration_rms_g")

        if velocity is not None:
            status = classify_vibration_severity(float(velocity))
            method = "velocity RMS (ISO 10816-3:2009)"
        elif acceleration is not None:
            status = classify_vibration_severity_acceleration(float(acceleration))
            method = "acceleration RMS (ISO 20816-1:2016)"
        elif readings:
            clean = _finite_values(readings)
            if clean:
                acc_rms = math.sqrt(
                    sum(v * v for v in clean) / len(clean)
                )
                status = classify_vibration_severity_acceleration(acc_rms)
                method = "derived acceleration RMS (ISO 20816-1:2016)"
            else:
                status = "normal"
                method = "no usable samples"
        else:
            status = "normal"
            method = "no data"

        record = {
            "stage": "analysis",
            "iso_stage": "analysis/diagnosis",
            "status": status,
            "method": method,
            "features": dict(features),
            "timestamp": current_timestamp(),
        }
        self.last_analysis = record
        self.stages_executed.extend(["analysis", "diagnosis"])
        return record

    # --------------------------------------------------------
    # PHASE 3: recommendation (prognosis + post-remedial)
    # --------------------------------------------------------
    def recommend(
        self,
        status: str,
        causes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Recommendation phase: prognosis and post-remedial guidance.

        Produces a recommendation record mapping the analyzed status to a
        remedial-action intent and listing probable causes. Maps onto the ISO
        17359 ``prognosis`` and ``post-remedial`` stages.

        Parameters
        ----------
        status : str
            System status from the analysis phase (``"normal"``,
            ``"warning"``, or ``"critical"``).
        causes : list of str, optional
            Probable causes identified during diagnosis.

        Returns
        -------
        dict
            Recommendation record carrying the remedial intent, probable
            causes, and guidance.
        """
        status = (status or "normal").lower()
        if status not in STATUS_TO_REMEDIAL:
            raise ValueError(
                f"Unknown status: {status!r}. "
                f"Valid statuses: {sorted(STATUS_TO_REMEDIAL)}."
            )
        causes = list(causes or [])

        guidance = {
            "normal": (
                "Continue routine monitoring; no intervention required."
            ),
            "warning": (
                "Investigate probable causes and reduce operating intensity "
                "to bring readings back within the normal band."
            ),
            "critical": (
                "Shut down equipment promptly and perform corrective "
                "maintenance before resuming operation."
            ),
        }

        record = {
            "stage": "recommendation",
            "iso_stage": "prognosis/post-remedial",
            "status": status,
            "causes": causes,
            "remedial_action": STATUS_TO_REMEDIAL[status],
            "guidance": guidance[status],
            "timestamp": current_timestamp(),
        }
        self.stages_executed.extend(["prognosis", "post-remedial"])
        return record

    # --------------------------------------------------------
    # FULL WORKFLOW RUN
    # --------------------------------------------------------
    def run(
        self,
        sensor_name: str,
        readings: List[float],
        features: Optional[Dict[str, Any]] = None,
        causes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run the full ISO 17359 workflow end to end.

        Convenience helper that executes acquire -> analyze -> recommend and
        returns the consolidated result.
        """
        self.acquire(sensor_name, readings)
        analysis = self.analyze(readings, features)
        recommendation = self.recommend(analysis["status"], causes)
        return {
            "acquisition": self.last_acquisition,
            "analysis": analysis,
            "recommendation": recommendation,
            "stages_executed": list(self.stages_executed),
        }


# ============================================================
# 4. THRESHOLD DEFINITIONS DATABASE INTEGRATION
# ============================================================

def save_threshold_to_db(
    parameter_name: str,
    normal_max: float,
    warning_max: float,
    source_standard: Optional[str],
    equipment_specific: int = 0
) -> int:
    """Persist a threshold definition to the ``threshold_definitions`` table.

    Standard-sourced thresholds (``equipment_specific=0``) are activated
    immediately. Equipment-specific thresholds that cannot be mapped to a
    recognized standard (``equipment_specific=1``) are stored inactive until an
    operator confirms them (Requirement 7.4).

    Any prior definition for the same ``parameter_name`` is replaced so that
    exactly one definition per parameter exists.

    Parameters
    ----------
    parameter_name : str
        Canonical monitoring-parameter name (e.g. ``"vibration_velocity_rms"``).
    normal_max : float
        Upper bound of the Normal (Zone A) band.
    warning_max : float
        Upper bound of the Warning (Zone B) band; Critical begins above this.
    source_standard : str or None
        Recognized standard the threshold derives from (Requirement 7.3). May
        be ``None`` for equipment-specific thresholds.
    equipment_specific : int
        ``1`` flags the threshold as equipment-specific and inactive until
        operator confirmation; ``0`` marks it standard-sourced and active.

    Returns
    -------
    int
        The row id of the inserted threshold definition.
    """
    if not parameter_name or not str(parameter_name).strip():
        raise ValueError("parameter_name is required.")

    normal_max = float(normal_max)
    warning_max = float(warning_max)

    if not (math.isfinite(normal_max) and math.isfinite(warning_max)):
        raise ValueError("normal_max and warning_max must be finite.")

    if normal_max < 0 or warning_max < 0:
        raise ValueError("normal_max and warning_max must be non-negative.")

    if normal_max >= warning_max:
        raise ValueError("normal_max must be lower than warning_max.")

    equipment_specific = 1 if equipment_specific else 0
    # Equipment-specific thresholds are inactive until operator confirmation
    # (Requirement 7.4); standard-sourced thresholds activate immediately.
    active = 0 if equipment_specific else 1

    connection = get_connection()

    try:
        # Replace any prior definition so one definition exists per parameter.
        connection.execute(
            "DELETE FROM threshold_definitions WHERE parameter_name = ?",
            (parameter_name,)
        )

        cursor = connection.execute("""
            INSERT INTO threshold_definitions (
                parameter_name,
                normal_max,
                warning_max,
                source_standard,
                equipment_specific,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            parameter_name,
            normal_max,
            warning_max,
            source_standard,
            equipment_specific,
            active
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def load_thresholds_from_db() -> Dict[str, Dict[str, Any]]:
    """Load active threshold definitions from the ``threshold_definitions`` table.

    Only ``active = 1`` rows are returned. Equipment-specific thresholds that
    have not yet been operator-confirmed (``active = 0``) are excluded, so that
    unconfirmed thresholds never drive detection decisions (Requirement 7.4).

    Returns
    -------
    dict
        Mapping of parameter name to its threshold definition, each carrying
        ``normal_max``, ``warning_max``, ``source_standard``,
        ``equipment_specific`` and ``active`` fields.
    """
    connection = get_connection()

    try:
        results = connection.execute("""
            SELECT parameter_name,
                   normal_max,
                   warning_max,
                   source_standard,
                   equipment_specific,
                   active
            FROM threshold_definitions
            WHERE active = 1
            ORDER BY parameter_name
        """).fetchall()

        thresholds: Dict[str, Dict[str, Any]] = {}
        for row in results:
            thresholds[row["parameter_name"]] = {
                "normal_max": row["normal_max"],
                "warning_max": row["warning_max"],
                "source_standard": row["source_standard"],
                "equipment_specific": bool(row["equipment_specific"]),
                "active": bool(row["active"]),
            }

        return thresholds

    finally:
        connection.close()


def get_threshold_from_db(parameter_name: str) -> Optional[Dict[str, Any]]:
    """Return the active threshold definition for a parameter, or None."""
    return load_thresholds_from_db().get(parameter_name)


def classify_with_db_thresholds(
    parameter_name: str,
    value: float
) -> Optional[str]:
    """Classify a value using a DB-loaded active threshold.

    Returns ``"normal"``, ``"warning"``, or ``"critical"`` when an active
    threshold exists for ``parameter_name``; otherwise ``None`` so the caller
    can fall back to the standard ``THRESHOLDS`` or flag the value as
    equipment-specific.
    """
    threshold = load_thresholds_from_db().get(parameter_name)
    if threshold is None:
        return None
    checked = _validate_vibration_value(value, "value")
    return _classify_by_thresholds(
        checked,
        threshold["normal_max"],
        threshold["warning_max"],
    )


# ============================================================
# 5. SELF-TEST
# ============================================================

def _self_test() -> None:
    """Verify classification, workflow, threshold documentation, and DB I/O."""

    print("ISO 10816/20816 vibration severity classification")
    print("-" * 52)

    # Velocity boundaries (ISO 10816-3:2009, Group 2 representative).
    assert classify_vibration_severity(0.0) == "normal", "0.0 should be normal"
    assert classify_vibration_severity(1.3) == "normal", "1.3 should be normal"
    assert classify_vibration_severity(1.4) == "warning", "1.4 starts warning"
    assert classify_vibration_severity(2.7) == "warning", "2.7 should be warning"
    assert classify_vibration_severity(2.8) == "critical", "2.8 starts critical"
    assert classify_vibration_severity(5.0) == "critical", "5.0 should be critical"
    print("  [PASS] velocity boundaries (normal / warning / critical)")

    # Zone letters.
    assert classify_vibration_zone(0.5) == "A"
    assert classify_vibration_zone(1.4) == "B"
    assert classify_vibration_zone(3.0) == "C"
    assert classify_vibration_zone(5.0) == "D"
    print("  [PASS] zone letters (A / B / C / D)")

    # Group-specific classification.
    assert classify_vibration_severity_for_group(3.0, 1) == "warning"
    assert classify_vibration_severity_for_group(3.0, 2) == "critical"
    print("  [PASS] machine-group-specific thresholds")

    # Acceleration boundaries (ISO 20816-1:2016).
    assert classify_vibration_severity_acceleration(0.5) == "normal"
    assert classify_vibration_severity_acceleration(1.0) == "warning"
    assert classify_vibration_severity_acceleration(2.0) == "critical"
    assert classify_vibration_severity_acceleration(3.0) == "critical"
    print("  [PASS] acceleration boundaries (ISO 20816)")

    # Invalid inputs are rejected.
    for bad in (None, float("nan"), float("inf"), -1.0):
        try:
            classify_vibration_severity(bad)  # type: ignore[arg-type]
            raise AssertionError(f"expected ValueError for {bad!r}")
        except ValueError:
            pass
    print("  [PASS] invalid input rejection")

    print("\nThreshold source documentation")
    print("-" * 52)

    # Every documented threshold carries a non-empty source_standard.
    for name, definition in THRESHOLDS.items():
        assert "source_standard" in definition, f"missing source for {name}"
        assert definition["source_standard"], (
            f"empty source_standard for {name}"
        )
    assert threshold_source_standard("vibration_velocity_rms") == \
        "ISO 10816-3:2009"
    assert threshold_source_standard("vibration_acceleration_rms") == \
        "ISO 20816-1:2016"
    assert threshold_source_standard("unknown_param") is None
    assert is_equipment_specific("unknown_param") is True
    assert is_equipment_specific("vibration_velocity_rms") is False
    print("  [PASS] each threshold carries a documented source standard")
    print("  [PASS] equipment-specific detection for unmapped parameters")

    print("\nISO 17359 condition monitoring workflow")
    print("-" * 52)

    assert ISO_17359_STAGES == (
        "detection", "analysis", "diagnosis", "prognosis", "post-remedial"
    )
    print("  [PASS] ISO 17359 stages documented")

    workflow = ConditionMonitoringWorkflow()

    acquisition = workflow.acquire("ADXL345", [0.1, 0.2, 0.15, None])
    assert acquisition["stage"] == "acquisition"
    assert acquisition["sensor_name"] == "ADXL345"
    assert acquisition["sample_count"] == 4
    assert acquisition["available_samples"] == 3
    print("  [PASS] acquire() records sensor and sample count")

    analysis = workflow.analyze(
        [0.1, 0.2, 0.15],
        features={"vibration_rms_mm_s": 3.0}
    )
    assert analysis["status"] == "critical"
    assert analysis["method"].startswith("velocity RMS")
    print("  [PASS] analyze() classifies via velocity features")

    analysis_acc = workflow.analyze([0.1, 0.2, 0.15])
    assert analysis_acc["status"] == "normal"
    assert "acceleration" in analysis_acc["method"]
    print("  [PASS] analyze() derives acceleration RMS from readings")

    recommendation = workflow.recommend(
        analysis["status"], ["Loose mounting", "Bearing wear"]
    )
    assert recommendation["remedial_action"] == "SHUTDOWN"
    assert recommendation["causes"] == ["Loose mounting", "Bearing wear"]
    print("  [PASS] recommend() maps status to remedial action")

    full = ConditionMonitoringWorkflow().run(
        "ADXL345",
        [0.1, 0.2, 0.15],
        features={"vibration_rms_mm_s": 1.5},
        causes=["Operating load change"]
    )
    assert full["analysis"]["status"] == "warning"
    assert full["recommendation"]["remedial_action"] == "DE_RATE"
    assert full["stages_executed"] == [
        "detection", "analysis", "diagnosis", "prognosis", "post-remedial"
    ]
    print("  [PASS] run() executes the full ISO 17359 lifecycle")

    print("\nThreshold definitions database integration")
    print("-" * 52)

    standard_param = "selftest_iso_velocity"
    equip_param = "selftest_iso_equipment_specific"

    try:
        # Ensure the schema exists (idempotent, matches database.py convention).
        from database import initialize_database
        initialize_database()

        # Standard-sourced threshold -> stored active (Requirement 7.3).
        save_threshold_to_db(
            standard_param, 1.4, 2.8, "ISO 10816-3:2009", equipment_specific=0
        )
        # Equipment-specific threshold -> stored inactive (Requirement 7.4).
        save_threshold_to_db(
            equip_param, 1.2, 2.5, None, equipment_specific=1
        )

        loaded = load_thresholds_from_db()
        assert standard_param in loaded, "active standard threshold missing"
        assert equip_param not in loaded, (
            "equipment-specific threshold should be inactive until confirmed"
        )
        assert loaded[standard_param]["source_standard"] == "ISO 10816-3:2009"
        assert loaded[standard_param]["equipment_specific"] is False

        classified = classify_with_db_thresholds(standard_param, 3.0)
        assert classified == "critical", "DB threshold classification failed"
        print("  [PASS] standard threshold stored active and classifies")
        print("  [PASS] equipment-specific threshold inactive until confirmed")
        print("  [PASS] DB-driven classification works")

    finally:
        # Clean up the self-test rows so the production table stays clean.
        connection = get_connection()
        try:
            connection.execute(
                "DELETE FROM threshold_definitions "
                "WHERE parameter_name IN (?, ?)",
                (standard_param, equip_param)
            )
            connection.commit()
        finally:
            connection.close()

    print("\nAll ISO standards self-tests passed.")


if __name__ == "__main__":
    _self_test()
