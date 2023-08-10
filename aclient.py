import asyncio
from mavsdk import System
import pickle
from mavsdk.offboard import PositionNedYaw

async def send_task(writer):
    global data
    while True:
        await asyncio.sleep(1)
        await send(writer, data)

async def send(writer, data):
    writer.write(pickle.dumps(data))
    await writer.drain()

async def main():
    global data
    data = PositionNedYaw(0,0,-5,0)
    reader, writer = await asyncio.open_connection('127.0.0.1', 8888)

    while True:
        data = PositionNedYaw(0,0,-5,0)
        await asyncio.sleep(3)

        data = PositionNedYaw(5,5,-5,0)

        await asyncio.sleep(10)


asyncio.run(main())

