import asyncio
from datetime import datetime, timezone
from temporalio.client import Client

async def fix_hung_workflows():
    print("SRE: Connecting to Temporal...")
    try:
        client = await Client.connect("localhost:7233")
        print("SRE: Connected to Temporal.")
    except Exception as e:
        print(f"SRE: Failed to connect: {e}")
        return

    # List all workflows
    print("SRE: Fetching workflows...")
    count = 0
    terminated = 0
    
    # We use list_workflows which returns an async iterator
    async for workflow in client.list_workflows('ExecutionStatus = "Running"'):
        count += 1
        start_time = workflow.start_time
        # March 21st, 2026
        cutoff = datetime(2026, 3, 21, tzinfo=timezone.utc)
        
        print(f"Found Workflow: {workflow.id} (Started: {start_time})")
        
        if start_time <= cutoff:
            print(f"⚠️  SRE: TERMINATING HUNG WORKFLOW: {workflow.id} (Started: {start_time})")
            handle = client.get_workflow_handle(workflow.id)
            await handle.terminate(reason="SRE: Manual termination of hung March 20th job")
            terminated += 1
            
    print(f"SRE: Scan complete. Found {count} running, terminated {terminated} hung jobs.")

if __name__ == "__main__":
    asyncio.run(fix_hung_workflows())
