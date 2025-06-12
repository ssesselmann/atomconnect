# swift_connect.py

import os
import csv
import asyncio
import time
import datetime
import struct
import swift_shared
import json

from bleak.exc import BleakError
from bleak import BleakScanner, BleakClient
from swift_shared import logging


NOTIFY_UUID  = "70bc767e-7a1a-4304-81ed-14b9af54f7bd"
RETRY_DELAY  = 1           # seconds between scan cycles


# Global to store the last count value for CPS calculation
last_counts = None
last_time = None

# ------------------------------------------------------------------
def _handle_notification(_sender: int, payload: bytearray) -> None:
    parsed = decode_swift_packet(payload)
    if not parsed:
        return
    save_latest_data(parsed)    
    store = swift_shared.latest_data
    store.setdefault("timestamps", []).append(time.strftime("%H:%M:%S"))
    store.setdefault("cps_history", []).append(parsed.get("cps", 0))
    store["data"] = parsed
    
    

# ------------------------------------------------------------------

async def scan_for_devices(timeout=1, prefix="atom"):

    found = {}

    logging.info(f"Scanning for devices...")

    def detection_callback(device, advertisement_data):
        if device.name and device.name.lower().startswith(prefix):
            if device.address not in found and advertisement_data.rssi > -70:
                found[device.address] = (device.name, device.address, advertisement_data.rssi)
                swift_shared.connection_status = f"👉 Found {device.name} (RSSI: {advertisement_data.rssi} dBm)"

    swift_shared.connection_status = f"🔍 Scanning for devices (~{int(timeout)} sec.)"

    scanner = BleakScanner(detection_callback)
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()

    if not found:
        swift_shared.connection_status = "❌ No matching devices found"
        logging.info(f"No devices found")
    else:
        swift_shared.connection_status = f"✅ Found {len(found)} device(s)"

        logging.info(f"Devices found {found}")

    return list(found.values())


# ------------------Connect to Device--------------------------------

def connect_to_device():

    swift_shared.stop_request = False

    address = swift_shared.selected_device_address

    name    = swift_shared.selected_device_name

    if not address:
        swift_shared.connection_status = "⏰ No address found — wait or scan again"
        return

    async def _connect():
        max_attempts = 10
        delay_between_attempts = 2.5  

        for attempt in range(1, max_attempts + 1):
            swift_shared.connection_status = f"🔌 Attempt {attempt}/{max_attempts} to connect to {name}"
            try:
                client = BleakClient(address)
                swift_shared.is_connected = False

                if not await client.connect(timeout=12.0): 
                    swift_shared.connection_status = f"❌ Attempt {attempt}: could not connect"
                    await asyncio.sleep(delay_between_attempts)
                    continue

                await client.start_notify(NOTIFY_UUID, _handle_notification)
                swift_shared.client = client
                swift_shared.is_connected = True
                swift_shared.connection_status = f"✅ Connected to {name}"

                # # Keep connection alive
                while not swift_shared.stop_request and swift_shared.is_connected:
                    await asyncio.sleep(1)

                # Clean disconnect
                await client.stop_notify(NOTIFY_UUID)
                await client.disconnect()
                swift_shared.is_connected = False

                if swift_shared.stop_request:
                    swift_shared.connection_status = "⏹️ Disconnected"
                    return
                else:
                    swift_shared.connection_status = "⚠️ Connection lost, retrying..."
                    await asyncio.sleep(delay_between_attempts)
                    continue

            except BleakError as e:
                swift_shared.connection_status = f"⚠️ Attempt {attempt}, error: {str(e)}"
                await asyncio.sleep(delay_between_attempts)
            except Exception as e:
                swift_shared.connection_status = f"⚠️ Attempt {attempt}, unexpected error: {str(e)}"
                await asyncio.sleep(delay_between_attempts)

        swift_shared.connection_status = f"❌ Failed after {max_attempts} attempts."
        swift_shared.is_connected = False

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_connect())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_connect())
# ------------------------------------------------------------------

def decode_swift_packet(data: bytes):
    global last_counts, last_time

    if len(data) != 13:
        print("⚠️ Invalid packet length")
        return None

    now = datetime.datetime.now()
    now_str = now.strftime("%H:%M:%S")

    status = data[0]
    dose = struct.unpack('<f', data[1:5])[0]
    dose_rate = struct.unpack('<f', data[5:9])[0]
    counts_2s = int.from_bytes(data[9:11], byteorder='little', signed=False)
    battery = data[11]
    temperature = data[12] if data[12] < 128 else data[12] - 256

    cps = counts_2s / 2.0
    total_counts = last_counts + counts_2s if last_counts is not None else counts_2s
    last_counts = total_counts
    last_time = now


    return {
        "time": now_str,
        "counts": total_counts,
        "cps": cps,
        "dose": dose,
        "rate": dose_rate,
        "battery": battery,
        "temp": temperature,
    }


# ------------------------------------------------------------------
def save_latest_data(data):
    latest_path = swift_shared.DATA_DIR / "latest_data.json"
    recording_path = swift_shared.DATA_DIR / "recording.json"

    # Save single latest snapshot
    with open(latest_path, "w") as f:
        json.dump(data, f, indent=2)

    # Append to recording log
    if not recording_path.exists():
        with open(recording_path, "w") as f:
            json.dump([data], f, indent=2)
    else:
        with open(recording_path, "r+", encoding="utf-8") as f:
            entries = json.load(f)
            entries.append(data)
            f.seek(0)
            json.dump(entries, f, indent=2)
            f.truncate()




# Make latest_data importable
__all__ = ['decode_swift_packet', 'latest_data']
