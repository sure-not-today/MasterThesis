import asyncio
import pickle
import colorama
from mavsdk.offboard import PositionNedYaw

colorama.init()

clients = {}  # Dictionary to store connected clients

class Container:
    def __init__(self, pos, name, aps):
        self.pos = pos
        self.level = 0
        self.name = name
        self.aps = aps
        self.full_status = False
        self.pending = False
        asyncio.create_task(self.fill_container())

    async def fill_container(self):
        while True:
            await asyncio.sleep(1)
            self.level += self.aps # amount per second
            if self.level >= 100:
                self.full_status = True
                print(f"{colorama.Fore.MAGENTA}Container {self.name} is full.{colorama.Style.RESET_ALL}")

                while self.full_status == True:
                    await asyncio.sleep(5)
                
async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"{colorama.Fore.CYAN}{addr} connected{colorama.Style.RESET_ALL}")

    clients[addr] = (reader, writer, True)

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

async def handle_responses(containers):
    while True:
        await asyncio.sleep(.1)  # Adjust this duration as needed

        for addr, (reader, writer, _ ) in clients.copy().items():
            try:
                if writer.can_write_eof():
                    data = await asyncio.wait_for(reader.read(100), timeout=0.1)
                    if data:
                        message = data.decode()
                        if message.startswith("REACHED"):
                            pos = extract_pos(message)
                            cname = pos_to_cont(containers, pos)
                            print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}{addr}: reached Container {cname} and empties it.{colorama.Style.RESET_ALL}")
                            for container in containers:
                                if cname == container.name:
                                    container.level = 0
                                    container.full_status = False
                                    container.pending = False
                        elif message.startswith("HOME"):
                            print(f"{colorama.Fore.GREEN}{addr}: back Home and idle.{colorama.Style.RESET_ALL}")
                            clients[addr] = (reader,writer,True)
                print("-----------------")  # Line separator after the if-else block
            except asyncio.TimeoutError:
                pass

def pos_to_cont(containers, pos):
    for container in containers:
        if container.pos == pos:
            return container.name
        
def extract_pos(message):
    _ , lat, long, alt = message.split("_")
    pos = [float(lat),float(long),float(alt)]
    return pos


async def main():
    pos1 = [47.39718698163323, 8.542156062422546, 500]
    pos2 = [47.39779268111438, 8.542395102770325, 500]
    pos3 = [47.39685021811752, 8.542915525936115, 500]
    container_a = Container(pos1, "A", 1)
    container_b = Container(pos2, "B", 2)
    container_c = Container(pos3, "C", 3)
    containers = [container_a, container_b, container_c]

    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"{colorama.Fore.YELLOW}Serving on {addr}{colorama.Style.RESET_ALL}")

    asyncio.create_task(handle_responses(containers))

    async with server:
        while True:
            await asyncio.sleep(1)  # Check containers every 1 second

            # Check if container is full and a client is available
            for container in containers:

                if container.full_status and not container.pending:

                    for client_addr, (reader, writer, idle) in clients.copy().items():

                        if idle:

                            clients[client_addr] = (reader, writer, False)
                            container.pending = True

                            print(f"Sending request to empty Container {container.name} to Drone @ {client_addr}")
                            msg = f"EMPTY_{container.pos[0]}_{container.pos[1]}_{container.pos[2]}"
                            writer.write(msg.encode())
                            await writer.drain()

                            break
                        
if __name__ == "__main__":
    asyncio.run(main())
    

