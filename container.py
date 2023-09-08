import asyncio
from dataclasses import dataclass
import colorama
import random
import numpy as np

colorama.init()

class RecursiveMean():
    def __init__(self) -> None:
        self.n = 0
        self.x = 0

    def __call__(self):
        return self.x

    def mean(self, x):
        self.n += 1
        self.x += (1/(self.n)) * (x - self.x)


class Container():
    def __init__(self, pos, name, capacity, aps, print_to_cmd=False):
        self.pos = pos
        self.name = name
        self.amount = 0
        self.capacity = capacity
        self.aps = aps
        self.penalty = 0
        self.print_to_cmd = print_to_cmd

class RContainer(Container):
    def __init__(self, pos, name, capacity, aps, method='linear', sigma = 1, print_to_cmd=False):
        super().__init__(pos, name, capacity, aps, print_to_cmd=False)
        self.pos = pos
        self.name = name
        self.amount = 0
        self.capacity = capacity
        self.aps = aps
        self.penalty = 0
        self.docked = None
        self.method = method
        self.sigma = sigma
        self.print_to_cmd = print_to_cmd
        asyncio.create_task(self.fill())

    async def fill(self):
        add_amount = self.aps
        mu_log = np.log((self.aps**2) / np.sqrt(self.sigma**2 + self.aps**2))
        sigma_log = np.sqrt(np.log((self.sigma**2 / self.aps**2) + 1))
        while True:
            if self.method == 'gauss':
                add_amount = max(random.gauss(self.aps,self.sigma), 0)
            elif self.method == 'fluct':
                add_amount += random.gauss(0,self.sigma)
                if add_amount < 0:
                    add_amount = 0
            elif self.method == "log":
                add_amount = np.random.lognormal(mu_log, sigma_log)
            elif self.method == "poisson":
                add_amount = np.random.poisson(self.aps)

            future_amount = self.amount + add_amount
            add_penalty = max(future_amount - self.capacity, 0)
            amountAdded = add_amount-add_penalty

            self.amount += amountAdded
            self.penalty += add_penalty
            if self.print_to_cmd:                
                print(f"{colorama.Style.DIM}Container {self.name}: Added amount >> {round(amountAdded,2)} || Added penalty >> {round(add_penalty,2)}{colorama.Style.RESET_ALL}")
                print(f"{colorama.Style.DIM}Container {self.name}: Amount >> {round(self.amount,2)} / {self.capacity} || Penalty >> {round(self.penalty,2)}{colorama.Style.RESET_ALL}")
                print(f"\n")
            await asyncio.sleep(1)

    def dock(self, drone):
        self.docked = drone
    
    async def give_payload(self):
        if self.docked:
            drone = self.docked
            payload = min(self.amount, drone.space)
            self.amount -= payload
            msg = f"PAYLOAD_{self.amount}_{self.penalty}_{payload}_{self.name}"
            writer = drone.writer
            writer.write(msg.encode())
            await writer.drain()
        else:
            print("No drone docked. Can't give payload")
            return
        
    def undock(self):
        if self.docked:
            self.docked = None
        else:
            print("Nothing to undock")

class SContainer(Container):
    def __init__(self, pos, name, capacity=float('inf'), aps=0, print_to_cmd=False):
        super().__init__(pos, name, capacity, aps, print_to_cmd=False)
        self.pos = pos
        self.name = name
        self.amount = 0
        self.capacity = float("inf")
        self.threshold = float("inf")
        self.aps = RecursiveMean()
        self.print_to_cmd = print_to_cmd

        self.data = None
        self.n = 0
        self.d = RecursiveMean() # time to empty
        self.pending = False
        self.capped = False

        asyncio.create_task(self.fill())
    
    def __str__(self) -> str:
        return f"Simulated Container {self.name}: aps = {self.aps()}, capacity = {self.capacity}, threshold = {self.threshold}, d = {self.d()}"

    async def fill(self):
        while True:
            self.amount += self.aps()
            if self.print_to_cmd:                
                print(f"{colorama.Style.DIM}Container {self.name}: Added amount >> {round(self.aps(),2)}")
                print(f"{colorama.Style.DIM}Container {self.name}: Amount >> {round(self.amount,2)} / {self.capacity}")
                print(f"\n")
            await asyncio.sleep(1)
    
    def new_data(self, data):
        self.n += 1
        t, a, p, r, d = data
        self.amount = a
        self.d.mean(d)   

        if self.data:
            tp, ap, pp, _, _ = self.data
            aps = (a - ap + p - pp + r) / (t - tp)
            self.aps.mean(aps)
            
        if p > 0 and not self.capped:
            self.capped = True
            self.capacity = a+r
            
        self.threshold = self.capacity - (self.aps()*self.d())
        
        self.data = data
        print(str(self))