import asyncio
from mavsdk.offboard import PositionNedYaw
import pickle
from dataclasses import dataclass

class Container:
    def __init__(self, pos, fillrate):
        self.pos = pos
        self.amount = 0
        self.fillrate = fillrate

        task = asyncio.create_task(self.fill())

    async def fill(self):
        while True:
            self.amount += self.fillrate
            await asyncio.sleep(1)

connected_clients = []

async def handle_client(reader, writer):
    # Add the client's writer to the list of connected clients
    connected_clients.append(writer)

    try:
        while True:
            message = input("Enter a message to send to the client: ")
            # You can add logic here to send tasks to clients based on received messages.
            if message == "START_TASK":
                
                print("Sending a task to the client.")
                writer.write("TASK".encode())
                await writer.drain()
                data = await reader.read(1024)
                message = data.decode()

                if message == "POS":
                    print("Client ready and requested Position")
                    data = pickle.dumps(PositionNedYaw(10,20,5,0))
                    writer.write(data)
                    await writer.drain()
                else:
                    print("Client was busy")
                    continue
                
                print("Waiting for client.")
                data = await reader.read(1024)
                message = data.decode()
                if message == "BUSY":
                    print("Client was busy.")
                print(f"Received from client: {message}")
            else:
                writer.write(message.encode())
                await writer.drain()

    except asyncio.CancelledError:
        pass

    finally:
        # Remove the client's writer from the list of connected clients when they disconnect
        connected_clients.remove(writer)
        writer.close()
        await writer.wait_closed()

async def request(reader, writer):
    print("Sending a task to the client.")
    writer.write("TASK".encode())
    await writer.drain()
    print("Waiting for client.")
    data = await reader.read(1024)
    message = data.decode()
    if message == "BUSY":
        print("Client was busy.")
    print(f"Received from client: {message}")

async def main():
    c1 = Container(PositionNedYaw(20,10,-5,0), 1)
    c2 = Container(PositionNedYaw(-10,5,-5,0), 2)
    c3 = Container(PositionNedYaw(-35,-15,-5,0), 3)
    containers = [c1, c2, c3]

    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f'Server started on {addr}')
    
    async with server:
        await server.serve_forever()

    

if __name__ == "__main__":
    asyncio.run(main())