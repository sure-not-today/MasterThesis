import asyncio
import pickle
from dataclasses import dataclass

@dataclass
class Drone:
    lat: float
    long: float
    alt: float

clients_data = {}

async def handle_echo(reader, writer):
    addr = writer.get_extra_info('peername')
    client_id = f"{addr[0]}:{addr[1]}"
    while True:
        data = await reader.read(100)
        [x,y] = pickle.loads(data)
        print(client_id)
        print(f"Received x: {x!r} from {addr!r}")
        print(f"Received y: {y!r} from {addr!r}")
        clients_data.setdefault(client_id, [])
        clients_data[client_id] = Drone(x, y, x*y)

def compare(clients_data, pos):
    for drone in clients_data:
        print(drone)

async def listen(server):
    async with server:
        await server.serve_forever()  

async def main():
    server = await asyncio.start_server(handle_echo, '127.0.0.1', 8888)

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving on {addrs}')


    task = asyncio.create_task(listen(server))

    await asyncio.sleep(10)

    print(clients_data)

    compare(clients_data, [0,42,5])



asyncio.run(main())