import asyncio
import pickle
import colorama
from mavsdk.offboard import PositionNedYaw
from dataclasses import dataclass
import math

colorama.init()

containers = []
drones = {}  # Dictionary to store connected drones

@dataclass
class Position:
    lat: float
    long: float
    alt: float

class Container:
    def __init__(self, pos, name, aps):
        self.pos = pos
        self.amount = 0
        self.name = name
        self.aps = aps
        self.penalty = 0
        self.full_status = False
        self.pending = False
        self.docked = None
        asyncio.create_task(self.fill())

    async def fill(self):
        while True:
            await asyncio.sleep(1)
            if self.amount < 100:
                old_amount = self.amount
                self.amount += self.aps
                if self.amount >= 100:
                    print(f"{colorama.Fore.RED}Container {self.name} is full. Collecting penalty.{colorama.Style.RESET_ALL}")
                if old_amount < 80 and self.amount >= 80:
                    print(f"{colorama.Fore.YELLOW}Container {self.name} reached threshold.{colorama.Style.RESET_ALL}")
            else:
                if self.amount > 100:
                    self.penalty += (self.amount - 100)
                    self.amount = 100
                self.penalty += self.aps

    def dock(self, addr):
        drone = drones[addr]
        d = calculate_distance(drone.pos, self.pos)
        if d < 2:
            self.docked = addr
            print(f"Drone {addr} docked to Container {self.name}.")
        else:
            print(f"Drone {addr} is to far away from Container {self.name} in order to dock.")
            return
    
    async def give_payload(self):
        if self.docked:
            drone = drones[self.docked]
            payload = math.min(self.amount, drone.space)
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


class Drone:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.pos = Position(0,0,0)
        self.idle = False
        self.space = 0

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"{colorama.Fore.CYAN}{addr} connected{colorama.Style.RESET_ALL}")
    drone = Drone(reader, writer)
    drones[addr] = drone

    try:
        while True:
            data = await reader.read(100)
            message = data.decode()

            if message.startswith("STATUS"):
                print(f"Received STATUS from {addr}")
                _ , lat_str, long_str, alt_str, idle_str, space_str = message.split('_')
                drone.pos = Position(float(lat_str), float(long_str), float(alt_str))
                drone.idle = bool(idle_str)
                drone.space = int(space_str)
                print(f"Position: {drone.pos}")
                print(f"Idle: {drone.idle}")
                print(f"Space: {drone.space}")

            elif message.startswith("REACHED"):
                pos = extract_pos(message)
                cname = pos_to_cont(containers, pos)
                print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}{addr}: reached Container {cname} and empties it.{colorama.Style.RESET_ALL}")
                for container in containers:
                    if cname == container.name:
                        container.dock(addr)
                        await container.give_payload()
                        container.undock()
                
            else:
                print(f"Received: {message!r} from {addr!r}")
    except asyncio.CancelledError:
        pass
    finally:
        del drones[addr]
        writer.close()

async def send_task_to_client(addr, task):
    if addr in drones:
        reader, writer = drones[addr]
        try:
            print(f"{colorama.Style.DIM}Sending {task} to client {addr}...{colorama.Style.RESET_ALL}")
            writer.write(task.encode())
            await writer.drain()
            response = await asyncio.wait_for(reader.read(100), timeout=5)
            if response:
                message = response.decode()
                if message == "accept":
                    print(f"{colorama.Fore.GREEN}Client {addr} accepted the {task}.{colorama.Style.RESET_ALL}")
                elif message == "busy":
                    print(f"{colorama.Fore.RED}Client {addr} is busy. Ignoring {task} request.{colorama.Style.RESET_ALL}")
        except asyncio.TimeoutError:
            print(f"{colorama.Fore.RED}Client {addr} did not respond to the {task} request.{colorama.Style.RESET_ALL}")
        except asyncio.CancelledError:
            pass

async def handle_responses():
    while True:
        await asyncio.sleep(.1)  # Adjust this duration as needed

        for addr, (reader, writer, _ ) in drones.copy().items():
            try:
                if writer.can_write_eof():
                    data = await asyncio.wait_for(reader.read(100), timeout=0.1)
                    if data:
                        message = data.decode()
                        if message.startswith("REACHED"):
                            pos = extract_pos(message)
                            cname = pos_to_cont(containers, pos)
                            print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}{addr}: reached Container {cname} and empties it.{colorama.Style.RESET_ALL}")
                            for container in containers:
                                if cname == container.name:
                                    container.amount = 0
                                    container.full_status = False
                                    container.pending = False
                        elif message.startswith("HOME"):
                            print(f"{colorama.Fore.GREEN}{addr}: back Home and idle.{colorama.Style.RESET_ALL}")
                            drones[addr] = (reader,writer,True)
                print("-----------------")  # Line separator after the if-else block
            except asyncio.TimeoutError:
                pass

def pos_to_cont(containers, pos):
    for container in containers:
        if container.pos == pos:
            return container.name
        
def extract_pos(message):
    _ , lat, long, alt = message.split("_")
    pos = [float(lat),float(long),float(alt)]
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
    else:
        print("All drones are busy")

    return closest_drone


async def main():
    pos1 = Position(47.39718698163323, 8.542156062422546, 500)
    pos2 = Position(47.39779268111438, 8.542395102770325, 500)
    pos3 = Position(47.39685021811752, 8.542915525936115, 500)
    container_a = Container(pos1, "A", 1)
    container_b = Container(pos2, "B", 2)
    container_c = Container(pos3, "C", 3)
    containers = [container_a, container_b, container_c]

    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"{colorama.Fore.YELLOW}Serving on {addr}{colorama.Style.RESET_ALL}")

    #asyncio.create_task(handle_responses(containers))

    async with server:
        while True:
            await asyncio.sleep(1)  # Check containers every 1 second

            for container in containers:

                if (container.amount > 80) and not container.pending:

                    closest_drone = get_closest_drone(container, drones)
                    container.pending = True
                    writer = drones[closest_drone].writer
                    msg = f"EMPTY_{container.pos.lat}_{container.pos.long}_{container.pos.alt}"
                    writer.write(msg.encode())
                    await writer.drain()


                    
if __name__ == "__main__":
    asyncio.run(main())
    

