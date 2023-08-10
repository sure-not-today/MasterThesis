import asyncio
import aioconsole
from mavsdk import System
import socket

async def main():

    drone = System(port=50051)
    await drone.connect(system_address="udp://:14541")

    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"-- Connected to drone!")
            break

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("-- Global position state is good enough for flying.")
            break

    await drone.action.arm()

    await drone.action.takeoff()

    await drone.action.hold()

    await asyncio.sleep(5)

    await drone.action.goto_location(47.39718698163323, 8.542156062422546, 500, 0)

    await asyncio.sleep(3600)

asyncio.run(main())