"""
OSSM BLE peripheral simulator for testing ble_remote.py without real hardware.

Advertises the standard OSSM GATT service and prints every command written
to the PRIMARY_COMMAND characteristic by the teledildonics device.

Usage:
    pip install bless
    python ossm_ble_sim.py

Requirements:
    - Linux: BlueZ with bluetoothd running, or macOS with CoreBluetooth.
    - bless >= 0.2.1  (https://github.com/kevincar/bless)
"""

import asyncio
import logging
import time
from bless import BlessServer, GATTCharacteristicProperties, GATTAttributePermissions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_UUID = "522b443a-4f53-534d-0001-420badbabe69"
COMMAND_UUID = "522b443a-4f53-534d-1000-420badbabe69"

# Silence timeout: if no write arrives within this many seconds after the last
# one, we treat it as a disconnection.  Must be comfortably longer than the
# STREAM_INTERVAL_MS (200 ms) used by ble_remote.py.
DISCONNECT_TIMEOUT = 3.0

_last_write: float | None = None
_central_active = False
_server: "BlessServer | None" = None
_loop: "asyncio.AbstractEventLoop | None" = None


def on_write(_characteristic, value: bytearray):
    global _last_write, _central_active, _server, _loop
    _last_write = time.monotonic()
    if not _central_active:
        _central_active = True
        logger.info("Central connected")
    if value and _server and _loop:
        cmd = bytes(value).decode("utf-8", errors="replace")
        print(f"[OSSM] received: {cmd!r}")
        asyncio.run_coroutine_threadsafe(_respond(cmd), _loop)


async def _respond(cmd: str):
    response = bytearray(f"ok:{cmd}".encode())
    char = _server.get_characteristic(COMMAND_UUID)
    char.value = response
    _server.update_value(SERVICE_UUID, COMMAND_UUID)


async def watch_connections():
    """Detect disconnection by write silence."""
    global _last_write, _central_active
    while True:
        await asyncio.sleep(0.25)
        if _central_active and _last_write is not None:
            if time.monotonic() - _last_write > DISCONNECT_TIMEOUT:
                _central_active = False
                _last_write = None
                logger.info("Central disconnected")


async def run():
    global _server, _loop
    _loop = asyncio.get_event_loop()
    _server = BlessServer(name="OSSM", loop=_loop)
    server = _server
    server.read_request_func = None
    server.write_request_func = on_write

    await server.add_new_service(SERVICE_UUID)

    # PRIMARY_COMMAND — writable and notifiable
    await server.add_new_characteristic(
        SERVICE_UUID,
        COMMAND_UUID,
        GATTCharacteristicProperties.write
        | GATTCharacteristicProperties.write_without_response
        | GATTCharacteristicProperties.notify,
        None,
        GATTAttributePermissions.writeable,
    )

    await server.start()
    logger.info("OSSM BLE simulator running. Waiting for teledildonics device to connect...")
    logger.info("Press Ctrl-C to stop.")

    watcher = asyncio.ensure_future(watch_connections())
    try:
        await asyncio.Event().wait()  # run until cancelled
    except asyncio.CancelledError:
        pass
    finally:
        watcher.cancel()
        await server.stop()


if __name__ == "__main__":
    asyncio.run(run())
