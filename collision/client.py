import asyncio
from mavsdk import System
import argparse
from dataclasses import dataclass
import colorama
import csv
import time
from mavsdk.telemetry import LandedState


colorama.init()
queue = asyncio.Queue()

@dataclass
class Position:
    lat: float
    long: float
    alt: float

@dataclass
class Status:
    pos: Position
    goal: Position
    idle: bool
    payload: float
    capacity: float
    landed_state: LandedState

class PausableTask():
    def __init__(self, pause_event) -> None:
        pass

parser = argparse.ArgumentParser()
parser.add_argument('-n', '--n', nargs='?', const=1, type=int, default=1)
parser.add_argument('--log', action='store_true', help='Enable logging')
args = parser.parse_args()

n = args.n - 1
p1 = 50050 + n
p2 = 14540 + n
udp = f"udp://:{p2}"

csvfile_path = f"dronelog{args.n}.csv"

def approx_same(f1,f2, tol):
    delta = abs((f1 - f2))
    if delta < tol:
        return True
    else:
        return False

async def status_update(drone, writer):
    if args.log:
        csvfile = open(csvfile_path, "w+", newline='')
        csv_writer = csv.writer(csvfile)
    while True:
        position = await drone.telemetry.position().__aiter__().__anext__()
        lat = round(position.latitude_deg, 5)
        long = round(position.longitude_deg, 5)
        alt = round(position.absolute_altitude_m, 1)
        loc = Position(lat,long,alt)
        status.pos = loc
        status.landed_state = await drone.telemetry.landed_state().__aiter__().__anext__()
        space = status.capacity - status.payload
        msg = f"STATUS_{status.pos.lat}_{status.pos.long}_{status.pos.alt}_{status.idle}_{space}"
        await queue.put(msg)
        if args.log:
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            csv_writer.writerow([current_time, status.pos, status.idle, status.payload])
        await asyncio.sleep(1)

async def pos_reached(pos):
    
    while True:
        lat_reached = approx_same(status.pos.lat, pos.lat, 1e-5)
        long_reached = approx_same(status.pos.long, pos.long, 1e-5)
        alt_reached = approx_same(status.pos.alt, pos.alt, 5e-1)
        if False:
            print("from " + str(status.pos.lat) + " to " + str(pos.lat) + ": " + str(lat_reached))
            print("from " + str(status.pos.long) + " to " + str(pos.long) + ": " + str(long_reached))
            print("from " + str(status.pos.alt) + " to " + str(pos.alt) + ": " + str(alt_reached))
        if lat_reached & long_reached & alt_reached:
            print("Reached location.")
            return
        else:
            await asyncio.sleep(1)

async def takeoff(drone):
    await drone.action.arm()
    await drone.action.takeoff()
    while (not (status.landed_state == LandedState(2))):
        await asyncio.sleep(1)

async def goto(drone, pos):  
    await drone.action.goto_location(pos.lat, pos.long, pos.alt, 0)
    await pos_reached(pos)

async def land(drone):
    await drone.action.land()
    while (not (status.landed_state == LandedState(1))):
        await asyncio.sleep(1)
    await drone.action.disarm()

async def move_to(drone):
    lat_reached = approx_same(status.pos.lat, status.goal.lat, 1e-5)
    long_reached = approx_same(status.pos.long, status.goal.long, 1e-5)
    if lat_reached & long_reached:
        print("Already there")
    else:
        await takeoff(drone)
        await goto(drone, status.goal)
        await land(drone)

    msg = f"REACHED_{status.goal.lat}_{status.goal.long}_{status.goal.alt}"
    await queue.put(msg)
    status.goal = None

async def return_home(drone):
    if status.payload > 0.8*status.capacity:
        print("Returning home")
        await takeoff(drone)
        await goto(drone, home)
        await land(drone)
        await asyncio.sleep(5)
        print("Setting payload to zero")
        status.payload = 0

    print("Setting idle")
    status.idle = True

async def send_msg(writer, msg):
    writer.write(msg.encode())
    await writer.drain()

async def writing(writer):
    while True:
        msg = await queue.get()
        await send_msg(writer, msg)
        await asyncio.sleep(0)

async def main():

    global status
    status = Status(Position(0,0,0), Position(0,0,0), True, 0, 1000, LandedState(0))

    drone = System(port=p1)
    await drone.connect(system_address=udp)

    global home
    home = Position(47.39728341067808, 8.542641053423798, 500)
    

    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"-- Connected to drone!")
            break

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("-- Global position state is good enough for flying.")
            break


    reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
    print(f"{colorama.Fore.GREEN}Connected to server.{colorama.Style.RESET_ALL}")
    
    task_status = asyncio.create_task(status_update(drone, writer))
    task_writer = asyncio.create_task(writing(writer))
    drone_name = chr(ord('A') + n)
    print(f"Hello I am Drone {drone_name}")
    await asyncio.sleep(2)

    current_task = None

    while True:
        msg = await reader.read(1024)
        message = msg.decode()

        if message.startswith("EMPTY"):
            t0 = asyncio.get_event_loop().time()
            status.idle = False
            print("Received task to empty container")
            _ , lat, long, alt = message.split("_")
            status.goal = Position(float(lat), float(long), float(alt))

            current_task = asyncio.create_task(move_to(drone), name="move")

            

        elif message.startswith("PAYLOAD"):
            _ , amount, penalty, received_payload, name = message.split("_")           
            status.payload += float(received_payload)
            te = asyncio.get_event_loop().time()
            time = round(te-t0, 1)
            print(f"Received {received_payload} units of Payload after {time} seconds from Container {name}")
            msg = f"INFO_{time}_{amount}_{penalty}_{received_payload}_{name}"
            await queue.put(msg)
            
            current_task = asyncio.create_task(return_home(drone), name="home")
        
        elif message.startswith("PAUSE"):
            task_name = None
            if current_task:
                current_task.cancel()
                await drone.action.hold()
                task_name = current_task.get_name()
            await asyncio.sleep(10)
            if task_name == "move":
                current_task = asyncio.create_task(move_to(drone))
            elif task_name == "home":
                current_task = asyncio.create_task(return_home(drone))
        
        elif message.startswith("STOP"):
            await land(drone)
            break
        
        await asyncio.sleep(0)

if __name__ == "__main__":
    asyncio.run(main())