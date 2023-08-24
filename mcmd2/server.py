import asyncio
import colorama
from mavsdk.offboard import PositionNedYaw
from dataclasses import dataclass
import math
import csv
import time
import argparse
import random

colorama.init()

containers = []
drones = {}  # Dictionary to store connected drones
csvfile_path = "container_log.csv"

@dataclass
class Position:
    lat: float
    long: float
    alt: float

parser = argparse.ArgumentParser()
parser.add_argument('--log', action='store_true', help='Enable logging')
args = parser.parse_args()

class Container:
    def __init__(self, pos, name, capacity, aps):
        self.pos = pos
        self.name = name
        self.amount = 0
        self.capacity = capacity
        self.aps = aps
        self.penalty = 0
        self.full_status = False
        self.pending = False
        self.docked = None
        asyncio.create_task(self.fill())

    async def fill(self):
        while True:
            await asyncio.sleep(1)
            if self.amount < self.capacity:
                old_amount = self.amount
                self.amount += random.gauss(self.aps,3)
                if self.amount >= self.capacity:
                    print(f"{colorama.Fore.RED}Container {self.name} is full. Collecting penalty.{colorama.Style.RESET_ALL}")
                if old_amount < self.capacity*0.8 and self.amount >= self.capacity*0.8:
                    print(f"{colorama.Fore.YELLOW}Container {self.name} reached threshold.{colorama.Style.RESET_ALL}")
            else:
                if self.amount > self.capacity:
                    self.penalty += (self.amount - self.capacity)
                    self.amount = self.capacity
                self.penalty += random.gauss(self.aps,3)

    def dock(self, addr):
        drone = drones[addr]
        if self.name == drone.atcont:
            self.docked = addr
            print(f"Drone {addr} docked to Container {self.name}.")
        else:
            print(f"Drone {addr} is to far away from Container {self.name} in order to dock.")
            return
    
    async def give_payload(self):
        if self.docked:
            drone = drones[self.docked]
            payload = min(self.amount, drone.space)
            self.amount -= payload
            msg = f"PAYLOAD_{payload}"
            drone.writer.write(msg.encode())
            await drone.writer.drain()
        else:
            print("No drone docked. Can't give payload")
            return
        
    def undock(self):
        if self.docked:
            self.docked = None
        else:
            print("Nothing to undock")

def str_to_bool(string):
    if string == "True":
        return True
    elif string == "False":
        return False
    else:
        raise NameError

class Drone:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.pos = Position(0,0,0)
        self.idle = False
        self.space = 0
        self.atcont = None

def equal_position(pos1,pos2):
    latb = round(pos1.lat,4) == round(pos2.lat,4)
    longb = round(pos1.long,4) == round(pos2.long,4)
    altb = round(pos1.alt,4) == round(pos2.alt,4)
    if latb and longb and altb:
        return True
    else:
        return False

def pos_to_cont(pos):
    for container in containers:
        print(f"Checking Container {container.name}")
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

def get_closest_drone(container, drones):
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
    addr = writer.get_extra_info('peername')
    print(f"{colorama.Fore.CYAN}{addr} connected{colorama.Style.RESET_ALL}")
    drone = Drone(reader, writer)
    drones[addr] = drone

    try:
        while True:
            await asyncio.sleep(.1)
            data = await reader.read(100)
            message = data.decode()
            if message.startswith("STATUS"):              
                _ , lat_str, long_str, alt_str, idle_str, space_str = message.split('_')
                drone.pos = Position(float(lat_str), float(long_str), float(alt_str))
                drone.idle = str_to_bool(idle_str)
                drone.space = int(space_str)
                if False:
                    print(f"Received STATUS from {addr}")
                    print(f"Position: {drone.pos}")
                    print(f"Idle: {drone.idle}")
                    print(f"Space: {drone.space}")

            elif message.startswith("REACHED"):
                print(message)
                pos = extract_pos(message)
                cname = pos_to_cont(pos)
                print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}{addr}: reached Container {cname} and empties it.{colorama.Style.RESET_ALL}")
                for container in containers:
                    if cname == container.name:
                        drone.atcont = cname
                        print(drones[addr].atcont)
                        container.dock(addr)
                        await container.give_payload()
                        container.undock()
                        container.pending = False
                
            else:
                print(f"Received: {message!r} from {addr!r}")
    except asyncio.CancelledError:
        pass
    finally:
        del drones[addr]
        writer.close()

async def log_containers():
    with open(csvfile_path, "w+", newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        while True:
            amounts = []
            penalties = []
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            for container in containers:
                amounts.append(container.amount)
                penalties.append(container.penalty)
            csv_writer.writerow([current_time, amounts, penalties])
            await asyncio.sleep(1)

async def main():
    pos1 = Position(47.39718698163323, 8.542156062422546, 500)
    pos2 = Position(47.39779268111438, 8.542395102770325, 500)
    pos3 = Position(47.39685021811752, 8.542915525936115, 500)
    container_a = Container(pos1, "A", 100, 1)
    container_b = Container(pos2, "B", 200, 2)
    container_c = Container(pos3, "C", 300, 3)
    containers.append(container_a)
    containers.append(container_b)
    containers.append(container_c)

    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"{colorama.Fore.YELLOW}Serving on {addr}{colorama.Style.RESET_ALL}")

    if args.log:
        asyncio.create_task(log_containers())

    async with server:
        while True:
            await asyncio.sleep(5)  # Check containers every 1 second

            for container in containers:

                if (container.amount > container.capacity*0.8) and not container.pending:

                    closest_drone = get_closest_drone(container, drones)
                    if closest_drone == None:
                        continue
                    container.pending = True
                    writer = drones[closest_drone].writer
                    msg = f"EMPTY_{container.pos.lat}_{container.pos.long}_{container.pos.alt}"
                    writer.write(msg.encode())
                    await writer.drain()
                    await asyncio.sleep(1)


                    
if __name__ == "__main__":
    asyncio.run(main())
    

