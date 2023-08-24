import asyncio
import aioconsole
from mavsdk import System
from dataclasses import dataclass
import time
import csv
import argparse

@dataclass
class Position:
    lat: float
    long: float
    alt: float

parser = argparse.ArgumentParser()
parser.add_argument('-n', '--n', nargs='?', const=1, type=int, default=1)
args = parser.parse_args()

n = args.n - 1
p1 = 50050 + n
p2 = 14540 + n
udp = f"udp://:{p2}"
csvfile_path = f"dronelog{args.n}.csv"


global idle
global payload
global capacity
global loc
idle = True
payload = 0
capacity = 200
loc = Position(0,0,0)

def get_space():
    return (capacity - payload)

async def get_position(drone):
    global loc
    position = await drone.telemetry.position().__aiter__().__anext__()
    lat = round(position.latitude_deg, 5)
    long = round(position.longitude_deg, 5)
    alt = round(position.absolute_altitude_m, 1)
    loc = Position(lat,long,alt)
    return loc

async def send_status(drone):
    with open(csvfile_path, "w+", newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        while True:
            pos = await get_position(drone)
            space = get_space()
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            csv_writer.writerow([current_time, pos, space])
            await asyncio.sleep(1)

async def pos_reached(drone,pos):
    while True:
        position = await drone.telemetry.position().__aiter__().__anext__()
        print(position)
        loc_lat = round(position.latitude_deg, 4)
        loc_long = round(position.longitude_deg, 4)
        loc_alt = round(position.absolute_altitude_m, 1)
        lat = round(pos[0], 4)
        long = round(pos[1], 4)
        alt = round(pos[2], 1)
        lat_reached = loc_lat==lat
        long_reached = loc_long==long
        alt_reached = loc_alt==alt
        if False:
            print("from " + str(loc_lat) + " to " + str(lat) + ": " + str(lat_reached))
            print("from " + str(loc_long) + " to " + str(long) + ": " + str(long_reached))
            print("from " + str(loc_alt) + " to " + str(alt) + ": " + str(alt_reached))
        if lat_reached & long_reached & alt_reached:
            print("Reached location.")
            return
        else:
            print("not reached yet")
            await asyncio.sleep(1)

async def main():
    drone = System(port=p1)
    await drone.connect(system_address=udp)

    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"-- Connected to drone!")
            break

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("-- Global position state is good enough for flying.")
            break

    task = asyncio.create_task(send_status(drone))

    await asyncio.sleep(20)

    task.cancel()
    
asyncio.run(main())


