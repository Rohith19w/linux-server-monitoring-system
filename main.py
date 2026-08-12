import json
import sqlite3
import time
import socket
import platform
from datetime import datetime

import psutil
import requests


# ============================================================
# CONFIGURATION
# ============================================================

CONFIG_FILE = "config.json"
DB_FILE = "monitor.db"


# ============================================================
# LOAD CONFIGURATION
# ============================================================

def load_config():

    with open(CONFIG_FILE, "r") as file:
        return json.load(file)


config = load_config()

WINDOWS_SERVER = config.get(
    "windows_server",
    "http://192.168.1.20:8000"
)

# Send live data to Windows every 5 seconds
SEND_INTERVAL = config.get(
    "send_interval",
    5
)

# Save data to SQLite every 60 seconds
DATABASE_INTERVAL = config.get(
    "database_interval",
    60
)

# Keep database records for 7 days
RETENTION_DAYS = config.get(
    "retention_days",
    7
)

CPU_WARNING = config.get(
    "cpu_warning",
    90
)

RAM_WARNING = config.get(
    "ram_warning",
    90
)

DISK_WARNING = config.get(
    "disk_warning",
    90
)


# ============================================================
# DATABASE
# ============================================================

def get_database_connection():

    connection = sqlite3.connect(
        DB_FILE,
        timeout=10
    )

    # Improve concurrent reading/writing
    connection.execute(
        "PRAGMA journal_mode=WAL"
    )

    return connection


def init_database():

    connection = get_database_connection()

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT NOT NULL,

            cpu REAL,

            memory REAL,

            swap REAL,

            disk REAL,

            bytes_sent INTEGER,

            bytes_received INTEGER,

            process_count INTEGER
        )
    """)

    connection.commit()
    connection.close()

    print("Database initialized.")


# ============================================================
# DATABASE CLEANUP
# ============================================================

def cleanup_old_data():

    try:

        connection = get_database_connection()

        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM metrics
            WHERE timestamp <
            datetime('now', ?)
        """, (
            f"-{RETENTION_DAYS} days",
        ))

        deleted_rows = cursor.rowcount

        connection.commit()
        connection.close()

        if deleted_rows > 0:

            print(
                f"Database cleanup: "
                f"deleted {deleted_rows} old records."
            )

    except sqlite3.Error as error:

        print(
            "Database cleanup error:",
            error
        )


# ============================================================
# CPU
# ============================================================

def get_cpu():

    return psutil.cpu_percent(
        interval=1
    )


# ============================================================
# MEMORY
# ============================================================

def get_memory():

    memory = psutil.virtual_memory()

    return {

        "percent": memory.percent,

        "total": memory.total,

        "used": memory.used,

        "available": memory.available
    }


# ============================================================
# SWAP
# ============================================================

def get_swap():

    swap = psutil.swap_memory()

    return {

        "percent": swap.percent,

        "total": swap.total,

        "used": swap.used,

        "free": swap.free
    }


# ============================================================
# DISK SPACE
# ============================================================

def get_disk():

    disk = psutil.disk_usage("/")

    return {

        "percent": disk.percent,

        "total": disk.total,

        "used": disk.used,

        "free": disk.free
    }


# ============================================================
# DISK I/O
# ============================================================

def get_disk_io():

    io = psutil.disk_io_counters()

    if io is None:

        return {

            "read_bytes": 0,

            "write_bytes": 0
        }

    return {

        "read_bytes": io.read_bytes,

        "write_bytes": io.write_bytes
    }


# ============================================================
# NETWORK
# ============================================================

def get_network():

    network = psutil.net_io_counters()

    return {

        "bytes_sent": network.bytes_sent,

        "bytes_received": network.bytes_recv
    }


# ============================================================
# PROCESSES
# ============================================================

def get_processes():

    processes = []

    for process in psutil.process_iter(
        [
            "pid",
            "name",
            "cpu_percent",
            "memory_percent"
        ]
    ):

        try:

            info = process.info

            processes.append({

                "pid": info["pid"],

                "name": info["name"],

                "cpu": info["cpu_percent"] or 0,

                "memory": info["memory_percent"] or 0
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess
        ):

            continue

    # Highest CPU first
    processes.sort(
        key=lambda x: x["cpu"],
        reverse=True
    )

    # Only send top 10
    return processes[:10]


# ============================================================
# LOGGED-IN USERS
# ============================================================

def get_users():

    users = []

    for user in psutil.users():

        users.append({

            "name": user.name,

            "terminal": user.terminal,

            "host": user.host
        })

    return users


# ============================================================
# UPTIME
# ============================================================

def get_uptime():

    boot_time = psutil.boot_time()

    boot_datetime = datetime.fromtimestamp(
        boot_time
    )

    uptime_seconds = (
        time.time() - boot_time
    )

    return {

        "boot_time":
            boot_datetime.isoformat(),

        "uptime_seconds":
            int(uptime_seconds)
    }


# ============================================================
# ALERT SYSTEM
# ============================================================

def generate_alerts(data):

    alerts = []

    # CPU
    if data["cpu"] >= CPU_WARNING:

        alerts.append({

            "severity": "WARNING",

            "type": "CPU",

            "message":
                f"CPU usage is "
                f"{data['cpu']}%"
        })


    # RAM
    if data["memory"] >= RAM_WARNING:

        alerts.append({

            "severity": "WARNING",

            "type": "MEMORY",

            "message":
                f"RAM usage is "
                f"{data['memory']}%"
        })


    # Disk
    if data["disk"] >= DISK_WARNING:

        alerts.append({

            "severity": "CRITICAL",

            "type": "DISK",

            "message":
                f"Disk usage is "
                f"{data['disk']}%"
        })


    return alerts


# ============================================================
# COLLECT ALL METRICS
# ============================================================

def collect_metrics():

    memory = get_memory()

    swap = get_swap()

    disk = get_disk()

    disk_io = get_disk_io()

    network = get_network()

    processes = get_processes()

    users = get_users()

    uptime = get_uptime()

    data = {

        "hostname":
            socket.gethostname(),

        "timestamp":
            datetime.now().isoformat(),

        "os":
            platform.platform(),

        "cpu":
            get_cpu(),

        "memory":
            memory["percent"],

        "memory_total":
            memory["total"],

        "memory_used":
            memory["used"],

        "memory_available":
            memory["available"],

        "swap":
            swap["percent"],

        "swap_total":
            swap["total"],

        "swap_used":
            swap["used"],

        "disk":
            disk["percent"],

        "disk_total":
            disk["total"],

        "disk_used":
            disk["used"],

        "disk_free":
            disk["free"],

        "disk_io":
            disk_io,

        "network":
            network,

        "process_count":
            len(psutil.pids()),

        "processes":
            processes,

        "users":
            users,

        "uptime":
            uptime
    }

    # Generate alerts
    data["alerts"] = generate_alerts(
        data
    )

    return data


# ============================================================
# SAVE METRICS TO SQLITE
# ============================================================

def save_metrics(data):

    try:

        connection = get_database_connection()

        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO metrics (

                timestamp,

                cpu,

                memory,

                swap,

                disk,

                bytes_sent,

                bytes_received,

                process_count

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            data["timestamp"],

            data["cpu"],

            data["memory"],

            data["swap"],

            data["disk"],

            data["network"]["bytes_sent"],

            data["network"]["bytes_received"],

            data["process_count"]
        ))

        connection.commit()

        connection.close()

    except sqlite3.Error as error:

        print(
            "Database save error:",
            error
        )


# ============================================================
# SEND DATA TO WINDOWS
# ============================================================

def send_to_windows(data):

    try:

        response = requests.post(

            f"{WINDOWS_SERVER}/api/metrics",

            json=data,

            timeout=3
        )

        if response.status_code == 200:

            print(
                "Data sent to Windows."
            )

        else:

            print(
                "Windows returned:",
                response.status_code
            )

    except requests.RequestException as error:

        print(
            "Windows server unavailable:",
            error
        )


# ============================================================
# DISPLAY STATUS
# ============================================================

def print_status(data):

    print(
        f"[{data['timestamp']}] "
        f"CPU: {data['cpu']}% | "
        f"RAM: {data['memory']}% | "
        f"Disk: {data['disk']}% | "
        f"Processes: {data['process_count']}"
    )

    # Display alerts
    for alert in data["alerts"]:

        print(
            f"[ALERT] "
            f"{alert['severity']} - "
            f"{alert['message']}"
        )


# ============================================================
# MAIN MONITORING LOOP
# ============================================================

def main():

    print(
        "===================================="
    )

    print(
        "Linux Monitoring Agent Started"
    )

    print(
        "===================================="
    )

    print(
        f"Windows server: {WINDOWS_SERVER}"
    )

    print(
        f"Live interval: {SEND_INTERVAL}s"
    )

    print(
        f"Database interval: {DATABASE_INTERVAL}s"
    )

    print(
        f"Database retention: {RETENTION_DAYS} days"
    )

    print()

    # Create database
    init_database()

    # Timers
    last_database_save = 0

    last_cleanup = 0

    while True:

        try:

            # ==========================================
            # COLLECT
            # ==========================================

            data = collect_metrics()


            # ==========================================
            # DISPLAY
            # ==========================================

            print_status(data)


            # ==========================================
            # SEND TO WINDOWS
            # ==========================================

            send_to_windows(data)


            # ==========================================
            # DATABASE
            # ==========================================

            current_time = time.time()

            if (
                current_time
                - last_database_save
                >= DATABASE_INTERVAL
            ):

                save_metrics(data)

                last_database_save = current_time

                print(
                    "Metrics saved to database."
                )


            # ==========================================
            # CLEANUP DATABASE
            # ==========================================

            if (
                current_time
                - last_cleanup
                >= 3600
            ):

                cleanup_old_data()

                last_cleanup = current_time


            # ==========================================
            # WAIT
            # ==========================================

            time.sleep(
                SEND_INTERVAL
            )


        except KeyboardInterrupt:

            print(
                "\nMonitoring agent stopped."
            )

            break


        except Exception as error:

            print(
                "Monitoring error:",
                error
            )

            # Don't crash the monitoring service
            time.sleep(5)


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()