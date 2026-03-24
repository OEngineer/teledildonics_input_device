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
from bless import BlessServer, GATTCharacteristicProperties, GATTAttributePermissions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_UUID = "522b443a-4f53-534d-0001-420badbabe69"
COMMAND_UUID = "522b443a-4f53-534d-1000-420badbabe69"


def on_write(_characteristic, value: bytearray):
    if value:
        print(f"[OSSM] received: {bytes(value).decode('utf-8', errors='replace')!r}")


async def run():
    server = BlessServer(name="OSSM", loop=asyncio.get_event_loop())
    server.read_request_func = None
    server.write_request_func = on_write

    await server.add_new_service(SERVICE_UUID)

    # PRIMARY_COMMAND — writable by central
    await server.add_new_characteristic(
        SERVICE_UUID,
        COMMAND_UUID,
        GATTCharacteristicProperties.write | GATTCharacteristicProperties.write_without_response,
        None,
        GATTAttributePermissions.writeable,
    )

    await server.start()
    logger.info("OSSM BLE simulator running. Waiting for teledildonics device to connect...")
    logger.info("Press Ctrl-C to stop.")

    try:
        await asyncio.Event().wait()  # run until cancelled
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(run())
