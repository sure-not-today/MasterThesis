import asyncio
from mavsdk.offboard import PositionNedYaw
import pickle
from dataclasses import dataclass
import time

@dataclass
class Position:
    lat:float
    long:float
    alt:float

@dataclass
class Drone:
    pos:Position
    prio:int
    space:int

class Container:
    def __init__(self, pos, fillrate):
        self.pos = pos
        self.amount = 0
        self.fillrate = fillrate
        self.penalty = 0

        self.task_fill = asyncio.create_task(self.fill())

    async def fill(self):
        while True:
            await asyncio.sleep(1)
            if self.amount < 100:
                self.amount += self.fillrate
            else:
                if self.amount > 100:
                    self.penalty += (self.amount - 100)
                    self.amount = 100
                self.penalty += self.fillrate

async def empty(container):
    while True:
        await asyncio.sleep(10)
        container.amount = 0

async def main():
    c1 = Container(Position(47.39718698163323, 8.542156062422546, 500), 34)
    task = asyncio.create_task(empty(c1))

    while True:
        await asyncio.sleep(1)
        print(f"amount: {c1.amount}, penalty: {c1.penalty}")
        

asyncio.run(main())