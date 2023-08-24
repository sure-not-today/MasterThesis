import asyncio
from mavsdk import System
from dataclasses import dataclass
from mavsdk.telemetry import LandedState
import colorama

colorama.init()

@dataclass
class Position:
    lat: float
    long: float
    alt: float

@dataclass
class Status:
    pos: Position
    prio: int
    payload: float
    capacity: float
    landed_state: LandedState

async def status_update(drone):
    while True:
        position = await drone.telemetry.position().__aiter__().__anext__()
        lat = round(position.latitude_deg, 5)
        long = round(position.longitude_deg, 5)
        alt = round(position.absolute_altitude_m, 1)
        loc = Position(lat,long,alt)
        status.pos = loc
        status.landed_state = await drone.telemetry.landed_state().__aiter__().__anext__()
        print(status)
        await asyncio.sleep(1)

async def main():

    global status
    status = Status(Position(0,0,0), 0, 0, 0, LandedState(0))

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
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
        print(f"{colorama.Fore.GREEN}Connected to server.{colorama.Style.RESET_ALL}")
    except:
        print(f"{colorama.Fore.RED}Could not connected to server.{colorama.Style.RESET_ALL}")

    
    task = asyncio.create_task(status_update(drone))

    await asyncio.sleep(3600)

asyncio.run(main())
