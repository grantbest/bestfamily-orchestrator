import asyncio
import os
from temporalio.client import Client
from datetime import datetime, timezone, timedelta

async def reset_temporal():
    """
    SRE Emergency Reset: Terminates ALL running workflows to unblock the Gastown pipeline.
    """
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    print(f"SRE: Connecting to Temporal at {temporal_address}...")
    client = await Client.connect(temporal_address)
    
    print("SRE: Fetching ALL running workflows...")
    count = 0
    async for workflow in client.list_workflows('ExecutionStatus = "Running"'):
        print(f"⚠️ Terminating Workflow: {workflow.id} (Type: {workflow.workflow_type})")
        handle = client.get_workflow_handle(workflow.id)
        try:
            await handle.terminate(reason="SRE Emergency Reset to unblock Gastown Pipeline")
            count += 1
        except Exception as e:
            print(f"❌ Failed to terminate {workflow.id}: {e}")
            
    print(f"🏁 SRE Reset complete. Terminated {count} workflows.")

if __name__ == "__main__":
    asyncio.run(reset_temporal())
