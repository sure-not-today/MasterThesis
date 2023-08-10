import asyncio
from mavsdk import System
from mavsdk.offboard import PositionNedYaw
import argparse
from dataclasses import dataclass

@dataclass
class Position:
    lat: float
    long: float
    alt: float

class Drone(System):
    def __init__(self, mavsdk_server_address=None, port=50051, sysid=245, compid=190, capacity = 100):
      super().__init__(mavsdk_server_address, port, sysid, compid)
      self.idle = True
      self.payload = 0
      self.capacity = capacity

    def get_idle(self):
        return self.idle

    def get_space(self):
        return (self.capacity - self.payload)

async def get_position(drone):
    position = await drone.telemetry.position().__aiter__().__anext__()
    lat = round(position.latitude_deg, 4)
    long = round(position.longitude_deg, 4)
    alt = round(position.absolute_altitude_m, 1)
    pos = Position(lat,long,alt)
    return pos

async def send_status(drone, writer):
    while True:
        await asyncio.sleep(2)
        pos = await get_position(drone)
        idle = drone.get_idle()
        space = drone.get_space()
        msg = f"STATUS_{pos.lat}_{pos.long}_{pos.alt}_{idle}_{space}"
        writer.write(msg.encode())
        await writer.drain()



async def pos_reached(drone,pos):
    while True:
        position = await drone.telemetry.position().__aiter__().__anext__()
        loc_lat = round(position.latitude_deg, 4)
        loc_long = round(position.longitude_deg, 4)
        loc_alt = round(position.absolute_altitude_m, 1)
        lat = round(pos[0], 4)
        long = round(pos[1], 4)
        alt = round(pos[2], 1)
        lat_reached = loc_lat==lat
        long_reached = loc_long==long
        alt_reached = loc_alt==alt
        #print("from " + str(loc_lat) + " to " + str(lat) + ": " + str(lat_reached))
        #print("from " + str(loc_long) + " to " + str(long) + ": " + str(long_reached))
        #print("from " + str(loc_alt) + " to " + str(alt) + ": " + str(alt_reached))
        if lat_reached & long_reached & alt_reached:
            return
        else:
            await asyncio.sleep(1)

async def main():
    global idle
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--n', nargs='?', const=1, type=int, default=1)
    args = parser.parse_args()
    
    n = args.n - 1
    p1 = 50050 + n
    p2 = 14540 + n
    udp = f"udp://:{p2}"

    drone = Drone(port=p1)
    await drone.connect(system_address=udp)

    home = [47.39728341067808, 8.542641053423798, 500]
    

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
        print("Connected to server.")
        
        await drone.action.arm()
        await asyncio.sleep(1)
        await drone.action.takeoff()
        await asyncio.sleep(2)

        task = asyncio.create_task(send_status(drone, writer))

        await asyncio.sleep(7)

        drone.idle = False

        while True:
            print("waiting to receive task from server")
            msg = await reader.read(1024)
            message = msg.decode()
            print(message)

            if message.startswith("EMPTY"):
                drone.idle = False
                print("received task to empty container")
                _ , lat, long, alt = message.split("_")
                pos = [float(lat),float(long),float(alt)]
                print("going to location")
                await drone.action.goto_location(*pos, 0)
                await pos_reached(drone, pos)
                print("reached container and now emptying")
                msg = f"REACHED_{pos[0]}_{pos[1]}_{pos[2]}"
                writer.write(msg.encode())
                await writer.drain()

            elif message.startswith("PAYLOAD"):
                _ , received_payload = message.split("_")
                print(f"Received {received_payload} units of Payload")
                payload += received_payload

                if payload > 0.8*drone.capacity:
                    print("returning home")
                    await drone.action.goto_location(*home, 0)
                    await pos_reached(drone, home)
                    await asyncio.sleep(5)
                    drone.payload = 0
                drone.idle = True


    except (ConnectionRefusedError, OSError):
        print("Connection to server failed. Make sure the server is running.")
    finally:
        # Close the connection when done
        writer.close()
        await writer.wait_closed()
        print("Connection closed.")

if __name__ == "__main__":
    asyncio.run(main())

