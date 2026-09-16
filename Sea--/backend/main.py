"""
SEAFLOOR INTELLIGENCE
Main FastAPI Application

REAL HARDWARE
    Arduino / ESP32
        ↓
    hardware_reader.py
        ↓
    main.py
        ↓
    anomaly_engine.py
        ↓
    Dashboard

SIMULATION
    simulator.py
        ↓
    anomaly_engine.py
        ↓
    Dashboard
"""

from pathlib import Path
import time

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ============================================================
# IMPORTS
# ============================================================

# IMPORTANT:
# These imports work when starting the server from backend:
#
# python -m uvicorn main:app --reload
#
# If you run from the project root instead, use:
# python -m uvicorn backend.main:app --reload
#
try:
    from .simulator import generate_reading
    from .anomaly_engine import analyse_reading
    from .hardware_reader import (
        connect_hardware,
        disconnect_hardware,
        get_hardware_reading,
        get_hardware_status,
        get_available_ports,
    )
    from .database import initialize_database
    from .database import save_reading, get_history as get_database_history
except ImportError:
    from simulator import generate_reading
    from anomaly_engine import analyse_reading
    from hardware_reader import (
        connect_hardware,
        disconnect_hardware,
        get_hardware_reading,
        get_hardware_status,
        get_available_ports,
    )
    from database import initialize_database
    from database import save_reading, get_history as get_database_history


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"



# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Seafloor Intelligence Platform",
    description=(
        "Real-time seafloor sensor monitoring, "
        "hardware integration and anomaly detection."
    ),
    version="5.0",
)
app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# FRONTEND
# ============================================================

if FRONTEND_DIR.exists():
    app.mount(
        "/frontend",
        StaticFiles(directory=FRONTEND_DIR),
        name="frontend",
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "system": "SEAFLOOR INTELLIGENCE",
        "status": "online",
        "version": "5.0",
        "message": "Seafloor Intelligence API is running.",
    }


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/dashboard")
def dashboard():

    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():
        return {
            "error": "Dashboard index.html not found.",
            "expected": str(index_file),
        }

    return FileResponse(
        index_file,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


# ============================================================
# HARDWARE STATUS
# ============================================================

@app.get("/api/hardware")
def hardware_status():

    try:
        status = get_hardware_status()
    except Exception as e:
        return {
            "connected": False,
            "hardware": False,
            "data_source": "SIMULATION",
            "probe": "PROBE-01",
            "sensor_status": {},
            "available_sensors": [],
            "unavailable_sensors": [],
            "all_required_sensors_available": False,
            "error": str(e),
        }

    return {
        "connected": status.get("connected", False),
        "hardware": status.get("hardware", False),
        "hardware_connected": (
            status.get("connected", False)
            and status.get("hardware_available", False)
        ),
        "hardware_available": status.get("hardware_available", False),
        "port": status.get("port"),
        "baudrate": status.get("baudrate"),
        "probe": status.get("probe", "PROBE-01"),

        "sensor_status": status.get(
            "sensor_status",
            {}
        ),

        "available_sensors": status.get(
            "available_sensors",
            []
        ),

        "unavailable_sensors": status.get(
            "unavailable_sensors",
            []
        ),

        "all_required_sensors_available": status.get(
            "all_required_sensors_available",
            False
        ),

        "data_source": (
            "REAL HARDWARE"
            if status.get("connected", False)
            and status.get("hardware_available", False)
            else "SIMULATION"
        ),

        "last_update": status.get("last_update"),

        "fresh_data": status.get(
            "fresh_data",
            False
        ),

        "error": status.get("error"),

        "timestamp": time.time(),
    }


# ============================================================
# AVAILABLE SERIAL PORTS
# ============================================================

@app.get("/api/hardware/ports")
def hardware_ports():

    try:
        ports = get_available_ports()
    except Exception:
        ports = []

    return {
        "ports": ports,
        "timestamp": time.time(),
    }


# ============================================================
# CONNECT REAL HARDWARE
# ============================================================

@app.post("/api/hardware/connect")
def connect_real_hardware(
    port: str = "COM5",
    baudrate: int = 115200,
):

    try:

        success = connect_hardware(
            port=port,
            baudrate=baudrate,
        )

        status = get_hardware_status()

        return {
            "success": success,

            "port": port,

            "baudrate": baudrate,

            "connected": status.get(
                "connected",
                False
            ),

            "hardware": status.get(
                "hardware",
                False
            ),

            "data_source": (
                "REAL HARDWARE"
                if status.get("connected", False)
                and status.get("hardware_available", False)
                else "SIMULATION"
            ),

            "status": status,

            "message": (
                f"Hardware connected on {port}."
                if success
                else f"Could not connect to {port}."
            ),

            "timestamp": time.time(),
        }

    except Exception as e:

        return {
            "success": False,
            "connected": False,
            "hardware": False,
            "data_source": "SIMULATION",
            "port": port,
            "baudrate": baudrate,
            "message": f"Hardware connection failed: {str(e)}",
            "error": str(e),
            "timestamp": time.time(),
        }


# ============================================================
# DISCONNECT HARDWARE
# ============================================================

@app.post("/api/hardware/disconnect")
def disconnect_real_hardware():

    try:
        success = disconnect_hardware()
    except Exception:
        success = False

    return {
        "success": success,
        "connected": False,
        "hardware": False,
        "data_source": "SIMULATION",
        "message": "Hardware disconnected.",
        "timestamp": time.time(),
    }


# ============================================================
# SENSOR DATA SOURCE
# ============================================================

def get_sensor_data():

    # --------------------------------------------------------
    # FIRST TRY REAL HARDWARE
    # --------------------------------------------------------

    try:
        hardware = get_hardware_reading()
    except Exception:
        hardware = {
            "connected": False,
            "hardware": False,
        }

    hardware_connected = (
        hardware.get("connected") is True
        and
        hardware.get("hardware") is True
        and
        hardware.get("fresh_data") is True
    )

    # --------------------------------------------------------
    # REAL HARDWARE
    # --------------------------------------------------------

    if hardware_connected:

        return {
            "timestamp": hardware.get(
                "timestamp",
                time.time()
            ),

            "x": hardware.get("x", 0.0),

            "y": hardware.get("y", 0.0),

            "depth": hardware.get("depth"),

            "temperature": hardware.get(
                "temperature"
            ),

            "magnetic": hardware.get(
                "magnetic"
            ),

            "em": hardware.get("em"),

            "inductive": hardware.get(
                "inductive",
                False
            ),

            "lat": hardware.get("lat"),

            "lon": hardware.get("lon"),

            "satellites": hardware.get(
                "satellites",
                0
            ),

            "probe": hardware.get(
                "probe",
                "PROBE-01"
            ),

            "data_source": "REAL HARDWARE",

            "hardware": True,

            "connected": True,

            "sensor_status": hardware.get(
                "sensor_status",
                {}
            ),
        }

    # --------------------------------------------------------
    # SIMULATION
    # --------------------------------------------------------

    simulated = generate_reading()

    simulated["data_source"] = "SIMULATION"

    simulated["hardware"] = False

    simulated["connected"] = False

    simulated["probe"] = simulated.get(
        "probe",
        "PROBE-01"
    )

    simulated["sensor_status"] = {
        "depth": "SIMULATED",
        "temperature": "SIMULATED",
        "magnetic": "SIMULATED",
        "em": "SIMULATED",
    }

    return simulated


# ============================================================
# MAIN SENSOR + AI ENDPOINT
# ============================================================

@app.get("/api/reading")
def reading(response: Response):

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    sensor_data = get_sensor_data()

    try:
        analysis = analyse_reading(
            sensor_data
        )
    except Exception as e:

        analysis = {
            "anomaly_score": 0.0,
            "confidence": 0.0,
            "classification": "NO DATA",
            "magnetic_score": None,
            "em_score": None,
            "thermal_score": None,
            "depth_score": None,
            "sensor_quality": 0.0,
            "hardware_quality": 0.0,
            "missing_sensor_message": str(e),
            "next_scan": {},
        }

    hardware_connected = (
        sensor_data.get("connected") is True
        and
        sensor_data.get("hardware") is True
    )

    response = {

        # SYSTEM
        "system": "SEAFLOOR INTELLIGENCE",

        "timestamp": sensor_data.get(
            "timestamp",
            time.time()
        ),

        # SOURCE
        "data_source": sensor_data.get(
            "data_source",
            "SIMULATION"
        ),

        # HARDWARE
        "hardware":
            hardware_connected,

        "hardware_connected":
            hardware_connected,

        "hardware_available":
            hardware_connected,

        "fresh_data":
            hardware_connected,

        "last_update":
            sensor_data.get("timestamp"),

        "probe":
            sensor_data.get(
                "probe",
                "PROBE-01"
            ),

        # SENSOR VALUES
        "depth":
            sensor_data.get("depth"),

        "temperature":
            sensor_data.get("temperature"),

        "magnetic":
            sensor_data.get("magnetic"),

        "em":
            sensor_data.get("em"),

        "inductive":
            sensor_data.get("inductive", False),

        # SENSOR STATUS
        "sensor_status":
            sensor_data.get(
                "sensor_status",
                {}
            ),

        # POSITION
        "x":
            sensor_data.get(
                "x",
                0.0
            ),

        "y":
            sensor_data.get(
                "y",
                0.0
            ),

        # GPS
        "lat":
            sensor_data.get("lat"),

        "lon":
            sensor_data.get("lon"),

        "satellites":
            sensor_data.get(
                "satellites",
                0
            ),

        # AI ANALYSIS
        "anomaly_score":
            analysis.get(
                "anomaly_score",
                0.0
            ),

        "confidence":
            analysis.get(
                "confidence",
                0.0
            ),

        "classification":
            analysis.get(
                "classification",
                "NO DATA"
            ),

        # INDIVIDUAL SCORES
        "magnetic_score":
            analysis.get(
                "magnetic_score"
            ),

        "em_score":
            analysis.get(
                "em_score"
            ),

        "thermal_score":
            analysis.get(
                "thermal_score"
            ),

        "depth_score":
            analysis.get(
                "depth_score"
            ),

        # QUALITY
        "sensor_quality":
            analysis.get(
                "sensor_quality",
                0.0
            ),

        "hardware_quality":
            analysis.get(
                "hardware_quality",
                0.0
            ),

        # MISSING SENSOR
        "missing_sensor_message":
            analysis.get(
                "missing_sensor_message",
                ""
            ),

        # NEXT SCAN
        "next_scan":
            analysis.get(
                "next_scan",
                {}
            ),
    }

    if sensor_data.get("data_source") == "SIMULATION":
        try:
            save_reading(sensor_data, analysis, {})
        except Exception:
            pass

    return response


# ============================================================
# SENSOR STATUS
# ============================================================

@app.get("/api/sensors")
def sensors():

    data = get_sensor_data()

    sensor_status = data.get(
        "sensor_status",
        {}
    )

    def available(sensor):

        status = sensor_status.get(
            sensor
        )

        return status in (
            "AVAILABLE",
            "SIMULATED",
        )

    return {

        "depth": {
            "value":
                data.get("depth"),

            "status":
                sensor_status.get(
                    "depth",
                    "NOT AVAILABLE"
                ),

            "available":
                available("depth"),
        },

        "temperature": {
            "value":
                data.get("temperature"),

            "status":
                sensor_status.get(
                    "temperature",
                    "NOT AVAILABLE"
                ),

            "available":
                available("temperature"),
        },

        "magnetic": {
            "value":
                data.get("magnetic"),

            "status":
                sensor_status.get(
                    "magnetic",
                    "NOT AVAILABLE"
                ),

            "available":
                available("magnetic"),
        },

        "em": {
            "value":
                data.get("em"),

            "status":
                sensor_status.get(
                    "em",
                    "NOT AVAILABLE"
                ),

            "available":
                available("em"),
        },

        "gps": {

            "latitude":
                data.get("lat"),

            "longitude":
                data.get("lon"),

            "satellites":
                data.get(
                    "satellites",
                    0
                ),

            "available": (
                data.get("lat") is not None
                and
                data.get("lon") is not None
            ),
        },

        "source":
            data.get(
                "data_source",
                "SIMULATION"
            ),

        "hardware_connected":
            data.get(
                "connected",
                False
            ),
    }


# ============================================================
# AI ANALYSIS
# ============================================================

@app.get("/api/analysis")
def analysis():

    data = get_sensor_data()

    try:

        result = analyse_reading(
            data
        )

    except Exception as e:

        result = {
            "anomaly_score": 0.0,
            "confidence": 0.0,
            "classification": "NO DATA",
            "error": str(e),
        }

    return {

        "source":
            data.get(
                "data_source",
                "SIMULATION"
            ),

        "anomaly":
            result,

        "timestamp":
            time.time(),
    }


# ============================================================
# SYSTEM HEALTH
# ============================================================

@app.get("/api/health")
def health():

    try:
        hardware = get_hardware_status()
    except Exception as e:

        return {
            "status": "online",
            "system": "SEAFLOOR-INTEL",
            "version": "5.0",
            "data_source": "SIMULATION",
            "hardware_connected": False,
            "hardware_available": False,
            "sensor_status": {},
            "error": str(e),
            "timestamp": time.time(),
        }

    connected = (
        hardware.get("connected") is True
        and
        hardware.get("hardware") is True
    )

    return {

        "status":
            "online",

        "system":
            "SEAFLOOR-INTEL",

        "version":
            "5.0",

        "data_source": (
            "REAL HARDWARE"
            if connected
            else
            "SIMULATION"
        ),

        "hardware_connected":
            connected,

        "hardware_available":
            connected,

        "serial_port":
            hardware.get("port"),

        "baudrate":
            hardware.get("baudrate"),

        "sensor_status":
            hardware.get(
                "sensor_status",
                {}
            ),

        "all_required_sensors_available":
            hardware.get(
                "all_required_sensors_available",
                False
            ),

        "last_update":
            hardware.get(
                "last_update"
            ),

        "fresh_data":
            hardware.get(
                "fresh_data",
                False
            ),

        "error":
            hardware.get("error"),

        "timestamp":
            time.time(),
    }


# ============================================================
# SYSTEM INFORMATION
# ============================================================

@app.get("/api/system")
def system_information():

    try:
        hardware = get_hardware_status()
    except Exception:
        hardware = {}

    return {

        "system":
            "SEAFLOOR INTELLIGENCE",

        "version":
            "5.0",

        "backend":
            "FastAPI",

        "analysis_engine":
            "Sensor Fusion Anomaly Engine",

        "hardware_interface":
            "Serial JSON",

        "sensors": [

            "MS5837 Depth / Pressure Sensor",

            "DS18B20 Temperature Sensor",

            "QMC5883L Magnetic Sensor",

            "EM Sensor",

            "GPS",
        ],

        "required_sensors": [

            "depth",

            "temperature",

            "magnetic",

            "em",
        ],

        "hardware_connected":
            hardware.get(
                "connected",
                False
            ),

        "hardware_verified":
            hardware.get(
                "hardware",
                False
            ),

        "port":
            hardware.get("port"),

        "sensor_status":
            hardware.get(
                "sensor_status",
                {}
            ),

        "timestamp":
            time.time(),
    }
@app.get("/api/history")
def get_history(limit: int = 200):
    records = get_database_history(limit)
    return {
        "records": records,
        "total": len(records),
        "source": records[-1]["source"] if records else "SIMULATION"
    }

# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup_event():

    initialize_database()

    print()
    print("=" * 55)
    print("       SEAFLOOR INTELLIGENCE PLATFORM")
    print("=" * 55)
    print("FastAPI backend started.")
    print("Hardware interface: READY")
    print("Simulation mode: READY")
    print("Anomaly engine: READY")
    print("Dashboard: READY")
    # The ESP32 is installed on COM5.  A missing/unavailable port is not a
    # startup failure; the Hardware page can retry the connection.
    if not get_hardware_status().get("connected", False):
        if connect_hardware(port="COM5", baudrate=115200):
            print("Hardware interface: connected to COM5")
        else:
            print("Hardware interface: COM5 unavailable; awaiting connection")
    print("=" * 55)
    print()


@app.on_event("shutdown")
def shutdown_event():
    """Release COM5 cleanly when FastAPI stops."""
    disconnect_hardware()
