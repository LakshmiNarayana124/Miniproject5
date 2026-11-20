"""
INTELLIWATCH - LCD DISPLAY & RELAY MODULE INTEGRATION
Version: 1.0
Layer: IoT Actuator Peripheral (output device)

Purpose
-------
Integrate a physical LCD character display (HD44780 over I2C / PCF8574) and a
multi-channel relay module into the IntelliWatch control-signal pipeline so
that every control intent dispatched by ``EquipmentController`` is reflected
both on the LCD (human-readable status) and on the relay channels (physical
equipment actuation).

Design goals (per project constraints)
--------------------------------------
1.  NO modification to any existing file -- integration uses only the public
    surface of ``iot_layer`` (``register_device``, ``authenticate``) and the
    existing ``EdgeDevice`` protocol (``connect``/``recv_data``/
    ``send_command``). The actuator registers as an HTTP-protocol edge device
    and rides the standard ``IoTIntegrationLayer.relay()`` delivery path.
2.  NO import errors / warnings on machines without hardware libraries.
    ``smbus2`` and ``RPi.GPIO`` are imported defensively; if unavailable the
    module runs in a pure-software "shadow" mode (in-memory state only) and
    logs at DEBUG level only, so production logs stay clean.
3.  Thread-safe -- relay / LCD writes are guarded by a lock because control
    signals can arrive from multiple inference / heartbeat threads.
4.  Fail-safe default -- on init and on SHUTDOWN all channels de-energize
    (the safe state for a generic relay module).

Hardware wiring reference
-------------------------
LCD (I2C backpack, PCF8574, default address 0x27, 16x2):
    SDA -> I2C SDA, SCL -> I2C SCL, VCC -> 5V, GND -> GND
    PCF8574 bit map: b0=RS, b1=RW, b2=EN, b3=Backlight, b4-b7=D4-D7

Relay module (1/2/4/8 channel, active-low by default):
    IN0..INn -> GPIO channels, VCC -> 5V/3V3, GND -> GND
    active_low=True means the relay energizes when the GPIO pin is LOW (the
    common Arduino/Raspberry Pi relay-board behaviour). Override per board.

Integration (server wiring)
----------------------------
    from lcd_relay_module import LCDRelayEdgeAdapter, create_lcd_relay_actuator

    actuator = create_lcd_relay_actuator()                 # LCD + 4-ch relay
    adapter = LCDRelayEdgeAdapter(
        device_id="lcd-relay-01",
        actuator=actuator,
    )
    handshake = iot_layer.register_device(adapter)         # uses existing API
    iot_layer.authenticate(                                # existing API
        handshake.device_id, handshake.device_credential,
    )
    equipment_controller = EquipmentController(iot_layer=iot_layer)

Now every ``equipment_controller.dispatch(...)`` flows through
``iot_layer.relay(intent)`` -> ``adapter.send_command(intent)`` ->
``actuator.actuate(intent)`` -> relay channels + LCD update. Existing code
is untouched.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


__all__ = [
    "LCD_AVAILABLE",
    "RELAY_AVAILABLE",
    "LCDDisplay",
    "RelayModule",
    "LCDRelayActuator",
    "LCDRelayEdgeAdapter",
    "create_lcd_relay_actuator",
]


# ============================================================
# 1. HARDWARE LIBRARY IMPORTS (graceful degradation)
# ============================================================
#
# These imports are expected to fail on development machines (e.g. Windows).
# We never log a warning for their absence: the module silently falls back to
# a software shadow so importing this file is always side-effect free.

try:
    import smbus2 as _smbus  # type: ignore

    LCD_AVAILABLE = True
except Exception:  # pragma: no cover - hardware specific
    _smbus = None
    LCD_AVAILABLE = False

try:
    import RPi.GPIO as _GPIO  # type: ignore

    RELAY_AVAILABLE = True
except Exception:  # pragma: no cover - hardware specific
    _GPIO = None
    RELAY_AVAILABLE = False


# ============================================================
# 2. REUSE iot_layer DATA STRUCTURES (with safe fallbacks)
# ============================================================

try:
    from iot_layer import HandshakeResult, Ack
except Exception:  # pragma: no cover - keeps module importable standalone

    @dataclass
    class HandshakeResult:
        success: bool
        device_id: str
        capabilities: Set[str]
        protocol: str
        reason: str = ""
        device_credential: Optional[str] = None

    @dataclass
    class Ack:
        device_id: str
        intent: str
        timestamp: str
        equipment_state: str = ""


# ============================================================
# 3. CONSTANTS
# ============================================================

DEFAULT_LCD_I2C_ADDR = 0x27
DEFAULT_LCD_WIDTH = 16
DEFAULT_LCD_ROWS = 2

# Default relay channel layout (BCM pin numbers). Override via config.
DEFAULT_RELAY_PINS: List[int] = [17, 27, 22, 23]
DEFAULT_RELAY_ACTIVE_LOW = True

# Channel names mapped to positional relay indices.
DEFAULT_CHANNEL_NAMES: List[str] = ["MAIN", "DERATE", "AUX", "INDICATOR"]

# Intent -> channel energize map. De-energize = safe state for SHUTDOWN.
DEFAULT_INTENT_RELAY_MAP: Dict[str, Dict[str, bool]] = {
    "RUN": {"MAIN": True, "DERATE": False, "AUX": False, "INDICATOR": True},
    "DE_RATE": {"MAIN": True, "DERATE": True, "AUX": False, "INDICATOR": True},
    "SHUTDOWN": {"MAIN": False, "DERATE": False, "AUX": False, "INDICATOR": False},
}

# Intent -> two LCD rows (line 1 = system, line 2 = status).
DEFAULT_INTENT_LCD_MAP: Dict[str, List[str]] = {
    "RUN": ["SYSTEM : RUN", "STATUS : NORMAL"],
    "DE_RATE": ["SYSTEM : DERATE", "STATUS : WARNING"],
    "SHUTDOWN": ["SYSTEM : STOP", "STATUS : CRITICAL"],
}

VALID_INTENTS = {"RUN", "DE_RATE", "SHUTDOWN"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# 4. LCD DISPLAY  (HD44780 over I2C / PCF8574)
# ============================================================

class LCDDisplay:
    """16x2 / 20x4 character LCD driven over an I2C PCF8574 backpack.

    Falls back to an in-memory shadow when ``smbus2`` (or an I2C bus) is not
    available, so the class is fully usable on any host for testing.
    """

    # PCF8574 bit assignments.
    _RS = 0x01
    _RW = 0x00  # held low (write only)
    _EN = 0x04
    _BL = 0x08

    # DDRAM start addresses per row (0-based row index).
    _ROW_OFFSETS = {0: 0x80, 1: 0xC0, 2: 0x94, 3: 0xD4}

    def __init__(
        self,
        i2c_addr: int = DEFAULT_LCD_I2C_ADDR,
        bus_number: int = 1,
        width: int = DEFAULT_LCD_WIDTH,
        rows: int = DEFAULT_LCD_ROWS,
        backlight: bool = True,
    ):
        self.i2c_addr = i2c_addr
        self.bus_number = bus_number
        self.width = width
        self.rows = rows
        self.backlight = backlight

        self._bus = None
        self._lock = threading.Lock()
        self._shadow: List[str] = [" " * width for _ in range(rows)]
        self._connected = False

        if not LCD_AVAILABLE:
            logger.debug(
                "LCDDisplay: smbus2 unavailable -- running in software shadow "
                "mode (addr=0x%02X, %dx%d).",
                i2c_addr, width, rows,
            )
            return

        try:
            self._bus = _smbus.SMBus(bus_number)
            self._init_4bit()
            self._connected = True
            logger.info(
                "LCDDisplay connected on I2C 0x%02X (bus %d).",
                i2c_addr, bus_number,
            )
        except Exception as exc:
            self._bus = None
            logger.debug(
                "LCDDisplay: I2C init failed (%s) -- using software shadow.",
                exc,
            )

    # --------------------------------------------------------
    # low-level I2C primitives
    # --------------------------------------------------------
    def _write_i2c(self, byte: int) -> None:
        if self._bus is None:
            return
        self._bus.write_byte(self.i2c_addr, byte & 0xFF)

    def _pulse(self, data: int) -> None:
        self._write_i2c(data | self._EN)          # EN high
        time.sleep(0.0005)
        self._write_i2c(data & ~self._EN)         # EN low
        time.sleep(0.0001)

    def _send_nibble(self, nibble: int, rs: bool, long_delay: bool = False) -> None:
        rs_bit = self._RS if rs else 0x00
        bl_bit = self._BL if self.backlight else 0x00
        data = ((nibble & 0x0F) << 4) | rs_bit | bl_bit
        self._pulse(data)
        if long_delay:
            time.sleep(0.002)

    def _send(self, value: int, rs: bool = False, long_delay: bool = False) -> None:
        self._send_nibble(value >> 4, rs, long_delay)
        self._send_nibble(value & 0x0F, rs, long_delay)

    def _init_4bit(self) -> None:
        time.sleep(0.05)
        # Three 0x03 nibbles wake the controller, then 0x02 selects 4-bit mode.
        self._send_nibble(0x03, rs=False); time.sleep(0.005)
        self._send_nibble(0x03, rs=False); time.sleep(0.0001)
        self._send_nibble(0x03, rs=False); time.sleep(0.0001)
        self._send_nibble(0x02, rs=False)
        # Function set: 4-bit, 2-line, 5x8 font.
        self._send(0x28, rs=False)
        # Display off, clear, entry mode, display on (cursor hidden).
        self._send(0x08, rs=False)
        self._send(0x01, rs=False, long_delay=True)
        self._send(0x06, rs=False)
        self._send(0x0C, rs=False)

    # --------------------------------------------------------
    # public API
    # --------------------------------------------------------
    def clear(self) -> None:
        with self._lock:
            self._shadow = [" " * self.width for _ in range(self.rows)]
            self._send(0x01, rs=False, long_delay=True)

    def home(self) -> None:
        with self._lock:
            self._send(0x02, rs=False, long_delay=True)

    def set_backlight(self, on: bool) -> None:
        self.backlight = bool(on)

    def write_line(self, row: int, text: str) -> None:
        """Write ``text`` to ``row`` (0-based), padded/truncated to width."""
        if not (0 <= row < self.rows):
            return
        text = (text or "").ljust(self.width)[: self.width]

        with self._lock:
            self._shadow[row] = text
            if self._bus is None:
                return
            self._send(self._ROW_OFFSETS[row], rs=False)
            for ch in text:
                self._send(ord(ch) & 0xFF, rs=True)

    def show_status(self, line1: str, line2: str = "") -> None:
        """Convenience writer for the common two-line status pattern."""
        self.write_line(0, line1)
        if self.rows >= 2 and line2:
            self.write_line(1, line2)

    def render(self) -> List[str]:
        """Return the current logical display content (for tests/shadow)."""
        with self._lock:
            return list(self._shadow)

    def close(self) -> None:
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
        self._bus = None
        self._connected = False


# ============================================================
# 5. RELAY MODULE  (multi-channel GPIO)
# ============================================================

class RelayModule:
    """Multi-channel relay board with fail-safe de-energize defaults.

    ``active_low`` selects the board polarity. The shadow mode (no RPi.GPIO)
    keeps an in-memory channel map so behaviour is testable anywhere.
    """

    def __init__(
        self,
        pins: Optional[List[int]] = None,
        active_low: bool = DEFAULT_RELAY_ACTIVE_LOW,
        channel_names: Optional[List[str]] = None,
    ):
        self.pins = list(pins or DEFAULT_RELAY_PINS)
        self.active_low = bool(active_low)
        self.channel_names = list(channel_names or DEFAULT_CHANNEL_NAMES)

        # Extend names to match pin count if a custom pin list was supplied.
        while len(self.channel_names) < len(self.pins):
            self.channel_names.append(f"CH{len(self.channel_names)}")

        self._name_to_index = {
            name: i for i, name in enumerate(self.channel_names[: len(self.pins)])
        }
        self._lock = threading.Lock()
        # energize state per pin (False = de-energized = safe default).
        self._state: Dict[int, bool] = {pin: False for pin in self.pins}

        if not RELAY_AVAILABLE:
            logger.debug(
                "RelayModule: RPi.GPIO unavailable -- running in software "
                "shadow mode (%d channels, active_low=%s).",
                len(self.pins), self.active_low,
            )
            return

        try:
            _GPIO.setmode(_GPIO.BCM)
            _GPIO.setwarnings(False)
            for pin in self.pins:
                _GPIO.setup(pin, _GPIO.OUT, initial=_GPIO.HIGH if self.active_low else _GPIO.LOW)
            logger.info(
                "RelayModule initialised on %d GPIO channels.",
                len(self.pins),
            )
        except Exception as exc:
            logger.debug("RelayModule: GPIO setup failed (%s) -- shadow mode.", exc)

    def _write_pin(self, pin: int, energize: bool) -> None:
        if _GPIO is not None:
            if self.active_low:
                level = _GPIO.LOW if energize else _GPIO.HIGH
            else:
                level = _GPIO.HIGH if energize else _GPIO.LOW
            _GPIO.output(pin, level)
        self._state[pin] = bool(energize)

    # --------------------------------------------------------
    # public API
    # --------------------------------------------------------
    def set_channel(self, channel: Any, energize: bool) -> None:
        """Energize/de-energize a channel by index or by name."""
        idx = channel if isinstance(channel, int) else self._name_to_index.get(channel)
        if idx is None or not (0 <= idx < len(self.pins)):
            return
        with self._lock:
            self._write_pin(self.pins[idx], energize)

    def apply_state(self, channel_states: Dict[str, bool]) -> None:
        """Apply a {channel_name: energize} map atomically."""
        with self._lock:
            for name, energize in channel_states.items():
                idx = self._name_to_index.get(name)
                if idx is not None:
                    self._write_pin(self.pins[idx], energize)

    def all_off(self) -> None:
        """Fail-safe: de-energize every channel."""
        with self._lock:
            for pin in self.pins:
                self._write_pin(pin, False)

    def get_state(self) -> Dict[str, bool]:
        with self._lock:
            return {
                self.channel_names[i]: self._state[self.pins[i]]
                for i in range(len(self.pins))
            }

    def close(self) -> None:
        self.all_off()
        if _GPIO is not None:
            try:
                _GPIO.cleanup()
            except Exception:
                pass


# ============================================================
# 6. LCD + RELAY ACTUATOR  (the integration brain)
# ============================================================

class LCDRelayActuator:
    """Map a control intent to relay channel states and an LCD status screen.

    Thread-safe and fail-safe. ``actuate("SHUTDOWN")`` always de-energizes
    every relay (the safe state) and shows a critical status.
    """

    def __init__(
        self,
        lcd: Optional[LCDDisplay] = None,
        relay: Optional[RelayModule] = None,
        intent_relay_map: Optional[Dict[str, Dict[str, bool]]] = None,
        intent_lcd_map: Optional[Dict[str, List[str]]] = None,
    ):
        self.lcd = lcd or LCDDisplay()
        self.relay = relay or RelayModule()
        self.intent_relay_map = intent_relay_map or DEFAULT_INTENT_RELAY_MAP
        self.intent_lcd_map = intent_lcd_map or DEFAULT_INTENT_LCD_MAP

        self._lock = threading.Lock()
        self._last_intent: str = "RUN"
        self._last_status: str = "NORMAL"

        # Fail-safe on boot: everything off, idle screen.
        self.relay.all_off()
        self._render_idle()

    # --------------------------------------------------------
    # core actuation
    # --------------------------------------------------------
    def actuate(self, intent: str, status: Optional[str] = None) -> Dict[str, Any]:
        """Drive relays and LCD for ``intent``.

        Returns a small state record describing what was applied. Unknown
        intents are treated as SHUTDOWN (fail-safe).
        """
        intent = str(intent).upper().strip()
        if intent not in VALID_INTENTS:
            logger.warning("LCDRelayActuator: unknown intent '%s' -> SHUTDOWN.", intent)
            intent = "SHUTDOWN"

        relay_map = self.intent_relay_map.get(intent, self.intent_relay_map["SHUTDOWN"])
        lcd_lines = self.intent_lcd_map.get(intent, ["SYSTEM : ??", "STATUS : UNKNOWN"])

        with self._lock:
            self._last_intent = intent
            if status:
                self._last_status = str(status).upper()

            self.relay.apply_state(relay_map)
            self.lcd.show_status(lcd_lines[0], lcd_lines[1] if len(lcd_lines) > 1 else "")

        logger.info(
            "LCDRelayActuator actuated: intent=%s relays=%s",
            intent, self.relay.get_state(),
        )
        return {
            "intent": intent,
            "relays": self.relay.get_state(),
            "lcd": self.lcd.render(),
            "timestamp": _now_iso(),
        }

    def emergency_stop(self) -> Dict[str, Any]:
        """Unconditional fail-safe: all relays off, critical screen."""
        with self._lock:
            self.relay.all_off()
            self._last_intent = "SHUTDOWN"
            self.lcd.show_status("EMERGENCY STOP", "STATUS : CRITICAL")
        logger.warning("LCDRelayActuator EMERGENCY STOP -- all relays de-energized.")
        return {
            "intent": "SHUTDOWN",
            "relays": self.relay.get_state(),
            "lcd": self.lcd.render(),
            "timestamp": _now_iso(),
        }

    # --------------------------------------------------------
    # display helpers
    # --------------------------------------------------------
    def _render_idle(self) -> None:
        self.lcd.show_status("IntelliWatch", "READY")

    def show_message(self, line1: str, line2: str = "") -> None:
        """Push an arbitrary message to the LCD without touching relays."""
        self.lcd.show_status(line1, line2)

    # --------------------------------------------------------
    # introspection
    # --------------------------------------------------------
    @property
    def last_intent(self) -> str:
        with self._lock:
            return self._last_intent

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "last_intent": self._last_intent,
                "last_status": self._last_status,
                "relays": self.relay.get_state(),
                "lcd": self.lcd.render(),
            }

    def close(self) -> None:
        self.emergency_stop()
        self.lcd.close()
        self.relay.close()


# ============================================================
# 7. EDGE DEVICE ADAPTER  (plugs into IoTIntegrationLayer)
# ============================================================

class LCDRelayEdgeAdapter:
    """EdgeDevice-protocol adapter that registers the actuator with the IoT
    integration layer so the standard ``relay()`` delivery path drives it.

    Protocol is reported as ``"HTTP"`` so the existing ``register_device``
    validation accepts it. ``recv_data`` returns empty bytes (this is an
    actuator, not a sensor source), which keeps the HTTP poll loop silent.
    """

    protocol = "HTTP"

    def __init__(
        self,
        device_id: str,
        actuator: Optional[LCDRelayActuator] = None,
        capabilities: Optional[Set[str]] = None,
    ):
        self.device_id = device_id
        self.actuator = actuator or LCDRelayActuator()
        self.capabilities = set(capabilities or {"lcd_display", "relay_control"})

        self._credential: Optional[str] = None
        self._message_handler = None
        self._connected = False

    # --------------------------------------------------------
    # auth / handler hooks called by IoTIntegrationLayer.register_device
    # --------------------------------------------------------
    def set_device_credential(self, credential: str) -> None:
        self._credential = credential

    def set_message_handler(self, handler) -> None:
        # Provided for protocol compatibility; the actuator emits no telemetry.
        self._message_handler = handler

    # --------------------------------------------------------
    # EdgeDevice protocol
    # --------------------------------------------------------
    def connect(self) -> HandshakeResult:
        self._connected = True
        logger.info("LCDRelayEdgeAdapter '%s' connected (HTTP/local).", self.device_id)
        return HandshakeResult(
            success=True,
            device_id=self.device_id,
            capabilities=set(self.capabilities),
            protocol=self.protocol,
        )

    def recv_data(self) -> bytes:
        # Actuator only: no sensor telemetry to ingest. Returning empty keeps
        # the HTTP poll loop quiet (no spurious validation warnings).
        return b""

    def send_command(self, intent: str) -> Ack:
        timestamp = _now_iso()
        if not self._connected:
            return Ack(self.device_id, intent, timestamp, "DISCONNECTED")

        try:
            result = self.actuator.actuate(intent)
            return Ack(
                self.device_id,
                intent,
                timestamp,
                f"ACTUATED:{result['intent']}",
            )
        except Exception as exc:
            logger.exception("LCDRelayEdgeAdapter send_command failed: %s", exc)
            return Ack(self.device_id, intent, timestamp, f"ERROR: {exc}")

    def disconnect(self) -> None:
        try:
            self.actuator.emergency_stop()
        except Exception:
            pass
        self._connected = False


# ============================================================
# 8. FACTORY
# ============================================================

def create_lcd_relay_actuator(
    lcd_addr: int = DEFAULT_LCD_I2C_ADDR,
    lcd_bus: int = 1,
    lcd_width: int = DEFAULT_LCD_WIDTH,
    lcd_rows: int = DEFAULT_LCD_ROWS,
    relay_pins: Optional[List[int]] = None,
    relay_active_low: bool = DEFAULT_RELAY_ACTIVE_LOW,
    relay_channel_names: Optional[List[str]] = None,
) -> LCDRelayActuator:
    """Build a ready-to-use actuator from a single config block."""
    lcd = LCDDisplay(
        i2c_addr=lcd_addr,
        bus_number=lcd_bus,
        width=lcd_width,
        rows=lcd_rows,
    )
    relay = RelayModule(
        pins=relay_pins,
        active_low=relay_active_low,
        channel_names=relay_channel_names,
    )
    return LCDRelayActuator(lcd=lcd, relay=relay)
