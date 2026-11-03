"""
INTELLIWATCH - EQUIPMENT CONTROLLER
Version: 1.0

Purpose:
- Map a System_Status to the corresponding Control_Signal intent
  (Requirement 3.1/3.3/3.4): CRITICAL -> SHUTDOWN, WARNING -> DE_RATE,
  NORMAL -> RUN.
- Dispatch control signals in-process so the <=500 ms SHUTDOWN budget is
  achievable (Requirement 3.5).
- SHUTDOWN carries the highest numeric priority and dominates simultaneous
  requests (Requirement 3.6, Property 13).
- Restore operation on CRITICAL -> NORMAL transition (Requirement 3.2,
  Property 12).
- Retry transient delivery failures (Requirement 11.2, Property 29) and latch
  CRITICAL SHUTDOWN until status returns to NORMAL (Requirement 11.3,
  Property 30).
- Raise a fail-safe alert within 1 s when the control channel is unavailable at
  CRITICAL detection (Requirement 11.4).
- Enforce an authorization gate reusing role-based access (Requirement 13.3,
  Property 37) and record immutable audit entries per dispatch
  (Requirement 13.1, Property 35).
- Persist equipment acknowledgements (Requirement 3.8, Property 14) and raise
  an actuation-failure alert on acknowledgement timeout (Requirement 3.9).

Dependencies:
- ``database`` for persistence (``save_control_ack``, ``record_audit_entry``,
  control_signals inserts).
- ``iot_layer`` for the optional relay to connected devices.
"""

import json
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import database

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

STATUS_TO_INTENT = {
    "CRITICAL": "SHUTDOWN",
    "WARNING": "DE_RATE",
    "NORMAL": "RUN",
}

# Numeric priorities: SHUTDOWN is highest (Req 3.6, Property 13).
INTENT_PRIORITY = {
    "SHUTDOWN": 3,
    "DE_RATE": 2,
    "RUN": 1,
}

PRIORITY_SHUTDOWN = INTENT_PRIORITY["SHUTDOWN"]
PRIORITY_DE_RATE = INTENT_PRIORITY["DE_RATE"]
PRIORITY_RUN = INTENT_PRIORITY["RUN"]

# Roles authorized to issue SHUTDOWN / DE_RATE (Req 13.3).
ACTUATION_ROLES = frozenset({"ADMIN", "MAINTENANCE_ENGINEER"})

# Default delivery retry parameters (Req 11.2).
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_S = 0.05

# Default acknowledgement timeout in seconds (Req 3.9).
DEFAULT_ACK_TIMEOUT_S = 5.0

# Fail-safe alert budget in seconds (Req 11.4).
FAIL_SAFE_BUDGET_S = 1.0


# ============================================================
# AUTHORIZATION  (Requirement 13.3, Property 37)
# ============================================================

class PermissionDenied(Exception):
    """Raised when an unauthorized session attempts a control dispatch."""


def authorize(session: Optional[Dict[str, Any]], allowed_roles: Optional[Set[str]] = None) -> bool:
    """Check whether ``session`` holds an authorized role (Req 13.3).

    ``session`` is a dict carrying at least ``role`` (and optionally
    ``username`` / ``id``).  When ``allowed_roles`` is ``None`` the
    ``ACTUATION_ROLES`` set is used (ADMIN and MAINTENANCE_ENGINEER).

    Returns ``True`` when authorized, ``False`` otherwise.
    """
    if not session or not isinstance(session, dict):
        return False
    roles = allowed_roles or ACTUATION_ROLES
    return session.get("role") in roles


# ============================================================
# EQUIPMENT CONTROLLER
# ============================================================

class EquipmentController:
    """Status-to-control-signal dispatch bus (Requirements 3, 11, 13).

    The controller runs in-process so the <=500 ms SHUTDOWN latency budget
    (Req 3.5) and the <=200 ms status budget (Req 11.1) are achievable without
    IPC overhead.  It latches CRITICAL SHUTDOWN (Req 11.3), retries transient
    delivery failures (Req 11.2), and records immutable audit entries
    (Req 13.1).
    """

    def __init__(
        self,
        iot_layer: Optional[Any] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay_s: float = DEFAULT_RETRY_DELAY_S,
        ack_timeout_s: float = DEFAULT_ACK_TIMEOUT_S,
    ):
        self.iot_layer = iot_layer
        self.max_retries = max_retries
        self.retry_delay_s = retry_delay_s
        self.ack_timeout_s = ack_timeout_s

        self._lock = threading.Lock()
        # The currently latched status; while CRITICAL, SHUTDOWN is held
        # and no downgrade is permitted (Req 11.3, Property 30).
        self._latched_status = "NORMAL"
        self._latched_intent = "RUN"

        # Listeners notified on actuation-failure / fail-safe alerts.
        self._alert_listeners: List[Any] = []
        # Track pending dispatches awaiting acknowledgement.
        self._pending_acks: Dict[int, float] = {}

    # --------------------------------------------------------
    # ALERT SUBSCRIPTION
    # --------------------------------------------------------
    def add_alert_listener(self, listener):
        """Register a callable notified on actuation-failure / fail-safe alerts."""
        self._alert_listeners.append(listener)

    def _raise_alert(self, alert_type: str, detail: Dict[str, Any]):
        """Notify all alert listeners of an actuation/fail-safe event."""
        alert = {
            "type": alert_type,
            "timestamp": _now_iso(),
            "detail": detail,
        }
        for listener in self._alert_listeners:
            try:
                listener(alert)
            except Exception as exc:
                logger.warning("Alert listener raised: %s", exc)

    # --------------------------------------------------------
    # STATUS HANDLER  (Requirement 3.1/3.3/3.4)
    # --------------------------------------------------------
    def on_status(self, status: str, trace: Optional[Any] = None, session: Optional[Dict] = None):
        """React to a new System_Status by dispatching the mapped intent.

        CRITICAL -> SHUTDOWN (Req 3.1), WARNING -> DE_RATE (Req 3.3),
        NORMAL -> RUN (Req 3.4).  On CRITICAL -> NORMAL transition a RUN signal
        restores operation (Req 3.2, Property 12).
        """
        status = status.upper() if status else "NORMAL"
        intent = STATUS_TO_INTENT.get(status, "RUN")

        with self._lock:
            prev_status = self._latched_status

            # CRITICAL latching: while CRITICAL, never downgrade (Req 11.3).
            if prev_status == "CRITICAL" and status not in ("CRITICAL",):
                # Only allow the latch to release when status returns to
                # NORMAL (Req 11.3).  WARNING is refused while latched.
                if status != "NORMAL":
                    logger.info(
                        "CRITICAL latch active; refusing downgrade to %s (%s)",
                        status, intent,
                    )
                    return self._latched_intent

        # Dispatch the mapped intent.
        return self.dispatch(
            intent=intent,
            status=status,
            trace=trace,
            session=session,
            priority=INTENT_PRIORITY.get(intent, PRIORITY_RUN),
        )

    # --------------------------------------------------------
    # DISPATCH  (Requirements 3.5, 11.2, 13.1, 13.3)
    # --------------------------------------------------------
    def dispatch(
        self,
        intent: str,
        status: str = "NORMAL",
        trace: Optional[Any] = None,
        session: Optional[Dict] = None,
        priority: Optional[int] = None,
        target_equipment: Optional[str] = None,
        deadline_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Dispatch a control signal.

        Enforces the authorization gate (Req 13.3), records an immutable audit
        entry (Req 13.1), and sends with retry (Req 11.2).  SHUTDOWN carries the
        highest priority and is dispatched within 500 ms when in-process
        (Req 3.5).
        """
        intent = intent.upper()
        status = status.upper() if status else "NORMAL"
        priority = priority if priority is not None else INTENT_PRIORITY.get(intent, PRIORITY_RUN)
        target_equipment = target_equipment or "default"

        # --- Authorization gate (Req 13.3, Property 37) ---
        if intent in ("SHUTDOWN", "DE_RATE") and not authorize(session):
            actor = (session or {}).get("username", "unknown")
            self._record_rejected(intent, status, actor, target_equipment)
            self._record_audit(
                category="rejected_attempt",
                actor=actor,
                target=target_equipment,
                detail={"intent": intent, "status": status, "reason": "unauthorized"},
            )
            raise PermissionDenied(
                f"Session not authorized to issue {intent}"
            )

        # --- Update latched state ---
        with self._lock:
            self._latched_status = status
            self._latched_intent = intent

        # --- Record the control signal row ---
        triggering_params = _trace_params(trace)
        model_version = _trace_model_version(trace)
        control_id = self._save_control_signal(
            intent=intent,
            status=status,
            priority=priority,
            target_equipment=target_equipment,
            triggering_params=triggering_params,
            model_version=model_version,
        )

        # --- Record immutable audit entry (Req 13.1, Property 35) ---
        actor = (session or {}).get("username", "system")
        self._record_audit(
            category="control_dispatch",
            actor=actor,
            target=target_equipment,
            detail={
                "intent": intent,
                "status": status,
                "priority": priority,
                "control_signal_id": control_id,
                "triggering_params": triggering_params,
            },
        )

        # --- Send with retry (Req 11.2, Property 29) ---
        deadline = deadline_ms or (500 if intent == "SHUTDOWN" else None)
        delivered = self._send_with_retry(
            intent=intent,
            priority=priority,
            control_id=control_id,
            deadline_ms=deadline,
        )

        if not delivered and intent == "SHUTDOWN":
            # Fail-safe alert within 1 s (Req 11.4).
            self._raise_alert("fail_safe", {
                "intent": intent,
                "control_signal_id": control_id,
                "reason": "delivery failed after retries",
            })

        return {
            "control_signal_id": control_id,
            "intent": intent,
            "status": status,
            "priority": priority,
            "delivered": delivered,
        }

    # --------------------------------------------------------
    # SEND WITH RETRY  (Requirement 11.2, Property 29)
    # --------------------------------------------------------
    def _send_with_retry(
        self,
        intent: str,
        priority: int,
        control_id: int,
        deadline_ms: Optional[int] = None,
    ) -> bool:
        """Attempt to deliver the intent, retrying on transient failure (Req 11.2).

        Returns ``True`` on success, ``False`` if all retries fail.  When a
        deadline is set (e.g. 500 ms for SHUTDOWN) the retry loop respects it
        so the latency budget is honored (Req 3.5).
        """
        deadline_s = (deadline_ms / 1000.0) if deadline_ms else None
        start = time.monotonic()

        for attempt in range(1, self.max_retries + 1):
            # Respect deadline.
            if deadline_s and (time.monotonic() - start) >= deadline_s:
                break

            try:
                if self.iot_layer is not None:
                    self.iot_layer.relay(intent)
                return True
            except Exception as exc:
                logger.warning(
                    "Control signal delivery attempt %d/%d failed: %s",
                    attempt, self.max_retries, exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay_s)

        return False

    # --------------------------------------------------------
    # ACKNOWLEDGEMENT  (Requirement 3.8, Property 14)
    # --------------------------------------------------------
    def on_ack(
        self,
        control_signal_id: int,
        equipment_state: str = "",
    ) -> bool:
        """Record an equipment acknowledgement (Req 3.8, Property 14).

        Persists the acknowledgement timestamp and resulting equipment state,
        then removes the dispatch from the pending set.
        """
        ack_ts = _now_iso()
        saved = database.save_control_ack(
            control_signal_id=control_signal_id,
            ack_timestamp=ack_ts,
            resulting_equipment_state=equipment_state,
        )
        with self._lock:
            self._pending_acks.pop(control_signal_id, None)
        if saved:
            self._record_audit(
                category="control_ack",
                actor="equipment",
                target=str(control_signal_id),
                detail={
                    "control_signal_id": control_signal_id,
                    "ack_timestamp": ack_ts,
                    "equipment_state": equipment_state,
                },
            )
        return saved

    def check_ack_timeouts(self):
        """Raise actuation-failure alerts for unacknowledged SHUTDOWNs (Req 3.9)."""
        now = time.monotonic()
        with self._lock:
            expired = [
                cid for cid, t in self._pending_acks.items()
                if (now - t) >= self.ack_timeout_s
            ]
        for cid in expired:
            self._raise_alert("actuation_failure", {
                "control_signal_id": cid,
                "reason": "no acknowledgement within timeout",
            })
            with self._lock:
                self._pending_acks.pop(cid, None)

    # --------------------------------------------------------
    # PRIORITY DOMINANCE  (Requirement 3.6, Property 13)
    # --------------------------------------------------------
    def select_dominant(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the highest-priority control signal from simultaneous requests.

        SHUTDOWN dominates DE_RATE and RUN (Req 3.6, Property 13).
        """
        if not requests:
            return {"intent": "RUN", "status": "NORMAL", "priority": PRIORITY_RUN}
        return max(
            requests,
            key=lambda r: INTENT_PRIORITY.get(r.get("intent", "RUN"), 0),
        )

    # --------------------------------------------------------
    # PERSISTENCE HELPERS
    # --------------------------------------------------------
    def _save_control_signal(
        self,
        intent: str,
        status: str,
        priority: int,
        target_equipment: str,
        triggering_params: Dict,
        model_version: Optional[str],
    ) -> int:
        """Insert a control_signals row and return its id."""
        conn = database.get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO control_signals (
                    timestamp, intent, system_status,
                    target_equipment, priority,
                    triggering_params_json, model_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                _now_iso(),
                intent,
                status,
                target_equipment,
                priority,
                json.dumps(triggering_params, default=str),
                model_version,
            ))
            conn.commit()
            control_id = cursor.lastrowid
            # Track for ack-timeout checking.
            with self._lock:
                self._pending_acks[control_id] = time.monotonic()
            return control_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _record_audit(self, category: str, detail: Dict, actor: str = None, target: str = None):
        """Record an immutable audit entry via ``database.record_audit_entry``."""
        try:
            database.record_audit_entry(
                category=category,
                detail_json=json.dumps(detail, default=str),
                actor=actor,
                target=target,
            )
        except Exception as exc:
            logger.warning("Failed to record audit entry (%s): %s", category, exc)

    def _record_rejected(self, intent: str, status: str, actor: str, target: str):
        """Log a rejected dispatch attempt (Req 13.5)."""
        logger.warning(
            "Rejected %s dispatch by '%s' for '%s' (status=%s)",
            intent, actor, target, status,
        )

    # --------------------------------------------------------
    # LATCH INSPECTION (for testing)
    # --------------------------------------------------------
    @property
    def latched_status(self) -> str:
        with self._lock:
            return self._latched_status

    @property
    def latched_intent(self) -> str:
        with self._lock:
            return self._latched_intent


# ============================================================
# HELPERS
# ============================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace_params(trace: Any) -> Dict[str, Any]:
    """Extract the triggering Monitoring_Parameter values from a DetectionTrace."""
    if trace is None:
        return {}
    inputs = getattr(trace, "inputs", None)
    if inputs is None:
        return {}
    if isinstance(inputs, dict):
        return inputs
    return {"inputs": str(inputs)}


def _trace_model_version(trace: Any) -> Optional[str]:
    """Extract the model version from a DetectionTrace."""
    if trace is None:
        return None
    return getattr(trace, "model_version", None)
