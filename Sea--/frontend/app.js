"use strict";

/*
============================================================
 SEAFLOOR INTELLIGENCE
 ESP32 -> FastAPI -> FRONTEND
 REAL HARDWARE TELEMETRY
============================================================
*/

let missionSeconds = 0;
let scanCount = 0;
let latestData = null;
let browserLocation = null;
let mapLocationKey = null;
let landCheckKey = null;


/* ============================================================
   HELPER
============================================================ */

function $(id) {
    return document.getElementById(id);
}


function setText(id, value) {
    /* The dashboard HTML uses kebab-case IDs; retain these aliases so
       optional/legacy dashboard widgets cannot stop live telemetry. */
    const aliases = {
        depthValue: ["depth-value"],
        temperatureValue: ["temperature-value"],
        magneticValue: ["magnetic-value"],
        emValue: ["em-value"],
        xValue: ["probe-x", "survey-x"],
        yValue: ["probe-y", "survey-y"],
        latValue: ["latitude", "survey-lat"],
        lonValue: ["longitude", "survey-lon"],
        satelliteValue: ["satellites"],
        anomalyScore: ["anomaly-value"],
        anomalyIndex: ["anomaly-bar-value", "analysis-score"],
        classification: ["classification-value", "analysis-classification"],
        confidenceText: ["confidence-value", "analysis-confidence"],
        magneticDeviation: ["magnetic-score"],
        emDeviation: ["em-score"],
        targetX: ["next-x"],
        targetY: ["next-y"],
        informationGain: ["information-gain"],
        connectionText: ["system-connection"],
        hardwareStatus: ["hardware-status"],
        systemStatus: ["health-source"],
        connectionStatus: ["hardware-port-status"],
    };
    const ids = aliases[id] || [id];
    ids.forEach(function(target) {
        const element = $(target);
        if (element) element.textContent = value;
    });
}


function formatNumber(value, digits = 2) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "--";
    }

    const n = Number(value);

    if (!Number.isFinite(n)) {
        return "--";
    }

    return n.toFixed(digits);
}


function validCoordinate(value) {
    return Number.isFinite(Number(value)) && Number(value) !== 0;
}


function ensureMapFrame(container) {
    if (!container) {
        return null;
    }

    let frame = container.querySelector(".real-map-frame");
    if (!frame) {
        frame = document.createElement("iframe");
        frame.className = "real-map-frame";
        frame.title = "Current survey map";
        frame.loading = "lazy";
        frame.referrerPolicy = "no-referrer-when-downgrade";
        frame.style.position = "absolute";
        frame.style.inset = "0";
        frame.style.width = "100%";
        frame.style.height = "100%";
        frame.style.border = "0";
        frame.style.zIndex = "0";
        frame.style.backgroundColor = "#03121b";
        frame.style.filter = "grayscale(1) brightness(0.3) contrast(1.15)";
        container.appendChild(frame);

        const tint = document.createElement("div");
        tint.className = "real-map-tint";
        tint.style.position = "absolute";
        tint.style.inset = "0";
        tint.style.zIndex = "1";
        tint.style.pointerEvents = "none";
        tint.style.backgroundColor = "rgba(0, 0, 0, 0.78)";
        container.appendChild(tint);
    }
    return frame;
}


function showRealMap(latitude, longitude, targetLatitude, targetLongitude) {
    const lat = Number(targetLatitude || latitude);
    const lon = Number(targetLongitude || longitude);
    const key = [latitude, longitude, targetLatitude, targetLongitude].map(function(value) {
        return Number(value).toFixed(5);
    }).join(",");

    if (!Number.isFinite(lat) || !Number.isFinite(lon) || key === mapLocationKey) {
        return;
    }

    mapLocationKey = key;
    const delta = 0.006;
    const bbox = [lon - delta, lat - delta, lon + delta, lat + delta].join(",");
    const source = "https://www.openstreetmap.org/export/embed.html?bbox=" + encodeURIComponent(bbox) + "&layer=mapnik&marker=" + encodeURIComponent(lat + "," + lon);

    document.querySelectorAll(".position-map, .survey-map-large").forEach(function(container) {
        const frame = ensureMapFrame(container);
        if (frame) {
            frame.src = source;
        }
    });
}


async function checkLand(latitude, longitude) {
    const key = Number(latitude).toFixed(4) + "," + Number(longitude).toFixed(4);
    if (key === landCheckKey) {
        return;
    }

    landCheckKey = key;
    try {
        const response = await fetch(
            "https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=10&lat=" +
            encodeURIComponent(latitude) + "&lon=" + encodeURIComponent(longitude),
            { headers: { "Accept": "application/json" } }
        );
        const place = await response.json();
        const isLand = Boolean(place.address && (
            place.address.country ||
            place.address.state ||
            place.address.city ||
            place.address.town ||
            place.address.village
        ));

        if (isLand) {
            setText("nextReason", "Could not find next-best scan: land detected.");
            setText("informationGain", "—");
            return;
        }

        if (latestData && latestData.next_scan && latestData.next_scan.reason) {
            setText("nextReason", latestData.next_scan.reason);
        }
    } catch (error) {
        console.warn("Map location check unavailable:", error);
    }
}


function updateRealMap(data) {
    let latitude = validCoordinate(data.lat) ? Number(data.lat) : null;
    let longitude = validCoordinate(data.lon) ? Number(data.lon) : null;

    if (latitude === null && browserLocation) {
        latitude = browserLocation.latitude;
        longitude = browserLocation.longitude;
    }

    if (latitude === null && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
            browserLocation = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude
            };
            updateRealMap(data);
        }, function() {
            setText("nextReason", "Waiting for current location...");
        }, { enableHighAccuracy: true, maximumAge: 60000, timeout: 10000 });
        return;
    }

    if (latitude === null || longitude === null) {
        return;
    }

    const next = data.next_scan || {};
    const xStep = Number(next.x) - Number(data.x || 0);
    const yStep = Number(next.y) - Number(data.y || 0);
    const targetLatitude = validCoordinate(next.latitude)
        ? Number(next.latitude)
        : latitude + (Number.isFinite(yStep) ? yStep : 5) / 111320;
    const targetLongitude = validCoordinate(next.longitude)
        ? Number(next.longitude)
        : longitude + (Number.isFinite(xStep) ? xStep : 5) / (111320 * Math.cos(latitude * Math.PI / 180));

    showRealMap(latitude, longitude, targetLatitude, targetLongitude);
    checkLand(latitude, longitude);
}


function updateMapPointers(data) {
    const next = data.next_scan || {};

    function position(value, minimum, maximum) {
        const number = Number(value);
        if (!Number.isFinite(number)) {
            return "50%";
        }
        return Math.max(0, Math.min(100, ((number - minimum) / (maximum - minimum)) * 100)) + "%";
    }

    document.querySelectorAll(".probe-marker").forEach(function(marker) {
        marker.style.left = position(data.x, 90, 120);
        marker.style.top = (100 - parseFloat(position(data.y, 15, 60))) + "%";
        marker.style.transition = "left 0.35s ease, top 0.35s ease";
    });

    document.querySelectorAll(".next-marker").forEach(function(marker) {
        marker.style.left = position(next.x, 90, 120);
        marker.style.top = (100 - parseFloat(position(next.y, 15, 60))) + "%";
        marker.style.transition = "left 0.35s ease, top 0.35s ease";
    });
}


/* ============================================================
   UPDATE HARDWARE STATUS
============================================================ */

function updateHardwareStatus(data) {

    if (!data) {
        return;
    }

    const realHardware =
        data.hardware_connected === true &&
        (
            data.hardware_available === true ||
            data.data_source === "REAL HARDWARE"
        );

    console.log(
        "HARDWARE:",
        realHardware ? "REAL HARDWARE" : "SIMULATION"
    );


    /*
    ------------------------------------------------------------
    TOP MODE BADGE
    ------------------------------------------------------------
    */

    const possibleStatusIds = [
        "connectionText",
        "hardwareStatus",
        "systemStatus",
        "connectionStatus",
        "mode",
        "system-connection",
        "health-source",
        "hardware-status",
        "hardware-source",
        "hardware-port-status"
    ];

    possibleStatusIds.forEach(function(id) {

        const element = $(id);

        if (!element) {
            return;
        }

        element.textContent =
            realHardware
                ? "REAL HARDWARE"
                : "SIMULATION MODE";

        if (realHardware) {

            element.classList.remove(
                "simulation",
                "offline"
            );

            element.classList.add(
                "hardware-connected"
            );

        } else {

            element.classList.remove(
                "hardware-connected"
            );

            element.classList.add(
                "simulation"
            );
        }
    });


    /*
    ------------------------------------------------------------
    CHANGE VISIBLE SIMULATION TEXT
    ------------------------------------------------------------
    */

    document
        .querySelectorAll("body *")
        .forEach(function(element) {

            if (
                element.children.length !== 0
            ) {
                return;
            }

            const text =
                element.textContent
                    .trim()
                    .toUpperCase();

            if (
                text === "SIMULATION MODE" ||
                text === "SIMULATION"
            ) {

                element.textContent =
                    realHardware
                        ? "REAL HARDWARE"
                        : "SIMULATION MODE";
            }
        });
}


/* ============================================================
   SENSOR STATUS
============================================================ */

function updateSensorStatus(data) {

    if (!data) {
        return;
    }

    const status =
        data.sensor_status || {};


    setText(
        "temperatureStatus",
        status.temperature === "AVAILABLE"
            ? "AVAILABLE"
            : "NOT AVAILABLE"
    );


    setText(
        "magneticStatus",
        status.magnetic === "AVAILABLE"
            ? "AVAILABLE"
            : "NOT AVAILABLE"
    );


    setText(
        "emStatus",
        status.em === "AVAILABLE"
            ? "AVAILABLE"
            : "NOT AVAILABLE"
    );


    setText(
        "depthStatus",
        status.depth === "AVAILABLE"
            ? "AVAILABLE"
            : "NOT AVAILABLE"
    );


    setText(
        "gpsStatus",
        status.gps === "AVAILABLE"
            ? "AVAILABLE"
            : "NOT AVAILABLE"
    );
}


/* ============================================================
   UPDATE MAIN SENSOR VALUES
============================================================ */

function updateTelemetry(data) {

    if (!data) {
        console.warn("No telemetry data received");
        return;
    }

    latestData = data;

    updateRealMap(data);
    updateMapPointers(data);

    console.log(
        "ESP32 -> FASTAPI -> FRONTEND",
        data
    );


    /*
    ------------------------------------------------------------
    SENSOR VALUES
    ------------------------------------------------------------
    */

    const depth =
        data.depth;

    const temperature =
        data.temperature;

    const magnetic =
        data.magnetic;

    const em =
        data.em;


    /*
    ------------------------------------------------------------
    MAIN SENSOR CARDS
    ------------------------------------------------------------
    */

    // Render the API value verbatim, including -1 reported by the ESP32 for
    // an unavailable depth sensor.  Status is shown separately.
    setText("depthValue", formatNumber(depth, 2));


    /*
    Temperature
    */

    setText(
        "temperatureValue",
        formatNumber(temperature, 2)
    );


    /*
    Magnetic
    */

    setText(
        "magneticValue",
        formatNumber(magnetic, 2)
    );


    /*
    EM
    */

    setText(
        "emValue",
        formatNumber(em, 3)
    );

    const metalDetected = data.inductive === true;
    setText(
        "inductive-value",
        metalDetected ? "METAL DETECTED" : "NO METAL"
    );

    const inductiveCard = $("inductive-card");
    const inductiveDot = $("inductive-dot");
    if (inductiveCard) {
        inductiveCard.classList.toggle("metal-detected", metalDetected);
    }
    if (inductiveDot) {
        inductiveDot.classList.toggle("metal-detected", metalDetected);
    }

    setText("sensor-depth-value", formatNumber(depth, 2) + " m");
    setText("sensor-temperature-value", formatNumber(temperature, 2) + " °C");
    setText("sensor-magnetic-value", formatNumber(magnetic, 2) + " µT");
    setText("sensor-em-value", formatNumber(em, 3));

    const updatedAt = Number(data.timestamp) * 1000;
    setText(
        "last-update",
        Number.isFinite(updatedAt)
            ? new Date(updatedAt).toLocaleTimeString()
            : "--"
    );


    /*
    ------------------------------------------------------------
    COORDINATES
    ------------------------------------------------------------
    */

    setText(
        "xValue",
        formatNumber(data.x ?? 0, 2)
    );

    setText(
        "yValue",
        formatNumber(data.y ?? 0, 2)
    );

    setText(
        "latValue",
        formatNumber(data.lat, 6)
    );

    setText(
        "lonValue",
        formatNumber(data.lon, 6)
    );

    setText(
        "satelliteValue",
        String(data.satellites ?? 0)
    );


    /*
    ------------------------------------------------------------
    BOTTOM TELEMETRY
    ------------------------------------------------------------
    */

    setText("bottomDepth", formatNumber(depth, 2) + " m");


    setText(
        "bottomTemperature",
        formatNumber(temperature, 2) + " °C"
    );


    setText(
        "bottomMagnetic",
        formatNumber(magnetic, 2) + " µT"
    );


    setText(
        "bottomEM",
        formatNumber(em, 3) + " V"
    );


    /*
    ------------------------------------------------------------
    ANOMALY
    ------------------------------------------------------------
    */

    if (
        data.anomaly_score !== null &&
        data.anomaly_score !== undefined
    ) {

        const score =
            Number(data.anomaly_score);

        setText(
            "anomalyScore",
            formatNumber(score, 1) + " %"
        );

        setText(
            "anomalyIndex",
            formatNumber(score, 1)
        );
    }


    /*
    ------------------------------------------------------------
    CLASSIFICATION
    ------------------------------------------------------------
    */

    if (data.classification) {

        setText(
            "classification",
            data.classification
        );
    }


    /*
    ------------------------------------------------------------
    CONFIDENCE
    ------------------------------------------------------------
    */

    if (
        data.confidence !== null &&
        data.confidence !== undefined
    ) {

        const confidence =
            Number(data.confidence);

        setText(
            "confidenceText",
            formatNumber(confidence, 1) + "%"
        );


        const confidenceBar =
            $("confidenceBar");

        if (confidenceBar) {

            confidenceBar.style.width =
                Math.max(
                    0,
                    Math.min(
                        100,
                        confidence
                    )
                ) + "%";
        }
    }


    /*
    ------------------------------------------------------------
    SENSOR SCORES
    ------------------------------------------------------------
    */

    if (
        data.magnetic_score !== null &&
        data.magnetic_score !== undefined
    ) {

        setText(
            "magneticDeviation",
            formatNumber(
                data.magnetic_score,
                1
            )
        );
    }


    if (
        data.em_score !== null &&
        data.em_score !== undefined
    ) {

        setText(
            "emDeviation",
            formatNumber(
                data.em_score,
                1
            )
        );
    }


    /*
    ------------------------------------------------------------
    NEXT SCAN
    ------------------------------------------------------------
    */

    if (data.next_scan) {

        if (
            data.next_scan.x !== undefined
        ) {

            setText(
                "targetX",
                formatNumber(
                    data.next_scan.x,
                    2
                )
            );
        }


        if (
            data.next_scan.y !== undefined
        ) {

            setText(
                "targetY",
                formatNumber(
                    data.next_scan.y,
                    2
                )
            );
        }


        if (
            data.next_scan.information_gain !== undefined
        ) {

            setText(
                "informationGain",
                formatNumber(
                    data.next_scan.information_gain,
                    1
                ) + "%"
            );
        }
    }


    /*
    ------------------------------------------------------------
    UPDATE HARDWARE/SENSOR STATUS
    ------------------------------------------------------------
    */

    updateHardwareStatus(data);

    updateSensorStatus(data);
}


/* ============================================================
   FETCH REAL DATA FROM FASTAPI
============================================================ */

async function fetchTelemetry() {

    try {

        console.log(
            "Fetching /api/reading..."
        );


        const response =
            await fetch(
                "/api/reading?ts=" +
                Date.now(),
                {
                    method: "GET",
                    cache: "no-store",
                    headers: {
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache"
                    }
                }
            );


        if (!response.ok) {

            throw new Error(
                "HTTP " +
                response.status
            );
        }


        const data =
            await response.json();


        console.log(
            "API DATA:",
            data
        );


        updateTelemetry(data);


    } catch (error) {

        console.error(
            "Telemetry error:",
            error
        );


        /*
        Do NOT automatically replace
        real values with fake values.
        */

        const connectionText =
            $("connectionText");

        if (connectionText) {

            connectionText.textContent =
                "BACKEND OFFLINE";
        }
    }
}


/* ============================================================
   HARDWARE STATUS
============================================================ */

async function getHardwareData() {

    try {

        const response =
            await fetch(
                "/api/hardware?ts=" +
                Date.now(),
                {
                    method: "GET",
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                "HTTP " +
                response.status
            );
        }


        const data =
            await response.json();


        console.log(
            "HARDWARE STATUS:",
            data
        );


        /*
        /api/hardware uses slightly
        different field names.
        */

        const converted = {

            hardware_connected:
                data.connected === true,

            hardware_available:
                data.hardware === true,

            data_source:
                data.data_source,

            sensor_status:
                data.sensor_status,

            port: data.port,

            baudrate: data.baudrate,

            probe: data.probe
        };


        updateHardwareStatus(
            converted
        );

        updateSensorStatus(
            converted
        );


    } catch (error) {

        console.error(
            "Hardware status error:",
            error
        );
    }
}


async function fetchHistory() {
    const response = await fetch("/api/history?limit=200", { cache: "no-store" });
    if (!response.ok) {
        throw new Error("HTTP " + response.status);
    }

    const data = await response.json();
    const records = data.records || [];
    const table = $("historyTableBody");

    setText("historyCount", String(data.total ?? records.length));
    setText("historySource", records.length ? records[records.length - 1].source : "—");
    setText("historyStatus", records.length ? records[records.length - 1].status : "—");

    if (!table) {
        return;
    }

    table.innerHTML = records.length
        ? records.map(function(record) {
            return `<tr><td>${record.timestamp || "—"}</td><td>${record.source || "—"}</td><td>${record.status || "—"}</td><td>${formatNumber(record.depth, 2)}</td><td>${formatNumber(record.temperature, 2)}</td><td>${formatNumber(record.magnetic, 2)}</td><td>${formatNumber(record.em, 3)}</td><td>${formatNumber(record.x, 2)}</td><td>${formatNumber(record.y, 2)}</td><td>${formatNumber(record.anomaly, 1)}</td><td>${record.classification || "—"}</td></tr>`;
        }).join("")
        : '<tr><td colspan="11" class="history-empty">No historical readings recorded.</td></tr>';
}


/* ============================================================
   MISSION TIMER
============================================================ */

function updateTimer() {

    missionSeconds++;


    const hours =
        Math.floor(
            missionSeconds / 3600
        );


    const minutes =
        Math.floor(
            (missionSeconds % 3600) / 60
        );


    const seconds =
        missionSeconds % 60;


    const time =
        String(hours).padStart(2, "0") +
        ":" +
        String(minutes).padStart(2, "0") +
        ":" +
        String(seconds).padStart(2, "0");


    setText(
        "missionTimer",
        time
    );
}


/* ============================================================
   CLOCK
============================================================ */

function updateClock() {
    const now =
        new Date();


    const time =
        now.toLocaleTimeString(
            [],
            {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false
            }
        );


    const date =
        now.toLocaleDateString(
            [],
            {
                day: "2-digit",
                month: "short",
                year: "numeric"
            }
        );


    setText(
        "live-clock",
        time
    );

    setText(
        "live-date",
        date
    );


    setText(
        "systemClock",
        time
    );
}


function navigateToPage(page, activeItem) {
    document.querySelectorAll(".page[data-page]").forEach(function(section) {
        section.classList.toggle("active", section.dataset.page === page);
    });

    document.querySelectorAll(".nav-item[data-page]").forEach(function(item) {
        item.classList.toggle("active", item === activeItem);
    });

    if (activeItem) {
        setText("page-title", activeItem.textContent.trim());
    }
}


/* ============================================================
   INITIALIZATION
============================================================ */

function initializeDashboard() {

    if (window.__seafloorDashboardInitialized) {
        return;
    }

    window.__seafloorDashboardInitialized = true;

    console.log(
        "========================================"
    );

    console.log(
        "SEAFLOOR INTELLIGENCE"
    );

    console.log(
        "REAL HARDWARE FRONTEND"
    );

    console.log(
        "ESP32 -> FASTAPI -> DASHBOARD"
    );

    console.log(
        "========================================"
    );


    /*
    ------------------------------------------------------------
    GET FIRST READING IMMEDIATELY
    ------------------------------------------------------------
    */

    fetchTelemetry();


    /*
    ------------------------------------------------------------
    REFRESH SENSOR DATA EVERY SECOND
    ------------------------------------------------------------
    */

    setInterval(
        fetchTelemetry,
        1000
    );


    /*
    ------------------------------------------------------------
    REFRESH HARDWARE STATUS
    ------------------------------------------------------------
    */

    getHardwareData();


    setInterval(
        getHardwareData,
        2000
    );


    /*
    ------------------------------------------------------------
    CLOCK
    ------------------------------------------------------------
    */

    updateClock();

    setInterval(
        updateClock,
        1000
    );


    /*
    ------------------------------------------------------------
    MISSION TIMER
    ------------------------------------------------------------
    */

    updateTimer();

    setInterval(
        updateTimer,
        1000
    );

    const refreshButton = $("refresh-data");

    if (refreshButton) {
        refreshButton.addEventListener("click", fetchTelemetry);
    }

    const connectButton = $("connect-hardware");

    if (connectButton) {
        connectButton.addEventListener("click", async function() {
            const portInput = $("hardware-port");
            const port = portInput && portInput.value.trim()
                ? portInput.value.trim()
                : "COM5";

            try {
                const response = await fetch(
                    "/api/hardware/connect?port=" + encodeURIComponent(port) + "&baudrate=115200",
                    { method: "POST", cache: "no-store" }
                );
                const result = await response.json();
                setText("hardware-message", result.message || "Connection request complete.");
                getHardwareData();
                fetchTelemetry();
            } catch (error) {
                setText("hardware-message", "Unable to connect to " + port + ".");
            }
        });
    }

    const historyButton = $("refresh-history");
    if (historyButton) {
        historyButton.addEventListener("click", fetchHistory);
    }
    fetchHistory().catch(function(error) {
        console.error("History error:", error);
    });

    document.addEventListener("click", function(event) {
        const button = event.target.closest(".nav-item[data-page]");

        if (!button) {
            return;
        }

        event.preventDefault();
        navigateToPage(button.dataset.page, button);
    });
}


/* ============================================================
   START
============================================================ */

if (
    document.readyState === "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initializeDashboard
    );

} else {

    initializeDashboard();
}
