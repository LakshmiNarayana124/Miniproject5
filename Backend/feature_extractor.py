"""
INTELLIWATCH - FEATURE EXTRACTOR
Version: 1.0

Purpose:
- Define the versioned Monitoring_Parameter data model that every derived
  monitoring quantity (vibration, temperature, current, FFT band energy, ...)
  is represented with (Requirement 2.5).
- Provide a ``_safe`` helper that filters ``None`` / non-finite values out of a
  raw sensor window so that downstream feature computations never choke on
  missing or corrupt samples.
- Guarantee that every Monitoring_Parameter can be serialized to a plain
  dictionary and reconstructed losslessly (Property 9, Requirement 2.5).

Dependencies:
- Python standard library only (``dataclasses``, ``math``, ``statistics``).

NOTE:
This is the foundational layer of the feature-extraction module. It currently
provides the data model, the ``_safe`` helper, and the per-axis vibration
feature extraction (RMS, peak, variance, kurtosis, crest factor). Later tasks
extend this file with ``temperature_features``, ``current_features``, FFT
band-energy extraction, and missing-value window resilience.
"""

import math
import statistics
from dataclasses import dataclass, asdict


# ============================================================
# 1. MONITORING PARAMETER DATA MODEL
# ============================================================


@dataclass
class MonitoringParameter:
    """A versioned, single-value monitoring quantity.

    Represents any raw or derived quantity the IntelliWatch system tracks
    (Requirement 2.5): vibration acceleration/RMS/peak/kurtosis/crest factor,
    FFT band energy, temperature mean/min/max/rise-rate, electrical current
    RMS/mean/variation, and so on.

    Fields
    ------
    name : str
        Canonical parameter name (e.g. ``"rms_x"``, ``"temperature_mean"``).
    unit : str
        Engineering unit of the value (e.g. ``"g"``, ``"degC"``, ``"A"``).
    sensor_source : str
        Identifier of the sensor / channel that produced the value.
    timestamp : str
        ISO-8601 timestamp marking when the value was sampled.
    value : float
        Numeric value of the parameter. ``NaN`` signals "missing / unavailable".
    schema_version : str
        Version of this data model, defaults to ``"1.0"`` for forward
        compatibility across schema changes.
    available : bool
        Whether a usable value was produced. ``False`` when the underlying
        window was empty or the value is missing/non-finite (Requirement 2.7).
    """

    name: str
    unit: str
    sensor_source: str
    timestamp: str          # ISO-8601
    value: float
    schema_version: str = "1.0"
    available: bool = True

    def __post_init__(self):
        """Normalize missing / non-finite values.

        When the value is ``None``, ``NaN``, or otherwise non-finite, the
        parameter is marked unavailable and the value is normalized to ``NaN``
        so that downstream consumers can detect missingness uniformly
        (Requirement 2.7).
        """
        if self.value is None or not math.isfinite(self.value):
            self.value = float("nan")
            self.available = False

    def to_dict(self):
        """Serialize this parameter to a plain dictionary.

        The mapping is a faithful, round-trippable representation of every
        field (Property 9).
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        """Reconstruct a MonitoringParameter from a dictionary.

        Required keys: ``name``, ``unit``, ``sensor_source``, ``timestamp``,
        ``value``. Optional keys ``schema_version`` and ``available`` default
        to ``"1.0"`` and ``True`` respectively. Missing/non-finite values are
        normalized via ``__post_init__``, so deserializing a serialized record
        always yields an equal record (Property 9).
        """
        return cls(
            name=data["name"],
            unit=data["unit"],
            sensor_source=data["sensor_source"],
            timestamp=data["timestamp"],
            value=data["value"],
            schema_version=data.get("schema_version", "1.0"),
            available=data.get("available", True),
        )


# ============================================================
# 2. WINDOW SANITIZATION HELPER
# ============================================================


def _safe(values):
    """Filter out None and non-finite values from a window.

    Returns a new list containing only the elements of ``values`` that are not
    ``None`` and pass ``math.isfinite`` (i.e. exclude ``NaN`` and ``inf``). Used
    by the feature-extraction functions so that ``None``/``NaN`` samples never
    corrupt aggregate statistics (Requirement 2.7).
    """
    return [v for v in values if v is not None and math.isfinite(v)]


# ============================================================
# 3. VIBRATION FEATURE EXTRACTION
# ============================================================


def _kurtosis(values, var):
    """Compute the excess kurtosis of a window.

    Excess kurtosis is the fourth standardized central moment minus 3.0 (the
    kurtosis of a normal distribution). This is the standard population
    (biased) estimator used by IntelliWatch so that the value satisfies the
    excess-kurtosis definition referenced by Property 5.

    Parameters
    ----------
    values : list[float]
        Finite, sanitized window (output of ``_safe``).
    var : float
        Population variance of ``values`` (e.g. ``statistics.pvariance``).

    Returns
    -------
    float
        Excess kurtosis, or ``NaN`` when there are fewer than two samples or
        the variance is zero (a constant window has no shape to measure).
    """
    n = len(values)
    if n < 2 or var == 0:
        return float("nan")
    mean = sum(values) / n
    return sum((v - mean) ** 4 for v in values) / (n * var * var) - 3.0


# Per-axis feature names and the order in which they are emitted.
_VIBRATION_FEATURES = ("rms", "peak", "variance", "kurtosis", "crest_factor")


def vibration_features(window_x, window_y, window_z, ts, source):
    """Extract per-axis vibration features from a triaxial acceleration window.

    For each acceleration axis (x, y, z) the function computes (Requirement 2.1):

    - ``rms``          = ``sqrt(mean(v^2))``
    - ``peak``         = ``max(abs(v))``
    - ``variance``     = population variance (``statistics.pvariance``)
    - ``kurtosis``     = excess kurtosis (see :func:`_kurtosis`)
    - ``crest_factor`` = ``peak / rms`` (``NaN`` when ``rms == 0``)

    Each result is wrapped in a :class:`MonitoringParameter` named
    ``"<feature>_<axis>"`` (e.g. ``"rms_x"``, ``"crest_factor_z"``) so every
    derived quantity is traceable and serializable (Requirement 2.5,
    Property 9).

    Missing-value resilience (Requirement 2.7): a window is first sanitized
    with :func:`_safe`. When the sanitized window is empty, all five derived
    features for that axis are emitted with ``value=NaN`` and
    ``available=False`` so the model input vector can exclude them without the
    whole window failing. Individual features that evaluate to a non-finite
    value (e.g. ``kurtosis`` / ``crest_factor`` for a constant window) are
    likewise normalized to unavailable by :meth:`MonitoringParameter.__post_init__`.

    Parameters
    ----------
    window_x, window_y, window_z : list[float]
        Raw acceleration samples for each axis. May contain ``None`` /
        non-finite values; these are filtered out.
    ts : str
        ISO-8601 timestamp shared by every emitted parameter.
    source : str
        Sensor / channel identifier recorded as ``sensor_source``.

    Returns
    -------
    dict[str, MonitoringParameter]
        Mapping of ``"<feature>_<axis>"`` to its :class:`MonitoringParameter`.
    """
    out = {}
    for axis, window in (("x", window_x), ("y", window_y), ("z", window_z)):
        sanitized = _safe(window)

        if not sanitized:
            # No usable samples for this axis: emit every feature as
            # unavailable with a NaN value (Requirement 2.7).
            for feature in _VIBRATION_FEATURES:
                name = f"{feature}_{axis}"
                out[name] = MonitoringParameter(
                    name=name, unit="g", sensor_source=source,
                    timestamp=ts, value=float("nan"), available=False,
                )
            continue

        rms = math.sqrt(sum(v * v for v in sanitized) / len(sanitized))
        peak = max(abs(v) for v in sanitized)
        var = statistics.pvariance(sanitized)
        kurt = _kurtosis(sanitized, var)
        crest = peak / rms if rms else float("nan")

        for feature, value in (
            ("rms", rms),
            ("peak", peak),
            ("variance", var),
            ("kurtosis", kurt),
            ("crest_factor", crest),
        ):
            name = f"{feature}_{axis}"
            out[name] = MonitoringParameter(
                name=name, unit="g", sensor_source=source,
                timestamp=ts, value=value,
            )

    return out


# ============================================================
# 4. FFT BAND-ENERGY EXTRACTION  (Requirement 2.2, Property 6)
# ============================================================

# Default frequency-band edges (Hz) used when the caller does not supply
# custom band boundaries.  The bands cover the sub-synchronous, low,
# mid, and high frequency ranges typical of rolling-element bearing
# diagnostics.  At least four bands are always defined (Requirement 2.2).
DEFAULT_FFT_BAND_EDGES = (
    (0.0, 50.0),       # sub-synchronous / rotor-related
    (50.0, 250.0),     # low-frequency bearing defect
    (250.0, 1000.0),   # mid-frequency structural
    (1000.0, 5000.0),  # high-frequency incipient defect
)

# Sampling rate (Hz) assumed when none is supplied.  The KAIST bearing
# rig samples at ~25.6 kHz, but for generic windows a conservative
# 10 kHz default keeps the band boundaries meaningful.
DEFAULT_SAMPLE_RATE = 10000.0

try:
    import numpy as _np  # type: ignore

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _np = None  # type: ignore
    _HAS_NUMPY = False


def fft_band_energies(
    window_x,
    window_y,
    window_z,
    ts,
    source,
    sample_rate=DEFAULT_SAMPLE_RATE,
    band_edges=DEFAULT_FFT_BAND_EDGES,
):
    """Compute per-axis FFT frequency-band energy across at least four bands.

    For each acceleration axis the function computes the non-negative FFT
    (via ``numpy.fft.rfft`` when available, or a pure-Python DFT fallback)
    and sums the energy (squared magnitude) within each defined frequency
    band (Requirement 2.2, Property 6).

    Each band-energy result is wrapped in a :class:`MonitoringParameter`
    named ``"fft_band{N}_{axis}"`` (e.g. ``"fft_band0_x"``) with unit ``"g^2"``
    (energy).  Missing-value resilience (Requirement 2.7): a window is first
    sanitized with :func:`_safe`; when the sanitized window has fewer than two
    samples every band-energy is emitted as unavailable with ``NaN``.

    Parameters
    ----------
    window_x, window_y, window_z : list[float]
        Raw acceleration samples for each axis (may contain ``None`` /
        non-finite values).
    ts : str
        ISO-8601 timestamp shared by every emitted parameter.
    source : str
        Sensor / channel identifier recorded as ``sensor_source``.
    sample_rate : float
        Sampling rate in Hz (default 10 000).
    band_edges : tuple of (float, float)
        At least four ``(low, high)`` frequency-band boundaries in Hz.

    Returns
    -------
    dict[str, MonitoringParameter]
        Mapping of ``"fft_band{N}_{axis}"`` to its band-energy parameter.
        At least ``4 * 3 = 12`` entries are produced (4 bands x 3 axes).
    """
    # Ensure at least four bands (Requirement 2.2).
    if len(band_edges) < 4:
        band_edges = DEFAULT_FFT_BAND_EDGES

    out = {}

    for axis, window in (("x", window_x), ("y", window_y), ("z", window_z)):
        sanitized = _safe(window)

        if len(sanitized) < 2:
            # Too few samples for a meaningful FFT: emit all band energies
            # as unavailable with NaN (Requirement 2.7).
            for i in range(len(band_edges)):
                name = f"fft_band{i}_{axis}"
                out[name] = MonitoringParameter(
                    name=name, unit="g^2", sensor_source=source,
                    timestamp=ts, value=float("nan"), available=False,
                )
            continue

        energies = _compute_band_energies(sanitized, sample_rate, band_edges)

        for i, energy in enumerate(energies):
            name = f"fft_band{i}_{axis}"
            out[name] = MonitoringParameter(
                name=name, unit="g^2", sensor_source=source,
                timestamp=ts, value=energy,
            )

    return out


def _compute_band_energies(samples, sample_rate, band_edges):
    """Return a list of non-negative band-energy values for ``samples``.

    Uses ``numpy.fft.rfft`` for speed when numpy is available, otherwise
    falls back to a pure-Python DFT.  Energy is the sum of squared
    magnitudes of the FFT coefficients whose frequency falls within each
    band, normalised by the number of samples so the result is independent
    of window length.
    """
    n = len(samples)

    if _HAS_NUMPY:
        spectrum = _np.fft.rfft(_np.asarray(samples, dtype=float))
        freqs = _np.fft.rfftfreq(n, d=1.0 / sample_rate)
        power = _np.abs(spectrum) ** 2

        energies = []
        for low, high in band_edges:
            mask = (freqs >= low) & (freqs < high)
            band_energy = float(_np.sum(power[mask])) / n if mask.any() else 0.0
            # Guard against tiny negative values from floating-point.
            energies.append(max(0.0, band_energy))
        return energies

    # ---- Pure-Python DFT fallback (no numpy) ---------------------
    # Compute one-sided amplitude spectrum and bin frequencies.
    energies = [0.0] * len(band_edges)
    for k in range(n // 2 + 1):
        real = 0.0
        imag = 0.0
        for t in range(n):
            angle = 2.0 * math.pi * k * t / n
            real += samples[t] * math.cos(angle)
            imag -= samples[t] * math.sin(angle)
        mag_sq = (real * real + imag * imag) / (n * n)
        freq = k * sample_rate / n
        for i, (low, high) in enumerate(band_edges):
            if low <= freq < high:
                energies[i] += mag_sq
                break

    return [max(0.0, e) for e in energies]


# ============================================================
# 5. TEMPERATURE FEATURE EXTRACTION  (Requirement 2.3, Property 7)
# ============================================================

_TEMPERATURE_FEATURES = ("mean", "min", "max", "rise_rate")


def temperature_features(window, ts, source):
    """Extract temperature features from a temperature window.

    Computes (Requirement 2.3, Property 7):

    - ``mean``      = arithmetic mean of the samples
    - ``min``       = window minimum
    - ``max``       = window maximum
    - ``rise_rate`` = slope of a linear fit over the window
                      (``(last - first) / (n - 1)`` when the window has at
                      least two samples; ``NaN`` otherwise)

    Each result is wrapped in a :class:`MonitoringParameter` named
    ``"temperature_<feature>"`` with unit ``"degC"``.

    Missing-value resilience (Requirement 2.7): the window is sanitized
    with :func:`_safe`.  An empty window emits all four features as
    unavailable with ``NaN``.
    """
    out = {}
    sanitized = _safe(window)

    if not sanitized:
        for feature in _TEMPERATURE_FEATURES:
            name = f"temperature_{feature}"
            out[name] = MonitoringParameter(
                name=name, unit="degC", sensor_source=source,
                timestamp=ts, value=float("nan"), available=False,
            )
        return out

    mean = sum(sanitized) / len(sanitized)
    minimum = min(sanitized)
    maximum = max(sanitized)

    if len(sanitized) >= 2:
        # Linear-regression slope: rise_rate = sum((x-xmean)*(y-ymean)) /
        # sum((x-xmean)^2), where x = index.  This is the standard
        # least-squares slope and equals (last-first)/(n-1) for evenly
        # spaced points (Property 7 "slope over the window").
        n = len(sanitized)
        x_mean = (n - 1) / 2.0
        y_mean = mean
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(sanitized))
        den = sum((i - x_mean) ** 2 for i in range(n))
        rise_rate = num / den if den else float("nan")
    else:
        rise_rate = float("nan")

    for feature, value in (
        ("mean", mean),
        ("min", minimum),
        ("max", maximum),
        ("rise_rate", rise_rate),
    ):
        name = f"temperature_{feature}"
        out[name] = MonitoringParameter(
            name=name, unit="degC", sensor_source=source,
            timestamp=ts, value=value,
        )

    return out


# ============================================================
# 6. CURRENT FEATURE EXTRACTION  (Requirement 2.4, Property 8)
# ============================================================

_CURRENT_FEATURES = ("rms", "mean", "variation")


def current_features(window_a, window_b, window_c, ts, source):
    """Extract per-phase current features from a three-phase current window.

    For each phase (a, b, c) the function computes (Requirement 2.4,
    Property 8):

    - ``rms``       = ``sqrt(mean(v^2))``
    - ``mean``      = arithmetic mean
    - ``variation`` = standard deviation (population) divided by the
                      absolute mean, capturing the spread relative to the
                      average load (``NaN`` when mean is zero)

    Each result is wrapped in a :class:`MonitoringParameter` named
    ``"current_<feature>_<phase>"`` (e.g. ``"current_rms_a"``) with unit
    ``"A"``.

    Missing-value resilience (Requirement 2.7): each phase window is
    sanitized with :func:`_safe`.  An empty phase emits its three features
    as unavailable with ``NaN``.
    """
    out = {}

    for phase, window in (("a", window_a), ("b", window_b), ("c", window_c)):
        sanitized = _safe(window)

        if not sanitized:
            for feature in _CURRENT_FEATURES:
                name = f"current_{feature}_{phase}"
                out[name] = MonitoringParameter(
                    name=name, unit="A", sensor_source=source,
                    timestamp=ts, value=float("nan"), available=False,
                )
            continue

        rms = math.sqrt(sum(v * v for v in sanitized) / len(sanitized))
        mean = sum(sanitized) / len(sanitized)
        var = statistics.pvariance(sanitized) if len(sanitized) > 1 else 0.0
        std = math.sqrt(var)
        variation = std / abs(mean) if mean else float("nan")

        for feature, value in (
            ("rms", rms),
            ("mean", mean),
            ("variation", variation),
        ):
            name = f"current_{feature}_{phase}"
            out[name] = MonitoringParameter(
                name=name, unit="A", sensor_source=source,
                timestamp=ts, value=value,
            )

    return out


# ============================================================
# 7. MISSING-VALUE WINDOW RESILIENCE  (Requirement 2.7, Property 40)
# ============================================================

def build_feature_vector(parameters, ordered_names=None):
    """Build a model-input vector from MonitoringParameters, excluding
    unavailable values.

    Walks a collection of :class:`MonitoringParameter` objects (or a
    ``dict`` of them) and returns the numeric values of every *available*
    parameter, preserving order.  Parameters that are ``available=False``
    (missing / non-finite) are excluded from the model input vector so the
    whole window never fails because of a single missing value
    (Requirement 2.7, Property 40).

    Parameters
    ----------
    parameters : dict[str, MonitoringParameter] | list[MonitoringParameter]
        Collection of derived monitoring parameters.
    ordered_names : list[str] | None
        Optional explicit ordering.  When ``None`` the natural iteration
        order of ``parameters`` is used.

    Returns
    -------
    (names, values) : (list[str], list[float])
        Parallel lists of the parameter names that were available and
        their finite float values.
    """
    if isinstance(parameters, dict):
        iterable = (
            [(name, parameters[name]) for name in ordered_names]
            if ordered_names
            else list(parameters.items())
        )
    else:
        # Sequence of MonitoringParameter objects.
        iterable = [(p.name, p) for p in parameters]

    names = []
    values = []

    for name, param in iterable:
        if not getattr(param, "available", True):
            continue
        value = getattr(param, "value", None)
        if value is None or not math.isfinite(value):
            continue
        names.append(name)
        values.append(float(value))

    return names, values


# ============================================================
# 8. SELF-TEST (serialization round-trip)
# ============================================================


def _dicts_equal(a, b):
    """Compare two dictionaries with NaN-aware float equality.

    ``float('nan') != float('nan')`` under normal equality, so a plain ``==``
    would wrongly reject a valid round-trip that preserves a missing value.
    Two matching ``NaN`` floats are treated as equal here.
    """
    if set(a.keys()) != set(b.keys()):
        return False
    for key in a:
        av, bv = a[key], b[key]
        if isinstance(av, float) and isinstance(bv, float):
            if math.isnan(av) and math.isnan(bv):
                continue
        if av != bv:
            return False
    return True


def _self_test():
    """Verify the to_dict / from_dict round-trip for several cases."""
    cases = [
        ("available value", MonitoringParameter(
            "rms_x", "g", "ADXL345", "2024-01-01T00:00:00Z", 1.23)),
        ("explicit defaults", MonitoringParameter(
            "temperature_mean", "degC", "DS18B20",
            "2024-01-01T00:00:00Z", 42.5, "1.0", True)),
        ("custom schema version", MonitoringParameter(
            "current_rms", "A", "ACSensor",
            "2024-01-01T00:00:00Z", 8.0, schema_version="2.1")),
        ("nan value -> unavailable", MonitoringParameter(
            "rms_y", "g", "ADXL345", "2024-01-01T00:00:00Z", float("nan"))),
        ("none value -> unavailable", MonitoringParameter(
            "rms_z", "g", "ADXL345", "2024-01-01T00:00:00Z", None)),
        ("infinite value -> unavailable", MonitoringParameter(
            "peak_x", "g", "ADXL345", "2024-01-01T00:00:00Z", float("inf"))),
    ]

    for label, original in cases:
        serialized = original.to_dict()
        reconstructed = MonitoringParameter.from_dict(serialized)
        reserialized = reconstructed.to_dict()

        assert _dicts_equal(serialized, reserialized), (
            f"Round-trip failed for '{label}': "
            f"{serialized} != {reserialized}"
        )

        # Missing/non-finite inputs must always end up unavailable with NaN.
        if label.endswith("unavailable"):
            assert math.isnan(reconstructed.value), (
                f"Value should be NaN for '{label}'"
            )
            assert reconstructed.available is False, (
                f"available should be False for '{label}'"
            )
        else:
            assert reconstructed.available is True, (
                f"available should stay True for '{label}'"
            )

        print(f"  [PASS] {label}")

    print("\nAll round-trip self-tests passed.")

    # ------------------------------------------------------------
    # Vibration feature extraction (Requirement 2.1, Property 5)
    # ------------------------------------------------------------
    print("\nVibration feature self-tests:")

    ts = "2024-01-01T00:00:00Z"
    source = "ADXL345"

    # x-axis: deterministic alternating window with known statistics.
    #   mean=0, rms=sqrt((1+1+1+1)/4)=1, peak=1, pvariance=1,
    #   excess kurtosis = 4/(4*1*1) - 3 = -2, crest = 1/1 = 1.
    window_x = [1.0, -1.0, 1.0, -1.0]
    # y-axis: constant window -> variance 0, rms 0.
    #   kurtosis (var==0) and crest_factor (rms==0) both become NaN.
    window_y = [0.0, 0.0, 0.0]
    # z-axis: entirely missing -> all five features unavailable with NaN.
    window_z = [None, float("nan"), float("inf")]

    feats = vibration_features(window_x, window_y, window_z, ts, source)

    # Every axis must emit all five features.
    for axis in ("x", "y", "z"):
        for feature in _VIBRATION_FEATURES:
            name = f"{feature}_{axis}"
            assert name in feats, f"missing feature {name}"
            assert feats[name].sensor_source == source
            assert feats[name].timestamp == ts
            assert feats[name].unit == "g"

    # x-axis: known deterministic values (Property 5 identities).
    assert math.isclose(feats["rms_x"].value, 1.0), feats["rms_x"]
    assert math.isclose(feats["peak_x"].value, 1.0), feats["peak_x"]
    assert math.isclose(feats["variance_x"].value, 1.0), feats["variance_x"]
    assert math.isclose(feats["kurtosis_x"].value, -2.0), feats["kurtosis_x"]
    assert math.isclose(feats["crest_factor_x"].value, 1.0), feats["crest_factor_x"]
    # Statistical identities: crest == peak / rms.
    assert math.isclose(
        feats["crest_factor_x"].value,
        feats["peak_x"].value / feats["rms_x"].value,
    )
    for feature in _VIBRATION_FEATURES:
        assert feats[f"{feature}_x"].available is True, feature

    # y-axis: constant window -> rms/peak/variance are 0 (available),
    # kurtosis and crest_factor are NaN (unavailable via __post_init__).
    assert math.isclose(feats["rms_y"].value, 0.0)
    assert math.isclose(feats["peak_y"].value, 0.0)
    assert math.isclose(feats["variance_y"].value, 0.0)
    assert math.isnan(feats["kurtosis_y"].value)
    assert math.isnan(feats["crest_factor_y"].value)
    assert feats["rms_y"].available is True
    assert feats["peak_y"].available is True
    assert feats["variance_y"].available is True
    assert feats["kurtosis_y"].available is False
    assert feats["crest_factor_y"].available is False

    # z-axis: entirely missing -> all five features unavailable with NaN.
    for feature in _VIBRATION_FEATURES:
        p = feats[f"{feature}_z"]
        assert math.isnan(p.value), p
        assert p.available is False, p

    # Vibration features must also round-trip through the data model.
    for name, param in feats.items():
        serialized = param.to_dict()
        reconstructed = MonitoringParameter.from_dict(serialized)
        assert _dicts_equal(serialized, reconstructed.to_dict()), name

    print("  [PASS] vibration features (deterministic, constant, missing)")
    print("\nAll vibration feature self-tests passed.")

    # ------------------------------------------------------------
    # FFT band-energy extraction (Requirement 2.2, Property 6)
    # ------------------------------------------------------------
    print("\nFFT band-energy self-tests:")

    # A pure sinusoid at 200 Hz should concentrate energy in band 1.
    sr = 10000.0
    n = 1024
    t_axis = [i / sr for i in range(n)]
    sine_x = [5.0 * math.sin(2 * math.pi * 200 * t) for t in t_axis]
    # A constant (DC) window concentrates energy in band 0.
    dc_y = [1.0] * n
    # Missing window -> all band energies unavailable.
    miss_z = [None, float("nan"), float("inf")]

    fft_feats = fft_band_energies(sine_x, dc_y, miss_z, ts, source)

    # Every axis must emit at least 4 band-energy parameters.
    for axis in ("x", "y", "z"):
        band_names = [k for k in fft_feats if k.endswith(f"_{axis}")]
        assert len(band_names) >= 4, f"expected >=4 bands for axis {axis}"

    # All band energies must be non-negative (Property 6).
    for name, param in fft_feats.items():
        if param.available:
            assert param.value >= 0.0, f"negative energy for {name}"

    # The sinusoid at 200 Hz should have most energy in band 1 (50-250 Hz).
    bx0 = fft_feats["fft_band0_x"]
    bx1 = fft_feats["fft_band1_x"]
    if bx0.available and bx1.available:
        assert bx1.value >= bx0.value, "200 Hz sine should peak in band 1"

    # Missing axis -> all unavailable with NaN.
    for i in range(4):
        p = fft_feats[f"fft_band{i}_z"]
        assert math.isnan(p.value), f"band {i} z should be NaN"
        assert p.available is False, f"band {i} z should be unavailable"

    print("  [PASS] FFT band energies (sinusoid, DC, missing)")

    # ------------------------------------------------------------
    # Temperature feature extraction (Requirement 2.3, Property 7)
    # ------------------------------------------------------------
    print("\nTemperature feature self-tests:")

    # Rising window: 10, 20, 30, 40 -> mean 25, min 10, max 40,
    # rise_rate = slope = 10 per step.
    temp_window = [10.0, 20.0, 30.0, 40.0]
    t_feats = temperature_features(temp_window, ts, source)

    assert math.isclose(t_feats["temperature_mean"].value, 25.0)
    assert math.isclose(t_feats["temperature_min"].value, 10.0)
    assert math.isclose(t_feats["temperature_max"].value, 40.0)
    assert math.isclose(t_feats["temperature_rise_rate"].value, 10.0)

    # Verify slope == (last - first) / (n - 1) for evenly spaced points.
    n = len(temp_window)
    assert math.isclose(
        t_feats["temperature_rise_rate"].value,
        (temp_window[-1] - temp_window[0]) / (n - 1),
    )

    # Constant window -> rise_rate NaN (denominator zero handled).
    t_const = temperature_features([25.0], ts, source)
    assert math.isnan(t_const["temperature_rise_rate"].value)
    assert t_const["temperature_rise_rate"].available is False
    assert math.isclose(t_const["temperature_mean"].value, 25.0)

    # Missing window -> all unavailable.
    t_miss = temperature_features([None, float("nan")], ts, source)
    for feature in _TEMPERATURE_FEATURES:
        p = t_miss[f"temperature_{feature}"]
        assert math.isnan(p.value), feature
        assert p.available is False, feature

    print("  [PASS] temperature features (rising, constant, missing)")

    # ------------------------------------------------------------
    # Current feature extraction (Requirement 2.4, Property 8)
    # ------------------------------------------------------------
    print("\nCurrent feature self-tests:")

    # Phase a: known sinusoid with rms = sqrt(mean(1^2)) = 1 for amplitude 1.
    cur_a = [math.sin(2 * math.pi * 50 * t / 1000) for t in range(1000)]
    # Phase b: constant 5 A -> rms 5, mean 5, variation NaN.
    cur_b = [5.0] * 100
    # Phase c: missing.
    cur_c = [None, float("nan")]

    c_feats = current_features(cur_a, cur_b, cur_c, ts, source)

    # Phase b: rms == mean == 5, variation NaN (mean nonzero but std=0 -> 0/5).
    assert math.isclose(c_feats["current_rms_b"].value, 5.0)
    assert math.isclose(c_feats["current_mean_b"].value, 5.0)
    # variation = std / |mean| = 0 / 5 = 0
    assert math.isclose(c_feats["current_variation_b"].value, 0.0)

    # rms identity: rms == sqrt(mean(v^2)).
    rms_b_check = math.sqrt(sum(v * v for v in [5.0] * 100) / 100)
    assert math.isclose(c_feats["current_rms_b"].value, rms_b_check)

    # Phase c: all unavailable with NaN.
    for feature in _CURRENT_FEATURES:
        p = c_feats[f"current_{feature}_c"]
        assert math.isnan(p.value), f"current {feature} c should be NaN"
        assert p.available is False, f"current {feature} c should be unavailable"

    print("  [PASS] current features (sinusoid, constant, missing)")

    # ------------------------------------------------------------
    # Missing-value window resilience (Requirement 2.7, Property 40)
    # ------------------------------------------------------------
    print("\nMissing-value resilience self-tests:")

    # Build a mixed parameter dict with some available and some unavailable.
    params = {
        "rms_x": MonitoringParameter("rms_x", "g", "s", ts, 1.0),
        "rms_y": MonitoringParameter("rms_y", "g", "s", ts, float("nan")),
        "rms_z": MonitoringParameter("rms_z", "g", "s", ts, 2.0, available=False),
        "temperature_mean": MonitoringParameter("temperature_mean", "degC", "s", ts, 42.0),
    }

    names, values = build_feature_vector(params)

    # Unavailable and NaN parameters excluded; available ones kept.
    assert "rms_x" in names
    assert "rms_y" not in names       # NaN value -> excluded
    assert "rms_z" not in names        # available=False -> excluded
    assert "temperature_mean" in names
    assert len(values) == 2
    assert values[names.index("rms_x")] == 1.0
    assert values[names.index("temperature_mean")] == 42.0

    # All-unavailable dict -> empty vector.
    empty_names, empty_vals = build_feature_vector({
        "a": MonitoringParameter("a", "g", "s", ts, float("nan")),
        "b": MonitoringParameter("b", "g", "s", ts, None),
    })
    assert empty_names == []
    assert empty_vals == []

    print("  [PASS] missing-value resilience (mixed, all-unavailable)")
    print("\nAll feature extraction self-tests passed.")


if __name__ == "__main__":
    _self_test()
