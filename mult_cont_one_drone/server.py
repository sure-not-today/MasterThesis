import asyncio
import pickle
import colorama
from mavsdk.offboard import PositionNedYaw

colorama.init()

clients = {}  # Dictionary to store connected clients

class Container:
    def __init__(self, pos):
        self.pos = pos
        self.level = 0
        self.full_status = False

async def fill_container(container, container_name, aps):
    while True:
        await asyncio.sleep(1)
        container.level += aps # amount per second
        if container.level >= 100:
            container.full_status = True
            print(f"{colorama.Fore.MAGENTA}Container {container_name} is full.{colorama.Style.RESET_ALL}")

            while container.full_status == True:
                await asyncio.sleep(5)
                
async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"{colorama.Fore.CYAN}{addr} connected{colorama.Style.RESET_ALL}")

    clients[addr] = (reader, writer)

    try:
        while True:
            await asyncio.sleep(3600)  # Wait for an hour (or any long duration)
    except asyncio.CancelledError:
        pass
    finally:
        del clients[addr]
        writer.close()

async def send_task_to_client(addr, task):
    if addr in clients:
        reader, writer = clients[addr]
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

async def main():
    pos1 = [47.39718698163323, 8.542156062422546, 500]
    pos2 = [47.39779268111438, 8.542395102770325, 500]
    pos3 = [47.39685021811752, 8.542915525936115, 500]
    container_a = Container(pos1)
    container_b = Container(pos2)
    container_c = Container(pos3)
    containers = [container_a, container_b, container_c]
    asyncio.create_task(fill_container(container_a, "A", 1))
    asyncio.create_task(fill_container(container_b, "B", 2))
    asyncio.create_task(fill_container(container_c, "C", 3))

    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"{colorama.Fore.YELLOW}Serving on {addr}{colorama.Style.RESET_ALL}")

    async with server:
        while True:
            await asyncio.sleep(1)  # Check containers every 1 second

            # Check if container is full and a client is available
            for container in containers:

                if container.full_status:

                    for client_addr, (reader, writer) in clients.items():
                        
                        # send Position to Drone

                        print("sending position of Container to Drone")
                        msg = f"GOTO_{container.pos[0]}_{container.pos[1]}_{container.pos[2]}"

                        writer.write(msg.encode())
                        await writer.drain()

                        # wait for Drone to arrive
                        print("waiting for Drone to arrive at Container")
                        msg = await reader.read(1024)
                        msg = msg.decode()
                        if msg == "DONE":
                            pass
                        else:
                            continue

                        # empty container
                        container.level = 0
                        container.full_status = False

                        msg = "HOME"
                        writer.write(msg.encode())
                        await writer.drain()

                        # wait for Drone to return
                        print("waiting for Drone to arrive at Home")
                        msg = await reader.read(1024)
                        msg = msg.decode()
                        if msg == "DONE":
                            pass
                        else:
                            continue


if __name__ == "__main__":
    asyncio.run(main())
    

