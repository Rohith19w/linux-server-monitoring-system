import psutil as p
import json
RAM_WARNING=90
CPU_WARNING=90
def conf():
    with open("config.json","r") as file:
        return json.load(file)
config = conf()
cpu_threshold=config.get("cpu_warning",90)
disk_threshold=config.get("disk_warning",90)
vm_threshold= config.get("vm_warning",90)
print(cpu_threshold)



def get_cpu():
    return p.cpu_percent(
        interval = 3
    )

def get_vm():
    d=p.virtual_memory()
    return {
        "percent":d.percent,
        "total":d.total,
        "used":d.used,
        "availale":d.available
    }

def get_disk():
    Disk=p.disk_usage("/")
    return {
        "percent":Disk.percent,
        "used":Disk.used,
        "total":Disk.total,
        "free":Disk.free
    }
def get_swap():
    swap=p.swap_memory()
    return{
        "percent":swap.percent,
        "used":swap.used,
        "total":swap.total,
        "free":swap.free
    }


def get_users():
    users = []
    for i in p.users():
        users.append({
            "name": user.name,

            "terminal": user.terminal,

            "host": user.host
        })

    return users
def get_processes():

    processes = []

    for process in p.process_iter(
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
            p.NoSuchProcess,
            p.AccessDenied,
            p.ZombieProcess
        ):

            continue
    processes.sort(
        key=lambda x: x["cpu"],
        reverse=True
    )
    return processes[:10]
def generate_alerts(data):

    alerts = []
    if data["cpu"] >= CPU_WARNING:

        alerts.append({

            "severity": "WARNING",

            "type": "CPU",

            "message":
                f"CPU usage is "
                f"{data['cpu']}%"
        })

    if data["memory"] >= RAM_WARNING:

        alerts.append({

            "severity": "WARNING",

            "type": "MEMORY",

            "message":
                f"RAM usage is "
                f"{data['memory']}%"
        })
print(generate_alerts(cpu_threshold))
def collect_metrics():

    memory = get_memory()

    swap = get_swap()

    disk = get_disk()

    #disk_io = get_disk_io()

    #network = get_network()

    processes = get_processes()

    users = get_users()

    #uptime = get_uptime()

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

    data["alerts"] = generate_alerts(
        data
    )

    return data


