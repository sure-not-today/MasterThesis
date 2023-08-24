import asyncio
import colorama
from dataclasses import dataclass
import math
import csv
import time
import argparse
import random

colorama.init()

whiteboard = []
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
    def __init__(self, pos, name, capacity, aps, method='linear', sigma = 1):
        self.pos = pos
        self.name = name
        self.amount = 0
        self.capacity = capacity
        self.threshold = 0.8*capacity
        self.aps = aps
        self.penalty = 0
        self.threshold_reached = False
        self.pending = False
        self.docked = None
        self.method = method
        self.sigma = sigma
        asyncio.create_task(self.fill())

    async def fill(self):
        add_amount = self.aps
        while True:
            if self.method == 'gauss':
                add_amount = max(random.gauss(self.aps,self.sigma), 0)
            elif self.method == 'fluct':
                add_amount += random.gauss(0,self.sigma)
                if add_amount < 0:
                    add_amount = 0

            future_amount = self.amount + add_amount
            add_penalty = max(future_amount - self.capacity, 0)
            amountAdded = add_amount-add_penalty

            if (future_amount >= self.threshold) and (self.amount < self.threshold):
                self.threshold_reached = True
                whiteboard.append(self)
                print(f"{colorama.Fore.YELLOW}Container {self.name} reached threshold.{colorama.Style.RESET_ALL}")
            elif (future_amount >= self.capacity) and (self.amount < self.capacity):
                print(f"{colorama.Fore.RED}Container {self.name} is full. Collecting penalty.{colorama.Style.RESET_ALL}")

            self.amount += amountAdded
            self.penalty += add_penalty
            if True:
                
                print(f"{colorama.Style.DIM}Container {self.name}: Added amount >> {round(amountAdded,2)} || Added penalty >> {round(add_penalty,2)}{colorama.Style.RESET_ALL}")
                print(f"{colorama.Style.DIM}Container {self.name}: Amount >> {round(self.amount,2)} / {self.capacity} || Penalty >> {round(self.penalty,2)}{colorama.Style.RESET_ALL}")
                print(f"\n")
            await asyncio.sleep(1)

    def dock(self, writer):
        self.docked = writer
    
    async def give_payload(self, space):
        if self.docked:
            payload = min(self.amount, space)
            self.amount -= payload
            msg = f"PAYLOAD_{payload}"
            self.docked.write(msg.encode())
            await self.docked.drain()
            if self.amount < self.threshold:
                self.threshold_reached = False
                whiteboard.remove(self)
        else:
            print("No drone docked. Can't give payload")
            return
        
    def undock(self):
        if self.docked:
            self.docked = None
        else:
            print("Nothing to undock")

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

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"{colorama.Fore.CYAN}{addr} connected{colorama.Style.RESET_ALL}")
    try:
        while True:
            await asyncio.sleep(.1)
            data = await reader.read(1024)
            message = data.decode()

            if message.startswith("REACHED"):
                _ , lat, long, alt, space = message.split("_")
                pos = Position(float(lat), float(long), float(alt))
                cname = pos_to_cont(pos)
                print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}{addr}: reached Container {cname} and empties it.{colorama.Style.RESET_ALL}")
                for container in containers:
                    if cname == container.name:
                        container.dock(writer)
                        await container.give_payload(float(space))
                        container.undock()
                        container.pending = False
            
            elif message.startswith("TASK"):
                loc = extract_pos(message)
                closest_container = None
                min_d = float('inf')

                for container in whiteboard.copy():
                    d = calculate_distance(loc, container.pos)         
                    if d < min_d and not container.pending:
                        print(f"{addr} is {round(d,1)}m away from Container {container.name}")
                        min_d = d
                        closest_container = container

                if closest_container:
                    closest_container.pending = True
                    msg = f"EMPTY_{closest_container.pos.lat}_{closest_container.pos.long}_{closest_container.pos.alt}"
                    writer.write(msg.encode())
                    await writer.drain()
                else:
                    msg = "NO_TASK"
                    writer.write(msg.encode())
                    await writer.drain()
    except asyncio.CancelledError:
        pass
    finally:
        del drones[addr]
        writer.close()

async def main():
    pos1 = Position(47.397186, 8.542156, 500)
    pos2 = Position(47.397792, 8.542395, 500)
    pos3 = Position(47.396850, 8.542915, 500)
    container_a = Container(pos1, "A", 100, 1)
    container_b = Container(pos2, "B", 200, 2, method='gauss', sigma=1)
    container_c = Container(pos3, "C", 300, 3, method='fluct')
    containers.append(container_a)
    containers.append(container_b)
    containers.append(container_c)

    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"{colorama.Fore.YELLOW}Serving on {addr}{colorama.Style.RESET_ALL}")

    if args.log:
        asyncio.create_task(log_containers())

    async with server:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())