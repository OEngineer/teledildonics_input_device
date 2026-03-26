"""
OSSM BLE peripheral simulator for testing ble_remote.py without real hardware.

Advertises the full OSSM GATT service profile (matching the C++ reference
firmware) and prints every command written to the PRIMARY_COMMAND
characteristic by the teledildonics device.

Usage:
    pip install bless
    python ossm_ble_sim.py

Requirements:
    - Linux: BlueZ with bluetoothd running, or macOS with CoreBluetooth.
    - bless >= 0.2.1  (https://github.com/kevincar/bless)
"""

import asyncio
import json
import logging
import time
import uuid

from bless import BlessServer, GATTCharacteristicProperties, GATTAttributePermissions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Service & characteristic UUIDs (must match nimble.h) ──────────────────────
SERVICE_UUID            = "522b443a-4f53-534d-0001-420badbabe69"
PAIRING_UUID            = "522b443a-4f53-534d-0010-420badbabe69"
COMMAND_UUID            = "522b443a-4f53-534d-1000-420badbabe69"
SPEED_KNOB_UUID         = "522b443a-4f53-534d-1010-420badbabe69"
WIFI_CONFIG_UUID        = "522b443a-4f53-534d-1020-420badbabe69"
LATENCY_COMP_UUID       = "522b443a-4f53-534d-1030-420badbabe69"
CURRENT_STATE_UUID      = "522b443a-4f53-534d-2000-420badbabe69"
PATTERNS_UUID           = "522b443a-4f53-534d-3000-420badbabe69"
PATTERN_DATA_UUID       = "522b443a-4f53-534d-3010-420badbabe69"


# Pattern names matching the OSSM firmware
PATTERNS = [
    {"name": "Simple Stroke",     "idx": 0},
    {"name": "Teasing Pounding",  "idx": 1},
    {"name": "Robo Stroke",       "idx": 2},
    {"name": "Half'n'Half",       "idx": 3},
    {"name": "Deeper",            "idx": 4},
    {"name": "Stop'n'Go",         "idx": 5},
    {"name": "Insist",            "idx": 6},
]

PATTERN_DESCRIPTIONS = [
    "Simple in and out. Sensation does nothing.",
    "Alternating strokes. Sensation controls in/out speed ratio.",
    "Robotic strokes. Sensation adjusts speed character.",
    "Alternate full and half strokes. Sensation controls speed ratio.",
    "Goes deeper with every stroke. Sensation controls step count.",
    "Stops after a series of strokes. Sensation controls the delay.",
    "Short rapid strokes. Sensation shifts position and stroke length.",
]

SESSION_ID = str(uuid.uuid4())[:8]

# ── Simulated device state ─────────────────────────────────────────────────────
_state = {
    "state":     "idle",
    "speed":     50,
    "stroke":    50,
    "sensation": 50,
    "depth":     50,
    "pattern":   0,
    "position":  0.0,
    "sessionId": SESSION_ID,
}

# ── Connection tracking ────────────────────────────────────────────────────────
_last_write: float | None = None
_central_active = False
_server: "BlessServer | None" = None
_loop: "asyncio.AbstractEventLoop | None" = None


def _state_json() -> str:
    return json.dumps({"timestamp": int(time.monotonic() * 1000), **_state})


def _push_state():
    """Update the CURRENT_STATE characteristic value and notify."""
    if _server is None:
        return
    char = _server.get_characteristic(CURRENT_STATE_UUID)
    if char is None:
        return
    char.value = bytearray(_state_json().encode())
    try:
        _server.update_value(SERVICE_UUID, CURRENT_STATE_UUID)
    except Exception as e:
        logger.debug(f"state notify error: {e}")


def _handle_command(cmd: str):
    """Parse an OSSM command string and update simulated state."""
    global _state
    print(f"[OSSM] received: {cmd!r}")

    if cmd.startswith("go:"):
        mode = cmd[3:]
        if mode in ("strokeEngine", "simplePenetration", "streaming"):
            _state["state"] = "streaming" if mode == "streaming" else "playing"
            logger.info(f"State → {_state['state']}")
        elif mode == "menu":
            _state["state"] = "idle"
            logger.info("State → idle")

    elif cmd.startswith("set:"):
        parts = cmd.split(":")
        if len(parts) == 3:
            _, field, raw = parts
            try:
                val = int(raw)
            except ValueError:
                return
            if field in _state:
                _state[field] = val
                logger.info(f"set:{field} → {val}")

    elif cmd.startswith("stream:"):
        parts = cmd.split(":")
        if len(parts) == 3:
            try:
                pos = int(parts[1])
                _state["position"] = round(pos / 100.0, 2)
            except ValueError:
                pass

    _push_state()


def on_read(characteristic, **_) -> bytearray:
    return characteristic.value or bytearray()


def on_write(_characteristic, value: bytearray):
    global _last_write, _central_active, _server, _loop
    _last_write = time.monotonic()
    if not _central_active:
        _central_active = True
        logger.info("Central connected")

    if value and _server and _loop:
        cmd = bytes(value).decode("utf-8", errors="replace").strip()
        asyncio.run_coroutine_threadsafe(_handle_async(cmd), _loop)


async def _handle_async(cmd: str):
    _handle_command(cmd)
    # Echo response on COMMAND characteristic (matches reference firmware "ok:<cmd>")
    if _server:
        char = _server.get_characteristic(COMMAND_UUID)
        if char:
            char.value = bytearray(f"ok:{cmd}".encode())
            _server.update_value(SERVICE_UUID, COMMAND_UUID)


async def watch_connections():
    """Detect disconnection by write silence (>3 s)."""
    global _last_write, _central_active
    while True:
        await asyncio.sleep(0.25)
        if _central_active and _last_write is not None:
            if time.monotonic() - _last_write > 3.0:
                _central_active = False
                _last_write = None
                logger.info("Central disconnected")


async def state_heartbeat():
    """Push a state notification every second (matches reference firmware loop)."""
    while True:
        await asyncio.sleep(1.0)
        if _central_active:
            _push_state()


async def run():
    global _server, _loop
    _loop = asyncio.get_event_loop()
    _server = BlessServer(name="OSSM", loop=_loop)
    server = _server
    server.read_request_func = on_read
    server.write_request_func = on_write

    # ── Main OSSM service ──────────────────────────────────────────────────────
    await server.add_new_service(SERVICE_UUID)

    rw   = GATTCharacteristicProperties.read | GATTCharacteristicProperties.write | GATTCharacteristicProperties.write_without_response
    rw_p = GATTAttributePermissions.readable | GATTAttributePermissions.writeable
    r_p  = GATTAttributePermissions.readable

    # Pairing (0010) — read/write
    await server.add_new_characteristic(SERVICE_UUID, PAIRING_UUID, rw, None, rw_p)

    # PRIMARY_COMMAND (1000) — read/write/notify
    await server.add_new_characteristic(
        SERVICE_UUID, COMMAND_UUID,
        GATTCharacteristicProperties.read
        | GATTCharacteristicProperties.write
        | GATTCharacteristicProperties.write_without_response
        | GATTCharacteristicProperties.notify,
        None, rw_p,
    )

    # SPEED_KNOB (1010)
    await server.add_new_characteristic(SERVICE_UUID, SPEED_KNOB_UUID, rw, None, rw_p)

    # WIFI_CONFIG (1020)
    await server.add_new_characteristic(SERVICE_UUID, WIFI_CONFIG_UUID, rw, None, rw_p)

    # LATENCY_COMP (1030)
    await server.add_new_characteristic(SERVICE_UUID, LATENCY_COMP_UUID, rw, None, rw_p)

    # CURRENT_STATE (2000) — read/notify (no cached initial value on CoreBluetooth)
    await server.add_new_characteristic(
        SERVICE_UUID, CURRENT_STATE_UUID,
        GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
        None, r_p,
    )

    # PATTERNS_LIST (3000) — read only
    patterns_json = bytearray(json.dumps(PATTERNS).encode())
    await server.add_new_characteristic(
        SERVICE_UUID, PATTERNS_UUID,
        GATTCharacteristicProperties.read,
        patterns_json, r_p,
    )

    # PATTERN_DATA (3010) — read/write
    await server.add_new_characteristic(
        SERVICE_UUID, PATTERN_DATA_UUID,
        GATTCharacteristicProperties.read | GATTCharacteristicProperties.write,
        None, rw_p,
    )

    await server.start()
    is_adv = await server.is_advertising()
    logger.info(f"OSSM BLE simulator started. Advertising: {is_adv}")
    if not is_adv:
        logger.error("Not advertising — check Bluetooth permissions for Terminal in System Settings → Privacy & Security → Bluetooth")
    logger.info("Press Ctrl-C to stop.")

    tasks = [
        asyncio.ensure_future(watch_connections()),
        asyncio.ensure_future(state_heartbeat()),
    ]
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        for t in tasks:
            t.cancel()
        await server.stop()


if __name__ == "__main__":
    asyncio.run(run())
