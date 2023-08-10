import asyncio
import aioconsole
from mavsdk import System
import socket

async def listen(drone):

    while True:
        line = await aioconsole.ainput('Input: ')
        if line == "goto":
            line = await aioconsole.ainput('Where do you wanna go: ')
            if line == str(1):
                await goto_wait(drone, pos1)
                continue
            elif line == str(2):
                await goto_wait(drone, pos2)
                continue
            elif line == str(3):
                await goto_wait(drone, pos3)
                continue
            else:
                print("Enter either 1, 2 or 3")
        elif line == "done":
            break
        elif line == "lat":
            print(latitude)
        elif line == "long":
            print(longitude)
        elif line == "alt":
            print(altitude) 
        else:
            print("Only command right now is goto")

async def get_alt_rel(drone):
    alt = None
    async for tel in drone.telemetry.position():
        alt = tel.relative_altitude_m
        break
    return alt

async def get_alt(drone):
    alt = None
    async for tel in drone.telemetry.position():
        alt = tel.absolute_altitude_m
        break
    return alt

async def get_lat(drone):
    lat = None
    async for tel in drone.telemetry.position():
        lat = tel.latitude_deg
        break
    return lat

async def get_long(drone):
    long = None
    async for tel in drone.telemetry.position():
        long = tel.longitude_deg
        break
    return long

async def goto_wait(drone, pos):
    lat = round(pos[0], 4)
    long = round(pos[1], 4)
    alt = round(pos[2], 1)
    await drone.action.arm()
    await drone.action.takeoff()
    await asyncio.sleep(5)
    await drone.action.goto_location(lat, long, alt, 0)

    loc_lat = 0
    loc_long = 0
    loc_alt = 0

    while True:
        loc_lat = round(await get_lat(drone), 4)
        loc_long = round(await get_long(drone), 4)
        loc_alt = round(await get_alt(drone), 1)
        lat_reached = loc_lat==lat
        long_reached = loc_long==long
        alt_reached = loc_alt==alt
        print("from " + str(loc_lat) + " to " + str(lat) + ": " + str(lat_reached))
        print("from " + str(loc_long) + " to " + str(long) + ": " + str(long_reached))
        print("from " + str(loc_alt) + " to " + str(alt) + ": " + str(alt_reached))
        if lat_reached & long_reached & alt_reached:
            break
        else:
            await asyncio.sleep(1)

async def print_loc(drone):

    global latitude
    global longitude
    global altitude

    while True:
        latitude = await get_lat(drone)
        longitude = await get_long(drone)
        altitude = await get_alt(drone)
        await asyncio.sleep(1)


async def main():

    drone = System()
    await drone.connect(system_address="udp://:14540")

    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"-- Connected to drone!")
            break

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("-- Global position state is good enough for flying.")
            break

    TCP_IP = '127.0.0.1'
    TCP_PORT = 5005
    BUFFER_SIZE = 20
    MESSAGE = "Hello World"

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TCP_IP, TCP_PORT))
    s.send(MESSAGE)
    data = s.recv(BUFFER_SIZE)
    s.close()

    print("received data: ", data)

    print("creating background tasks")
    background_task = set()
    task = asyncio.create_task(print_loc(drone))
    background_task.add(task)
    print("2")
    await listen(drone)
    print("3")
    task.cancel()
    print("4")

pos1 = [47.39718698163323, 8.542156062422546, 500]
pos2 = [47.39907273002228, 8.54371614376562, 500]
pos3 = [47.39662124395584, 8.544626191215746, 500]

global latitude
global longitude
global altitude

asyncio.run(main())
