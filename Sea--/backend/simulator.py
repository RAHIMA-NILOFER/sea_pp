"""
SEAFLOOR INTELLIGENCE
SIMULATOR

Purpose:
    Generate test sensor readings when you want to test the
    dashboard and anomaly engine without physical hardware.

IMPORTANT:
    This file does NOT represent real hardware.

    Real hardware data comes from:
        hardware_reader.py

    The simulator is only for:
        - UI development
        - Software testing
        - Demonstrations
        - Testing anomaly detection
"""

import math
import random
import time


# ============================================================
# SIMULATOR STATE
# ============================================================

_state = {

    "x": 100.0,

    "y": 25.0,

    "step": 0,

}


# ============================================================
# SIMULATION SETTINGS
# ============================================================

START_DEPTH = 115.0

BASE_TEMPERATURE = 18.0

BASE_MAGNETIC = 50.0

BASE_EM = 2.5


# ============================================================
# GENERATE READING
# ============================================================

def generate_reading():

    """
    Generate one simulated sensor reading.

    The returned structure intentionally matches the structure
    expected from real hardware.
    """

    # --------------------------------------------------------
    # Advance simulation
    # --------------------------------------------------------

    _state["step"] += 1

    step = _state["step"]


    # ========================================================
    # SIMULATED POSITION
    # ========================================================

    _state["x"] += 0.35

    _state["y"] += (
        math.sin(
            step / 12.0
        )
        *
        0.15
    )


    # Keep probe inside demonstration survey area

    if _state["x"] > 120.0:

        _state["x"] = 90.0


    if _state["y"] > 60.0:

        _state["y"] = 15.0


    x = round(
        _state["x"],
        1,
    )

    y = round(
        _state["y"],
        1,
    )


    # ========================================================
    # SIMULATED DEPTH
    # ========================================================

    depth = (

        START_DEPTH

        +

        math.sin(
            step / 15.0
        )
        *
        4.0

        +

        random.uniform(
            -1.5,
            1.5,
        )

    )


    # ========================================================
    # SIMULATED TEMPERATURE
    # ========================================================

    temperature = (

        BASE_TEMPERATURE

        +

        math.sin(
            step / 20.0
        )
        *
        0.8

        +

        random.uniform(
            -0.25,
            0.25,
        )

    )


    # ========================================================
    # SIMULATED MAGNETIC RESPONSE
    # ========================================================

    anomaly_wave = math.sin(
        step / 18.0
    )


    magnetic = (

        BASE_MAGNETIC

        +

        anomaly_wave
        *
        35.0

        +

        random.uniform(
            -8.0,
            8.0,
        )

    )


    # Keep value sensible

    magnetic = max(
        5.0,
        magnetic,
    )


    # ========================================================
    # SIMULATED EM RESPONSE
    # ========================================================

    em = (

        BASE_EM

        +

        abs(
            anomaly_wave
        )
        *
        3.0

        +

        random.uniform(
            -0.5,
            0.5,
        )

    )


    em = max(
        0.2,
        em,
    )

    # Demonstrate intermittent metal detection without claiming hardware input.
    inductive = anomaly_wave > 0.65


    # ========================================================
    # SIMULATED GPS
    # ========================================================

    # These are demonstration coordinates only.
    # They are NOT real GPS measurements.

    latitude = 0.0

    longitude = 0.0

    satellites = 0


    # ========================================================
    # RETURN DATA
    # ========================================================

    return {

        "timestamp":
            time.time(),

        "x":
            x,

        "y":
            y,

        "depth":
            round(
                depth,
                1,
            ),

        "temperature":
            round(
                temperature,
                2,
            ),

        "magnetic":
            round(
                magnetic,
                1,
            ),

        "em":
            round(
                em,
                3,
            ),

        "inductive":
            inductive,

        "lat":
            latitude,

        "lon":
            longitude,

        "satellites":
            satellites,

        "probe":
            "SIM-PROBE-01",

        "source":
            "SIMULATION",

        "data_source":
            "SIMULATION",

        "hardware":
            False,

        "connected":
            False,

    }


# ============================================================
# NEXT SIMULATED SCAN
# ============================================================

def get_next_scan(x, y):

    """
    Return the next simulated survey position.
    """

    try:

        x = float(x)

    except (
        TypeError,
        ValueError,
    ):

        x = 100.0


    try:

        y = float(y)

    except (
        TypeError,
        ValueError,
    ):

        y = 25.0


    next_x = x + 5.0

    next_y = y + 3.0


    if next_x > 120.0:

        next_x = 90.0


    if next_y > 60.0:

        next_y = 15.0


    return {

        "x":
            round(
                next_x,
                1,
            ),

        "y":
            round(
                next_y,
                1,
            ),

        "information_gain":
            65.0,

        "source":
            "SIMULATION",

    }


# ============================================================
# RESET SIMULATOR
# ============================================================

def reset_simulator():

    """
    Reset the simulated probe to its starting position.
    """

    _state["x"] = 100.0

    _state["y"] = 25.0

    _state["step"] = 0


# ============================================================
# SIMULATOR STATUS
# ============================================================

def get_simulator_status():

    """
    Return simulator state for the dashboard.
    """

    return {

        "active":
            True,

        "source":
            "SIMULATION",

        "probe":
            "SIM-PROBE-01",

        "step":
            _state["step"],

        "position": {

            "x":
                round(
                    _state["x"],
                    1,
                ),

            "y":
                round(
                    _state["y"],
                    1,
                ),

        },

    }
