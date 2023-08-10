import asyncio



async def ping():
    while True:
        await asyncio.sleep(1)
        print(idle)

async def main():
    global idle
    idle = True

    task = asyncio.create_task(ping())

    await asyncio.sleep(4)

    idle = False

    await asyncio.sleep(4)

asyncio.run(main())