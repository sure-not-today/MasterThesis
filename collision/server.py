import sys
import os
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from container import RContainer, SContainer
import asyncio
import colorama
from dataclasses import dataclass
import math
import csv
import time
import argparse
import tkinter as tk
from tkinter import ttk

colorama.init()

containers = []
sconts = {}
drones = {}  # Dictionary to store connected drones
csvfile_path_real = "rcontainer_log.csv"
csvfile_path_sim = "scontainer_log.csv"
drone_n = 0

@dataclass
class Position:
    lat: float
    long: float
    alt: float

parser = argparse.ArgumentParser()
parser.add_argument('--log', action='store_true', help='Enable logging')
args = parser.parse_args()

def str_to_bool(string: str) -> bool:
    if string == "True":
        return True
    elif string == "False":
        return False
    else:
        raise NameError

class Drone:
    def __init__(self, reader, writer, name):
        self.reader = reader
        self.writer = writer
        self.name = name
        self.pos = Position(0,0,0)
        self.idle = False
        self.space = 0
        self.atcont = None

    async def stop(self):
        self.writer.write("STOP".encode())
        await self.writer.drain()

    async def pause(self):
        self.writer.write("PAUSE".encode())
        await self.writer.drain()

def equal_position(pos1: Position, pos2: Position) -> bool:
    latb = round(pos1.lat,4) == round(pos2.lat,4)
    longb = round(pos1.long,4) == round(pos2.long,4)
    altb = round(pos1.alt,4) == round(pos2.alt,4)
    if latb and longb and altb:
        return True
    else:
        return False

def pos_to_cont(pos):
    for container in containers:
        if equal_position(container.pos, pos):
            return container.name
        
def extract_pos(message):
    _ , lat, long, alt = message.split("_")
    pos = Position(float(lat), float(long), float(alt))
    return pos

def calculate_distance(p1, p2):
    dlat = (p1.lat - p2.lat)
    dlong = (p1.long - p2.long)
    dist = (math.sqrt(dlat**2 + dlong**2))*111139
    return dist

def get_closest_drone(container):
    closest_drone = None
    min_d = float('inf')

    for addr, drone in drones.copy().items():
        if drone.idle:
            d = calculate_distance(drone.pos, container.pos)
            print(f"{addr} is {round(d,1)}m away from Container {container.name}")
            if d < min_d:
                min_d = d
                closest_drone = addr
    if closest_drone:
        print(f"Closest drone to Container {container.name} is {closest_drone} with a distance of {round(min_d,1)}")

    return closest_drone

async def handle_client(reader, writer):
    global drone_n
    drone_n += 1
    drone_name = chr(ord('A') + (drone_n-1))
    addr = writer.get_extra_info('peername')
    print(f"{colorama.Fore.CYAN}{addr} connected as Drone {drone_name}{colorama.Style.RESET_ALL}")
    drone = Drone(reader, writer, drone_name)
    drones[addr] = drone

    try:
        while True:
            await asyncio.sleep(.1)
            data = await reader.read(1024)
            message = data.decode()
            if message.startswith("STATUS"):
                _ , lat_str, long_str, alt_str, idle_str, space_str = message.split('_')
                drone.pos = Position(float(lat_str), float(long_str), float(alt_str))
                drone.idle = str_to_bool(idle_str)
                drone.space = float(space_str)
                if False:
                    print(f"Received STATUS from {addr}")
                    print(f"Position: {drone.pos}")
                    print(f"Idle: {drone.idle}")
                    print(f"Space: {drone.space}")

            elif message.startswith("REACHED"):
                pos = extract_pos(message)
                cname = pos_to_cont(pos)
                print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}{addr}: reached Container {cname} and empties it.{colorama.Style.RESET_ALL}")
                for container in containers:
                    if cname == container.name:
                        drone.atcont = cname
                        container.dock(drone)
                        await container.give_payload()
                        container.undock()
                        sconts[cname].pending = False
            
            elif message.startswith("INFO"):
                _ ,time, amount, penalty, removed, name = message.split('_')
                print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}{addr} has INFO of Container {name}.{colorama.Style.RESET_ALL}")
                t = asyncio.get_event_loop().time()
                data = (t, float(amount), float(penalty), float(removed), float(time))
                sconts[name].new_data(data)
            else:
                print(f"Received: {message!r} from {addr!r}")
                break
    except asyncio.CancelledError:
        pass
    finally:
        print(f"{colorama.Fore.CYAN}{addr} disconnected!{colorama.Style.RESET_ALL}")
        del drones[addr]
        writer.close()

async def log_containers():
    with open(csvfile_path_real, "w+", newline='') as csvfile_real, open(csvfile_path_sim, "w+", newline='') as csvfile_sim:
        csv_writer_real = csv.writer(csvfile_real)
        csv_writer_sim = csv.writer(csvfile_sim)
        while True:
            amounts = []
            samounts = []
            penalties = []
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            for container in containers:
                amounts.append(container.amount)
                penalties.append(container.penalty)
            for scont in sconts.values():
                samounts.append(scont.amount)
            csv_writer_real.writerow([current_time, amounts, penalties])
            csv_writer_sim.writerow([current_time, samounts])
            await asyncio.sleep(1)

def get_crit_container():
    prio = float("inf")
    crit_c = None
    for c in sconts.values():
        if not c.pending:
            if c.n < prio and not c.capped:
                prio = c.n
                crit_c = c
            elif c.capped and (c.amount >= c.threshold):
                crit_c = c
    return crit_c

def get_crit_container2():
    for container in sconts.values():
        if container.n == 0 and not container.pending:
            return container
        
    for container in sconts.values():
        if container.n == 1 and not container.pending:
            return container
        
    for container in sconts.values():
        if not container.capped and not container.locked and not container.pending:
            return container

    for container in sconts.values():
        if container.capped and container.amount >= container.threshold and not container.pending:
            return container

    for container in sconts.values():
        for drone in drones:
            if drone.space <= container.amount and not container.pending:
                return container

def get_crit_container3():
    crit_c = None
    prio = float("inf")
    for container in sconts.values():
        if not container.pending:
            if container.capped and container.n > 2:
                if container.amount >= container.threshold:
                    crit_c = container
            else:
                if not container.locked:
                    if container.n < prio:
                        prio = container.n
                        crit_c = container

    return crit_c


def compare_dict_keys(dict1, dict2):
    # Find keys unique to dict1
    keys_only_in_dict1 = set(dict1.keys()) - set(dict2.keys())
    
    # Find keys unique to dict2
    keys_only_in_dict2 = set(dict2.keys()) - set(dict1.keys())
    
    return (keys_only_in_dict1, keys_only_in_dict2)

async def gui():
    root = tk.Tk()
    root.title("Container Simulation")

    frame_RC = tk.Frame(master=root, relief=tk.RIDGE, borderwidth=5)
    frame_SC = tk.Frame(master=root, relief=tk.RIDGE, borderwidth=5)
    frame_D = tk.Frame(master=root, relief=tk.RIDGE, borderwidth=5)

    frame_RC.grid(row=0, column=0, padx=10, pady=10)
    frame_SC.grid(row=0, column=1, padx=10, pady=10)
    frame_D.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    # REAL CONTAINERS
    real_label = {}
    real_progress_bars = {}
    penalty_floats = {}

    tk.Label(frame_RC, text="Real Containers").pack()
    rc_amount_frame = tk.Frame(frame_RC)
    rc_amount_frame.pack(side="left", padx=10, pady=10)

    penalty_frame = tk.Frame(frame_RC)
    penalty_frame.pack(side="right", padx=10, pady=10)

    for i, container in enumerate(containers):
        label = tk.Label(rc_amount_frame, text=f"{container.name} Amount: {container.amount} / {container.capacity}")
        label.pack()

        progress_bar = ttk.Progressbar(rc_amount_frame, orient="horizontal", mode="determinate", length=200)
        progress_bar.pack()

        penalty_label = tk.Label(penalty_frame, text=f"{container.name} Penalty:")
        penalty_label.pack()

        penalty_float = tk.Label(penalty_frame, text=str(container.penalty))
        penalty_float.pack()

        real_label[i] = label
        real_progress_bars[i] = progress_bar
        penalty_floats[i] = penalty_float
    
    # SIMULATED CONTAINERS
    simulated_labels = {}
    simulated_progress_bars = {}
    indicators = {}

    tk.Label(frame_SC, text="Simulated Containers").pack()
    sc_amount_frame = tk.Frame(frame_SC)
    sc_amount_frame.pack(side="left", padx=10, pady=10)

    si_frame = tk.Frame(frame_SC)
    si_frame.pack(side="right", padx=10, pady=10)
    
    for i, container in enumerate(sconts.values()):
        label = tk.Label(sc_amount_frame, text=f"{container.name} Amount: {container.amount} / {container.capacity}")
        label.pack()

        progress_bar = ttk.Progressbar(sc_amount_frame, orient="horizontal", mode="determinate", length=200)
        progress_bar.pack()

        indicator_label = tk.Label(si_frame, text=f"{container.name} Status:")
        indicator_label.pack()

        indicator = tk.Label(si_frame, text="Pending", bg="yellow", width=10)
        indicator.pack()

        simulated_labels[i] = label
        simulated_progress_bars[i] = progress_bar
        indicators[i] = indicator

    # DRONES
    tk.Label(frame_D, text="Drones").pack()

    try:
        clients_gui = {}
        drone_labels = {}
        drone_progress_bars = {}
        drone_indicators = {}
        while True:
            add_to_gui, remove_from_gui = compare_dict_keys(drones, clients_gui)
            for addr in add_to_gui:
                drone = drones[addr]
                frame = tk.Frame(frame_D)
                frame.pack()

                label = tk.Label(frame, text=f"{drone.name} Space: {drone.space}")
                label.grid(row=0, column=0, padx=10)

                progress_bar = ttk.Progressbar(frame, orient="horizontal", mode="determinate", length=200)
                progress_bar.grid(row=1, column=0, padx=10, pady=10)

                indicator_label = tk.Label(frame, text=f"{drone.name} Status:")
                indicator_label.grid(row=0, column=1, padx=10)

                indicator = tk.Label(frame, text="Idle", bg="green", width=10)
                indicator.grid(row=1, column=1, padx=10, pady=10)

                stop_button = tk.Button(frame, text="STOP", command=lambda: asyncio.create_task(drone.stop()))
                stop_button.grid(row=0, column=2, rowspan=2, padx=10)

                pause_button = tk.Button(frame, text="PAUSE", command=lambda: asyncio.create_task(drone.pause()))
                pause_button.grid(row=0, column=3, rowspan=2, padx=10)

                clients_gui[addr] = (frame, label, progress_bar, indicator, stop_button)

            for addr in remove_from_gui:
                frame, _, _, _, _= clients_gui.pop(addr)
                frame.pack_forget()

            for i, container in enumerate(containers):
                real_label[i]["text"] = f"{container.name} Amount: {container.amount} / {container.capacity}"
                real_progress_bars[i]["value"] = (container.amount / container.capacity) * 100
                penalty_floats[i]["text"] = container.penalty

            for i, container in enumerate(sconts.values()):
                simulated_labels[i]["text"] = f"{container.name} Amount: {round(container.amount,0)} / {container.capacity}"
                simulated_progress_bars[i]["value"] = (container.amount / container.capacity) * 100
                if container.pending:
                    indicators[i]["text"] = "Pending"
                    indicators[i]["bg"] = "yellow"
                elif container.locked:
                    indicators[i]["text"] = "Locked"
                    indicators[i]["bg"] = "red"
                elif container.capacity == float("inf"):
                    indicators[i]["text"] = "inf"
                    indicators[i]["bg"] = "blue"
                else:
                    indicators[i]["text"] = "Filling"
                    indicators[i]["bg"] = "green"

            for addr in clients_gui:
                _ , label, _, indicator, button = clients_gui[addr]
                drone = drones[addr]
                label["text"] = f"{drone.name} Space: {drone.space}"
                if drone.idle:
                    indicator["text"] = "Idle"
                    indicator["bg"] = "green"
                else:
                    indicator["text"] = "Busy"
                    indicator["bg"] = "red"   

                button["command"] = lambda: asyncio.create_task(drone.stop())              

            root.update()  # Update the GUI
            await asyncio.sleep(0.01)  # Yield control to asyncio event loop
    except tk.TclError:
        print("Why would you close the GUI?!")

async def main():
    pos1 = Position(47.39718698163323, 8.542156062422546, 500)
    pos2 = Position(47.39779268111438, 8.542395102770325, 500)
    pos3 = Position(47.39685021811752, 8.542915525936115, 500)
    cont_print = False
    container_a = RContainer(pos1, "A", 100, 1, method="poisson", sigma=2, print_to_cmd=cont_print)
    container_b = RContainer(pos2, "B", 200, 2.2, method="poisson", sigma=2, print_to_cmd=cont_print)
    container_c = RContainer(pos3, "C", 300, 3.6, method="poisson", sigma=2, print_to_cmd=cont_print)
    containers.append(container_a)
    containers.append(container_b)
    containers.append(container_c)
    cont_print = False
    scont_a = SContainer(pos1, "A", print_to_cmd=cont_print)
    scont_b = SContainer(pos2, "B", print_to_cmd=cont_print)
    scont_c = SContainer(pos3, "C", print_to_cmd=cont_print)
    sconts[container_a.name]=scont_a
    sconts[container_b.name]=scont_b
    sconts[container_c.name]=scont_c

    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"{colorama.Fore.YELLOW}Serving on {addr}{colorama.Style.RESET_ALL}")
    gui_task = asyncio.create_task(gui())
    if args.log:
        asyncio.create_task(log_containers())
    async with server:
        t0 = asyncio.get_event_loop().time()
        while True:
            container = get_crit_container3()
            if container:
                closest_drone = get_closest_drone(container)
                if closest_drone:
                    container.pending = True
                    drones[closest_drone].idle = False
                    writer = drones[closest_drone].writer
                    msg = f"EMPTY_{container.pos.lat}_{container.pos.long}_{container.pos.alt}"
                    print(msg)
                    writer.write(msg.encode())
                    await writer.drain()
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())