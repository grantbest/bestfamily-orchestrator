import asyncio
import os
from temporalio.client import Client

async def main():
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    print(f"Connecting to Temporal at {temporal_address}...")
    client = await Client.connect(temporal_address)
    
    # Trigger the SRE Daemon
    try:
        handle = await client.start_workflow(
            "SREHealingWorkflow",
            id="sre-healing-daemon",
            task_queue="sre-queue"
        )
        print(f"🚀 SRE Healing Daemon Started. ID: {handle.id}")
    except Exception as e:
        print(f"⚠️ SRE Daemon already running or failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
