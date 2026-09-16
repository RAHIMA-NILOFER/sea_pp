import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_FILE = DATA_DIR / "seafloor.db"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    # Sensor readings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            data_source TEXT,
            hardware_connected INTEGER,
            probe TEXT,
            depth REAL,
            temperature REAL,
            magnetic REAL,
            em REAL,
            latitude REAL,
            longitude REAL,
            satellites INTEGER,
            x REAL,
            y REAL,
            anomaly_score REAL,
            confidence REAL,
            classification TEXT
        )
    """)

    # Hardware connection/disconnection history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hardware_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event TEXT,
            port TEXT,
            probe TEXT,
            details TEXT
        )
    """)

    columns = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(sensor_readings)")
    }
    if "confidence" not in columns:
        cursor.execute(
            "ALTER TABLE sensor_readings ADD COLUMN confidence REAL"
        )

    conn.commit()
    conn.close()


def save_reading(sensor_data, analysis, hardware_status):
    initialize_database()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sensor_readings (
            timestamp,
            data_source,
            hardware_connected,
            probe,
            depth,
            temperature,
            magnetic,
            em,
            latitude,
            longitude,
            satellites,
            x,
            y,
            anomaly_score,
            confidence,
            classification
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        sensor_data.get("data_source"),

        1 if sensor_data.get("connected") else 0,

        sensor_data.get("probe", "PROBE-01"),

        sensor_data.get("depth"),
        sensor_data.get("temperature"),
        sensor_data.get("magnetic"),
        sensor_data.get("em"),

        sensor_data.get("lat"),
        sensor_data.get("lon"),
        sensor_data.get("satellites", 0),

        sensor_data.get("x"),
        sensor_data.get("y"),

        analysis.get("anomaly_score", 0.0),
        analysis.get("confidence", 0.0),
        analysis.get("classification", "NO DATA")
    ))

    conn.commit()
    conn.close()


def get_history(limit=200):
    initialize_database()
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            timestamp,
            data_source AS source,
            CASE hardware_connected
                WHEN 1 THEN 'REAL HARDWARE'
                ELSE 'SIMULATION'
            END AS status,
            depth,
            temperature,
            magnetic,
            em,
            x,
            y,
            anomaly_score AS anomaly,
            classification
        FROM sensor_readings
        ORDER BY id DESC
        LIMIT ?
    """, (max(1, int(limit)),)).fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]


def save_hardware_packet(packet):
    """Save one already-validated ESP32 packet without fabricating values."""
    initialize_database()
    save_reading(
        {
            "data_source": "REAL HARDWARE",
            "connected": True,
            "probe": packet.get("probe"),
            "depth": packet.get("depth"),
            "temperature": packet.get("temperature"),
            "magnetic": packet.get("magnetic"),
            "em": packet.get("em"),
            "lat": packet.get("lat"),
            "lon": packet.get("lon"),
            "satellites": packet.get("satellites", 0),
            "x": packet.get("x", 0.0),
            "y": packet.get("y", 0.0),
        },
        {
            "anomaly_score": 0.0,
            "confidence": 0.0,
            "classification": "PENDING ANALYSIS",
        },
        {},
    )


def save_hardware_event(
    event,
    port=None,
    probe="PROBE-01",
    details=""
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO hardware_events (
            timestamp,
            event,
            port,
            probe,
            details
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        event,
        port,
        probe,
        details
    ))

    conn.commit()
    conn.close()
