import asyncio

class PausableTask():
    def __init__(self, pause_event):
        self.pause_event = pause_event
    
    async def background_task(pause_event):
        while True:
            if not pause_event.is_set():
                print("Background task is running...")
            else:
                print("Background task is paused...")
            await asyncio.sleep(1)

async def subtask():
    while True:
        print("doing subtask...")
        await asyncio.sleep(1)

async def main():
    task = asyncio.create_task(subtask())
        # Run the task for 5 seconds
    await asyncio.sleep(5)
    
    # Cancel the current task
    task.cancel()
    
    try:
        await task  # Wait for the task to be canceled
    except asyncio.CancelledError:
        pass
    
    print("Task has been canceled.")
    print(task.get_coro())
    # Restart the task
    task = asyncio.create_task(task.get_coro())
    
    # Run the restarted task for another 3 seconds
    await asyncio.sleep(3)
    
    # Cancel the restarted task
    task.cancel()
    
    try:
        await task  # Wait for the restarted task to be canceled
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(main())