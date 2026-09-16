"""
SEAFLOOR INTELLIGENCE
REAL HARDWARE READER

Purpose:
    Communicate with Arduino / ESP-class boards through USB serial.

The firmware should send JSON packets like:

{
    "depth": 12.4,
    "temperature": 18.2,
    "magnetic": 53.7,
    "em": 1.82,
    "lat": 10.123456,
    "lon": 76.123456,
    "satellites": 8,
    "hardware": true
}

Important:
    - No simulated sensor values are created here.
    - Missing sensors are reported as NOT AVAILABLE.
    - A serial connection is NOT considered valid hardware
      until a valid hardware packet is received.
"""

import json
import threading
import time


# ============================================================
# SERIAL LIBRARY
# ============================================================

try:

    import serial
    import serial.tools.list_ports

    SERIAL_AVAILABLE = True

except ImportError:

    serial = None

    SERIAL_AVAILABLE = False


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_PORT = "COM5"

DEFAULT_BAUDRATE = 115200

READ_TIMEOUT = 1.0

DATA_STALE_TIME = 5.0

EXPECTED_PROBE = "PROBE-01"


# ============================================================
# REQUIRED SENSOR DEFINITIONS
# ============================================================

REQUIRED_SENSORS = [

    "temperature",

    "magnetic",

    "em",

    "depth",

    "gps",

]


# ============================================================
# GLOBAL HARDWARE STATE
# ============================================================

_serial_connection = None

_reader_thread = None

_reader_running = False

_state_lock = threading.Lock()

_last_connect_attempt = 0.0

_CONNECT_RETRY_INTERVAL = 5.0


_state = {

    # --------------------------------------------------------
    # Connection
    # --------------------------------------------------------

    "connected": False,

    "hardware": False,

    "port": None,

    "baudrate": DEFAULT_BAUDRATE,

    "error": None,


    # --------------------------------------------------------
    # Identification
    # --------------------------------------------------------

    "probe": "PROBE-01",


    # --------------------------------------------------------
    # Latest sensor data
    # --------------------------------------------------------

    "depth": None,

    "temperature": None,

    "magnetic": None,

    "em": None,

    "inductive": False,


    # --------------------------------------------------------
    # GPS
    # --------------------------------------------------------

    "lat": None,

    "lon": None,

    "satellites": 0,


    # --------------------------------------------------------
    # Position
    # --------------------------------------------------------

    "x": 0.0,

    "y": 0.0,


    # --------------------------------------------------------
    # Data state
    # --------------------------------------------------------

    "last_update": None,

    "last_packet": None,

    "fresh_data": False,

}


# ============================================================
# SENSOR AVAILABILITY
# ============================================================

def _sensor_available(value):

    """
    A sensor is available only when it produced a usable value.
    """

    if value is None:

        return False

    try:

        value = float(value)

        return value >= 0

    except (
        TypeError,
        ValueError,
    ):

        return False


def _get_sensor_status():

    """
    Build sensor availability information for the dashboard.
    """

    with _state_lock:

        temperature = _state["temperature"]

        magnetic = _state["magnetic"]

        em = _state["em"]

        depth = _state["depth"]

        lat = _state["lat"]

        lon = _state["lon"]


    temperature_ok = _sensor_available(
        temperature
    )

    magnetic_ok = _sensor_available(
        magnetic
    )

    em_ok = _sensor_available(
        em
    )

    depth_ok = _sensor_available(
        depth
    )

    gps_ok = (

        lat is not None

        and

        lon is not None

    )


    status = {

        "temperature": (

            "AVAILABLE"

            if temperature_ok

            else

            "NOT AVAILABLE"

        ),

        "magnetic": (

            "AVAILABLE"

            if magnetic_ok

            else

            "NOT AVAILABLE"

        ),

        "em": (

            "AVAILABLE"

            if em_ok

            else

            "NOT AVAILABLE"

        ),

        "depth": (

            "AVAILABLE"

            if depth_ok

            else

            "NOT AVAILABLE"

        ),

        "gps": (

            "AVAILABLE"

            if gps_ok

            else

            "NOT AVAILABLE"

        ),

    }


    available = [

        name

        for name, value in status.items()

        if value == "AVAILABLE"

    ]


    unavailable = [

        name

        for name, value in status.items()

        if value == "NOT AVAILABLE"

    ]


    return {

        "status": status,

        "available_sensors": available,

        "unavailable_sensors": unavailable,

        "all_required_sensors_available": (

            len(unavailable) == 0

        ),

    }


# ============================================================
# UPDATE HARDWARE STATE
# ============================================================

def _update_from_packet(packet):

    """
    Store one valid hardware JSON packet.
    """

    if not isinstance(
        packet,
        dict
    ):

        return False


    # --------------------------------------------------------
    # Verify that this is the expected ESP32 telemetry packet.  Opening a
    # serial port (or parsing an unrelated JSON message) must never make the
    # backend claim that real hardware is available.
    # --------------------------------------------------------

    hardware_flag = packet.get(
        "hardware",
        False
    )

    if hardware_flag is not True:

        return False

    if packet.get("probe") != EXPECTED_PROBE:

        return False


    with _state_lock:

        # ----------------------------------------------------
        # Sensor values
        # ----------------------------------------------------

        if "depth" in packet:

            _state["depth"] = (
                _safe_float(
                    packet.get("depth")
                )
            )


        if "temperature" in packet:

            _state["temperature"] = (
                _safe_float(
                    packet.get("temperature")
                )
            )


        if "magnetic" in packet:

            _state["magnetic"] = (
                _safe_float(
                    packet.get("magnetic")
                )
            )


        if "em" in packet:

            _state["em"] = (
                _safe_float(
                    packet.get("em")
                )
            )


        if "inductive" in packet:

            val = packet.get("inductive")

            _state["inductive"] = (
                val is True or str(val).lower() == "true" or val == 1
            )


        # ----------------------------------------------------
        # GPS
        # ----------------------------------------------------

        if "lat" in packet:

            _state["lat"] = (
                _safe_float(
                    packet.get("lat")
                )
            )


        if "lon" in packet:

            _state["lon"] = (
                _safe_float(
                    packet.get("lon")
                )
            )


        if "satellites" in packet:

            _state["satellites"] = (
                _safe_int(
                    packet.get("satellites")
                )
            )


        # ----------------------------------------------------
        # Optional position
        # ----------------------------------------------------

        if "x" in packet:

            _state["x"] = (
                _safe_float(
                    packet.get("x")
                )
            )


        if "y" in packet:

            _state["y"] = (
                _safe_float(
                    packet.get("y")
                )
            )


        # ----------------------------------------------------
        # Probe
        # ----------------------------------------------------

        if packet.get("probe"):

            _state["probe"] = str(
                packet.get("probe")
            )


        # ----------------------------------------------------
        # Packet information
        # ----------------------------------------------------

        _state["last_packet"] = packet

        _state["last_update"] = time.time()

        _state["fresh_data"] = True

        _state["hardware"] = True

        _state["error"] = None

    # Persist every validated ESP32 packet at reception time.  This is outside
    # the lock so a slow SQLite write never delays serial acquisition.
    try:
        try:
            from .database import save_hardware_packet
        except ImportError:
            from database import save_hardware_packet
        save_hardware_packet(packet)
    except Exception:
        # Telemetry remains usable if storage is temporarily unavailable.
        pass


    return True


# ============================================================
# SAFE CONVERSIONS
# ============================================================

def _safe_float(value):

    try:

        if value is None:

            return None

        number = float(value)

        # Handle invalid JSON-style sensor values

        if number != number:

            return None

        return number

    except (
        TypeError,
        ValueError,
    ):

        return None


def _safe_int(value):

    try:

        return int(
            float(value)
        )

    except (
        TypeError,
        ValueError,
    ):

        return 0


# ============================================================
# SERIAL READER
# ============================================================

def _reader_loop():

    global _reader_running

    # Serial is a byte stream: readline() can return a fragment at timeout or
    # a debug line followed by JSON.  Retain incomplete objects and extract
    # complete JSON dictionaries as bytes arrive.
    buffer = ""
    decoder = json.JSONDecoder()

    while _reader_running:

        try:

            if (

                _serial_connection is None

                or

                not _serial_connection.is_open

            ):


                with _state_lock:
                    _state["connected"] = False
                    _state["hardware"] = False
                    _state["fresh_data"] = False

                time.sleep(0.2)

                continue


            raw = _serial_connection.read(256)


            if not raw:

                continue


            try:

                chunk = raw.decode(
                    "utf-8",
                    errors="ignore"
                )

            except Exception:

                continue


            if not chunk:

                continue

            buffer += chunk

            # Discard boot/debug output before the next possible object.
            while buffer:
                start = buffer.find("{")
                if start < 0:
                    buffer = ""
                    break
                if start:
                    buffer = buffer[start:]

                try:
                    packet, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    # It may be incomplete.  Retain it unless it is clearly
                    # malformed and another object has already begun.
                    next_start = buffer.find("{", 1)
                    if next_start > 0:
                        buffer = buffer[next_start:]
                        continue
                    break

                buffer = buffer[end:].lstrip()
                if isinstance(packet, dict):
                    _update_from_packet(packet)

            # Bound memory if a device emits an unterminated line forever.
            if len(buffer) > 8192:
                buffer = buffer[buffer.rfind("{"):]


        except Exception as exc:

            with _state_lock:

                _state["error"] = str(
                    exc
                )

                _state["fresh_data"] = False

                _state["connected"] = False

                _state["hardware"] = False

            time.sleep(0.5)


# ============================================================
# CONNECT HARDWARE
# ============================================================

def connect_hardware(
    port=DEFAULT_PORT,
    baudrate=DEFAULT_BAUDRATE,
):

    global _serial_connection

    global _reader_thread

    global _reader_running


    # --------------------------------------------------------
    # Check pyserial
    # --------------------------------------------------------

    if not SERIAL_AVAILABLE:

        with _state_lock:

            _state["error"] = (
                "pyserial is not installed."
            )

        return False


    # --------------------------------------------------------
    # Disconnect previous connection
    # --------------------------------------------------------

    disconnect_hardware()


    try:

        connection = serial.Serial(

            port=port,

            baudrate=baudrate,

            timeout=READ_TIMEOUT,

        )


        time.sleep(1.0)


        _serial_connection = connection


        with _state_lock:

            _state["connected"] = True

            _state["hardware"] = False

            _state["port"] = port

            _state["baudrate"] = baudrate

            _state["error"] = None

            _state["fresh_data"] = False


        # ----------------------------------------------------
        # Start reader thread
        # ----------------------------------------------------

        _reader_running = True


        _reader_thread = threading.Thread(

            target=_reader_loop,

            daemon=True,

        )


        _reader_thread.start()


        return True


    except Exception as exc:

        with _state_lock:

            _state["connected"] = False

            _state["hardware"] = False

            _state["port"] = None

            _state["error"] = str(
                exc
            )


        _serial_connection = None

        return False


# ============================================================
# DISCONNECT HARDWARE
# ============================================================

def disconnect_hardware():

    global _serial_connection

    global _reader_running


    _reader_running = False


    connection = _serial_connection


    _serial_connection = None


    if connection is not None:

        try:

            if connection.is_open:

                connection.close()

        except Exception:

            pass


    with _state_lock:

        _state["connected"] = False

        _state["hardware"] = False

        _state["fresh_data"] = False

        _state["port"] = None

        _state["last_update"] = None


    return True


# ============================================================
# GET HARDWARE READING
# ============================================================

def get_hardware_reading():

    global _last_connect_attempt

    now = time.time()

    with _state_lock:
        needs_connection = not _state["connected"]

    if (
        needs_connection
        and now - _last_connect_attempt >= _CONNECT_RETRY_INTERVAL
    ):
        _last_connect_attempt = now
        connect_hardware()

    sensor_info = _get_sensor_status()


    with _state_lock:

        last_update = (
            _state["last_update"]
        )

        now = time.time()


        # ----------------------------------------------------
        # Determine whether data is fresh
        # ----------------------------------------------------

        if last_update is None:

            fresh = False

        else:

            fresh = (
                now - last_update
                <= DATA_STALE_TIME
            )


        _state["fresh_data"] = fresh

        # A historical packet is not live hardware.  Keep the raw port state
        # separately, but expose this effective status to API selection.
        hardware_available = (
            _state["connected"]
            and _state["hardware"]
            and fresh
        )


        return {

            # ------------------------------------------------
            # Connection
            # ------------------------------------------------

            "connected":
                _state["connected"],

            "hardware":
                hardware_available,

            "hardware_available":
                hardware_available,

            "port":
                _state["port"],

            "baudrate":
                _state["baudrate"],


            # ------------------------------------------------
            # Sensor data
            # ------------------------------------------------

            "depth":
                _state["depth"],

            "temperature":
                _state["temperature"],

            "magnetic":
                _state["magnetic"],

            "em":
                _state["em"],

            "inductive":
                _state["inductive"],


            # ------------------------------------------------
            # GPS
            # ------------------------------------------------

            "lat":
                _state["lat"],

            "lon":
                _state["lon"],

            "satellites":
                _state["satellites"],


            # ------------------------------------------------
            # Position
            # ------------------------------------------------

            "x":
                _state["x"],

            "y":
                _state["y"],


            # ------------------------------------------------
            # Identification
            # ------------------------------------------------

            "probe":
                _state["probe"],


            # ------------------------------------------------
            # Status
            # ------------------------------------------------

            "fresh_data":
                fresh,

            "last_update":
                last_update,

            "timestamp":
                last_update,

            "last_packet":
                _state["last_packet"],

            "error":
                _state["error"],


            # ------------------------------------------------
            # Sensor availability
            # ------------------------------------------------

            "sensor_status":
                sensor_info["status"],

            "available_sensors":
                sensor_info[
                    "available_sensors"
                ],

            "unavailable_sensors":
                sensor_info[
                    "unavailable_sensors"
                ],

            "all_required_sensors_available":
                sensor_info[
                    "all_required_sensors_available"
                ],

        }


# ============================================================
# HARDWARE STATUS
# ============================================================

def get_hardware_status():

    reading = get_hardware_reading()


    return {

        "connected":
            reading["connected"],

        "hardware":
            reading["hardware"],

        "hardware_available":
            reading["hardware_available"],

        "port":
            reading["port"],

        "baudrate":
            reading["baudrate"],

        "probe":
            reading["probe"],

        "sensor_status":
            reading["sensor_status"],

        "available_sensors":
            reading["available_sensors"],

        "unavailable_sensors":
            reading["unavailable_sensors"],

        "all_required_sensors_available":
            reading[
                "all_required_sensors_available"
            ],

        "fresh_data":
            reading["fresh_data"],

        "last_update":
            reading["last_update"],

        "error":
            reading["error"],

    }


# ============================================================
# AVAILABLE SERIAL PORTS
# ============================================================

def get_available_ports():

    if not SERIAL_AVAILABLE:

        return []


    try:

        ports = (
            serial.tools.list_ports
            .comports()
        )


        result = []


        for port in ports:

            result.append({

                "port":
                    port.device,

                "description":
                    port.description,

                "manufacturer":
                    port.manufacturer,

            })


        return result


    except Exception:

        return []
