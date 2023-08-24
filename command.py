import asyncio
from mavsdk import System
from dataclasses import dataclass
from mavsdk.telemetry import LandedState

@dataclass
class Position:
    lat: float
    long: float
    alt: float

async def get_position(drone):
    while True:
        global loc
        global state
        position = await drone.telemetry.position().__aiter__().__anext__()
        state = await drone.telemetry.landed_state().__aiter__().__anext__()
        lat = round(position.latitude_deg, 5)
        long = round(position.longitude_deg, 5)
        alt = round(position.absolute_altitude_m, 1)
        loc = Position(lat,long,alt)
        await asyncio.sleep(.1)

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
            print("from " + str(loc.lat) + " to " + str(lat) + ": " + str(lat_reached))
            print("from " + str(loc.long) + " to " + str(long) + ": " + str(long_reached))
            print("from " + str(loc.alt) + " to " + str(alt) + ": " + str(alt_reached))
        if lat_reached & long_reached & alt_reached:
            print("Reached location.")
            return
        else:
            await asyncio.sleep(1)

async def takeoff(drone):
    print("arming")
    await drone.action.arm()
    print("takeoff")
    await drone.action.takeoff()
    while (not (state == LandedState(2))):
        print("Raising...")
        await asyncio.sleep(1)

async def goto(drone, pos):  
    print("goto")
    await drone.action.goto_location(*pos, 0)
    await pos_reached(pos)

async def land(drone):
    print("landing")
    await drone.action.land()
    while (not (state == LandedState(1))):
        print("Landing...")
        await asyncio.sleep(1)
    await drone.action.disarm()
    
async def main():
    global loc
    global state
    loc = Position(0,0,0)
    state = LandedState(0)

    drone = System(port=50050)
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
    
    pos = [47.39907273002228, 8.54371614376562, 500]

    task = asyncio.create_task(get_position(drone))

    await takeoff(drone)

    await goto(drone, pos)

    await land(drone)



asyncio.run(main())