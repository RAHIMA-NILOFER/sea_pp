"""
SEAFLOOR INTELLIGENCE
ANOMALY ENGINE

Purpose:
    Analyse sensor readings and determine whether the
    surveyed area requires attention.

Sensor fusion:
    Magnetic     -> 50%
    EM           -> 35%
    Temperature  -> 15%

Depth/pressure:
    Used as supporting telemetry.
    It is NOT included in anomaly scoring because the
    pressure sensor may currently be unavailable.

The engine works with both:
    REAL HARDWARE
    SIMULATION
"""

import math
import time


# ============================================================
# SENSOR BASELINES
# ============================================================

MAGNETIC_BASELINE = 50.0
EM_BASELINE = 2.5
TEMPERATURE_BASELINE = 18.0


# ============================================================
# SENSOR WEIGHTS
# ============================================================

MAGNETIC_WEIGHT = 0.50
EM_WEIGHT = 0.35
THERMAL_WEIGHT = 0.15


# ============================================================
# CLASSIFICATION THRESHOLDS
# ============================================================

CRITICAL_THRESHOLD = 70.0
ELEVATED_THRESHOLD = 45.0
WATCH_THRESHOLD = 25.0


# ============================================================
# SAFE NUMBER CONVERSION
# ============================================================

def safe_float(value):

    if value is None:
        return None

    try:

        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):

        return None


# ============================================================
# NORMALIZED DEVIATION
# ============================================================

def normalized_deviation(
    value,
    baseline,
    scale,
):

    value = safe_float(value)

    if value is None:

        return None

    deviation = abs(
        value - baseline
    ) / scale

    return min(
        deviation,
        1.0
    )


# ============================================================
# ANALYSE READING
# ============================================================

def analyse_reading(data):

    """
    Analyse one sensor reading.

    Returns:
        anomaly score
        confidence
        classification
        individual sensor scores
        sensor availability
        next scan recommendation
    """

    # ========================================================
    # READ SENSOR VALUES
    # ========================================================

    magnetic = safe_float(
        data.get("magnetic")
    )

    em = safe_float(
        data.get("em")
    )

    temperature = safe_float(
        data.get("temperature")
    )

    depth = safe_float(
        data.get("depth")
    )

    x = safe_float(
        data.get("x")
    )

    y = safe_float(
        data.get("y")
    )


    # ========================================================
    # SENSOR DEVIATION SCORES
    # ========================================================

    magnetic_score = normalized_deviation(

        magnetic,

        MAGNETIC_BASELINE,

        100.0,

    )


    em_score = normalized_deviation(

        em,

        EM_BASELINE,

        8.0,

    )


    thermal_score = normalized_deviation(

        temperature,

        TEMPERATURE_BASELINE,

        10.0,

    )


    # ========================================================
    # MISSING SENSOR HANDLING
    # ========================================================

    available_scores = []

    available_weights = []


    if magnetic_score is not None:

        available_scores.append(
            magnetic_score
        )

        available_weights.append(
            MAGNETIC_WEIGHT
        )


    if em_score is not None:

        available_scores.append(
            em_score
        )

        available_weights.append(
            EM_WEIGHT
        )


    if thermal_score is not None:

        available_scores.append(
            thermal_score
        )

        available_weights.append(
            THERMAL_WEIGHT
        )


    # ========================================================
    # NO SENSOR DATA
    # ========================================================

    if not available_scores:

        return {

            "anomaly_score":
                0.0,

            "confidence":
                0.0,

            "classification":
                "NO DATA",

            "magnetic_score":
                0.0,

            "em_score":
                0.0,

            "thermal_score":
                0.0,

            "depth_available":
                depth is not None,

            "sensors_available":
                0,

            "sensors_used":
                [],

            "sensor_status":
                "NO SENSOR DATA",

            "next_scan":
                calculate_next_scan(
                    x,
                    y,
                    0.0,
                ),

            "analysis_timestamp":
                time.time(),

        }


    # ========================================================
    # WEIGHTED SENSOR FUSION
    #
    # We normalize by the weights of available sensors.
    #
    # Example:
    #
    # If depth is unavailable -> no problem.
    #
    # If temperature is unavailable:
    #
    # magnetic + EM weights are re-normalized.
    # ========================================================

    weighted_sum = 0.0

    total_weight = 0.0

    sensors_used = []


    if magnetic_score is not None:

        weighted_sum += (

            magnetic_score
            *
            MAGNETIC_WEIGHT

        )

        total_weight += MAGNETIC_WEIGHT

        sensors_used.append(
            "MAGNETIC"
        )


    if em_score is not None:

        weighted_sum += (

            em_score
            *
            EM_WEIGHT

        )

        total_weight += EM_WEIGHT

        sensors_used.append(
            "EM"
        )


    if thermal_score is not None:

        weighted_sum += (

            thermal_score
            *
            THERMAL_WEIGHT

        )

        total_weight += THERMAL_WEIGHT

        sensors_used.append(
            "TEMPERATURE"
        )


    # --------------------------------------------------------
    # Normalize based on available sensors.
    # --------------------------------------------------------

    if total_weight > 0:

        anomaly_score = (

            weighted_sum
            /
            total_weight

        )

    else:

        anomaly_score = 0.0


    anomaly_percent = round(

        anomaly_score
        *
        100.0,

        1,

    )


    # ========================================================
    # CLASSIFICATION
    # ========================================================

    if anomaly_percent >= CRITICAL_THRESHOLD:

        classification = "CRITICAL"

    elif anomaly_percent >= ELEVATED_THRESHOLD:

        classification = "ELEVATED"

    elif anomaly_percent >= WATCH_THRESHOLD:

        classification = "WATCH"

    else:

        classification = "NORMAL"


    # ========================================================
    # CONFIDENCE
    #
    # Confidence depends on:
    #
    # 1. Number of available sensors
    # 2. Strength of the measured deviation
    #
    # It is NOT the probability that an anomaly physically
    # exists. It is a prototype confidence indicator.
    # ========================================================

    sensor_coverage = (

        total_weight
        /
        (
            MAGNETIC_WEIGHT
            +
            EM_WEIGHT
            +
            THERMAL_WEIGHT
        )

    )


    base_confidence = (

        55.0
        +
        sensor_coverage
        *
        25.0

    )


    deviation_confidence = (

        abs(
            anomaly_percent
            -
            35.0
        )
        *
        0.25

    )


    confidence = min(

        99.0,

        max(

            50.0,

            base_confidence
            +
            deviation_confidence

        )

    )


    confidence = round(
        confidence,
        1,
    )


    # ========================================================
    # SENSOR STATUS
    # ========================================================

    if sensor_coverage >= 0.99:

        sensor_status = (
            "ALL ANALYSIS SENSORS AVAILABLE"
        )

    elif sensor_coverage >= 0.70:

        sensor_status = (
            "PARTIAL SENSOR DATA"
        )

    else:

        sensor_status = (
            "LIMITED SENSOR DATA"
        )


    # ========================================================
    # NEXT BEST SCAN
    # ========================================================

    next_scan = calculate_next_scan(

        x,

        y,

        anomaly_percent,

    )


    # ========================================================
    # ANALYSIS RESULT
    # ========================================================

    return {

        "anomaly_score":
            anomaly_percent,

        "confidence":
            confidence,

        "classification":
            classification,

        "magnetic_score":
            round(
                (
                    magnetic_score
                    *
                    100.0
                )
                if magnetic_score is not None
                else 0.0,

                1,
            ),

        "em_score":
            round(
                (
                    em_score
                    *
                    100.0
                )
                if em_score is not None
                else 0.0,

                1,
            ),

        "thermal_score":
            round(
                (
                    thermal_score
                    *
                    100.0
                )
                if thermal_score is not None
                else 0.0,

                1,
            ),

        "depth_available":
            depth is not None,

        "sensors_available":
            len(
                sensors_used
            ),

        "sensors_used":
            sensors_used,

        "sensor_status":
            sensor_status,

        "next_scan":
            next_scan,

        "analysis_timestamp":
            time.time(),

    }


# ============================================================
# NEXT-BEST SCAN
# ============================================================

def calculate_next_scan(
    x,
    y,
    anomaly_percent,
):

    """
    Recommend the next survey location.

    Higher anomaly:
        Smaller step -> investigate nearby area.

    Lower anomaly:
        Larger step -> explore more area.
    """

    # --------------------------------------------------------
    # Safe position values
    # --------------------------------------------------------

    if x is None:

        x = 100.0


    if y is None:

        y = 25.0


    # --------------------------------------------------------
    # Step size
    # --------------------------------------------------------

    if anomaly_percent >= CRITICAL_THRESHOLD:

        step_x = 2.0
        step_y = 2.0

    elif anomaly_percent >= ELEVATED_THRESHOLD:

        step_x = 3.0
        step_y = 2.5

    elif anomaly_percent >= WATCH_THRESHOLD:

        step_x = 4.0
        step_y = 3.0

    else:

        step_x = 5.0
        step_y = 3.0


    next_x = float(x) + step_x

    next_y = float(y) + step_y


    # ========================================================
    # SURVEY BOUNDARIES
    # ========================================================

    if next_x > 120.0:

        next_x = 90.0


    if next_y > 60.0:

        next_y = 15.0


    # ========================================================
    # INFORMATION GAIN
    # ========================================================

    information_gain = (

        40.0

        +

        anomaly_percent
        *
        0.55

    )


    information_gain = min(

        information_gain,

        95.0,

    )


    information_gain = round(

        information_gain,

        1,

    )


    # ========================================================
    # REASON
    # ========================================================

    if anomaly_percent >= CRITICAL_THRESHOLD:

        reason = (

            "Strong multi-sensor anomaly detected. "
            "Prioritize the adjacent grid cell "
            "for confirmation."

        )

    elif anomaly_percent >= ELEVATED_THRESHOLD:

        reason = (

            "Elevated sensor deviation detected. "
            "Increase local sampling density."

        )

    elif anomaly_percent >= WATCH_THRESHOLD:

        reason = (

            "Moderate deviation detected. "
            "Additional spatial sampling recommended."

        )

    else:

        reason = (

            "Sensor values remain within the "
            "expected local range."

        )


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
            information_gain,

        "reason":
            reason,

    }