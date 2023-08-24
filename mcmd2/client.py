import asyncio
from mavsdk import System
import argparse
from dataclasses import dataclass
import colorama
import csv
import time
from mavsdk.telemetry import LandedState


colorama.init()

@dataclass
class Position:
    lat: float
    long: float
    alt: float

parser = argparse.ArgumentParser()
parser.add_argument('-n', '--n', nargs='?', const=1, type=int, default=1)
parser.add_argument('--log', action='store_true', help='Enable logging')
args = parser.parse_args()

n = args.n - 1
p1 = 50050 + n
p2 = 14540 + n
udp = f"udp://:{p2}"

csvfile_path = f"dronelog{args.n}.csv"

def get_space():
    return (capacity - payload)

async def get_position(drone):
    global loc
    global state
    position = await drone.telemetry.position().__aiter__().__anext__()
    state = await drone.telemetry.landed_state().__aiter__().__anext__()
    lat = round(position.latitude_deg, 5)
    long = round(position.longitude_deg, 5)
    alt = round(position.absolute_altitude_m, 1)
    loc = Position(lat,long,alt)
    return loc

async def send_status(drone, writer):
    if args.log:
        csvfile = open(csvfile_path, "w+", newline='')
        csv_writer = csv.writer(csvfile)
    while True:
        await asyncio.sleep(0.2)
        pos = await get_position(drone)

        space = get_space()
        msg = f"STATUS_{pos.lat}_{pos.long}_{pos.alt}_{idle}_{space}"
        writer.write(msg.encode())
        await writer.drain()
        if args.log:
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            csv_writer.writerow([current_time, pos, idle, space])

async def pos_reached(pos):
    
    lat = round(pos[0], 4)
    long = round(pos[1], 4)
    alt = round(pos[2], 1)
    while True:
        global loc
        lat_reached = round(loc.lat, 4)==lat
        long_reached = round(loc.long, 4)==long
        alt_reached = round(loc.alt, 4)==alt
        if False:
            print("from " + str(loc_lat) + " to " + str(lat) + ": " + str(lat_reached))
            print("from " + str(loc_long) + " to " + str(long) + ": " + str(long_reached))
            print("from " + str(loc_alt) + " to " + str(alt) + ": " + str(alt_reached))
        if lat_reached & long_reached & alt_reached:
            print("Reached location.")
            return
        else:
            await asyncio.sleep(1)

async def takeoff(drone):
    await drone.action.arm()
    print("Taking off...")
    await drone.action.takeoff()
    while (not (state == LandedState(2))):
        await asyncio.sleep(1)

async def goto(drone, pos):  
    print("Goto...")
    await drone.action.goto_location(*pos, 0)
    await pos_reached(pos)

async def land(drone):
    print("Landing...")
    await drone.action.land()
    while (not (state == LandedState(1))):
        await asyncio.sleep(1)
    await drone.action.disarm()

async def main():
    global idle
    global payload
    global capacity
    global loc
    global state
    idle = True
    payload = 0
    capacity = 200
    loc = Position(0,0,0)
    state = LandedState(0)

    drone = System(port=p1)
    await drone.connect(system_address=udp)

    home = [47.39728341067808, 8.542641053423798, 500]
    

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
    
    task = asyncio.create_task(send_status(drone, writer))

    while True:
        print("Waiting to receive task from server")
        msg = await reader.read(1024)
        message = msg.decode()
        print(message)

        if message.startswith("EMPTY"):
            idle = False
            print("Received task to empty container")
            _ , lat, long, alt = message.split("_")
            pos = [float(lat),float(long),float(alt)]

            await takeoff(drone)
            await goto(drone, pos)
            await land(drone)

            msg = f"REACHED_{pos[0]}_{pos[1]}_{pos[2]}"
            writer.write(msg.encode())
            await writer.drain()

        elif message.startswith("PAYLOAD"):
            _ , received_payload = message.split("_")
            print(f"Received {received_payload} units of Payload")
            payload += int(received_payload)

            if payload > 0.8*capacity:
                print("Returning home")
                await takeoff(drone)
                await goto(drone, home)
                await land(drone)
                await asyncio.sleep(5)
                print("Setting payload to zero")
                payload = 0
            print("Setting idle")
            idle = True

if __name__ == "__main__":
    asyncio.run(main())

