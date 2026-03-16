import os
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from beads_manager import read_bead

# --- AI Quarterback Activities ---

@activity.defn
async def triage_task_queue(bead_id: str) -> str:
    """Uses LLM to determine the implementer (Dev vs Homelab vs SRE)."""
    import ollama
    bead_data = read_bead(bead_id)
    ollama_host = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    client = ollama.Client(host=ollama_host)
    
    prompt = f"Triage this task to 'betting-app-queue', 'homelab-queue', or 'sre-queue'. Task: {bead_data['title']} - {bead_data['description']}. Respond ONLY with the queue name."
    response = client.chat(model="llama3:latest", messages=[{'role': 'user', 'content': prompt}])
    queue = response['message']['content'].strip().lower()
    
    if "betting" in queue: return "betting-app-queue"
    if "sre" in queue: return "sre-queue"
    return "homelab-queue"

# --- Quarterback Workflows ---

@workflow.defn
class TriageWorkflow:
    @workflow.run
    async def run(self, *args) -> str:
        # Robust argument handling for list-based vs positional calls
        if len(args) == 1:
            if isinstance(args[0], (list, tuple)) and len(args[0]) == 2:
                bead_id, bucket = args[0]
            else:
                bead_id = args[0] if not isinstance(args[0], (list, tuple)) else args[0][0]
                bucket = "Design" # Default for single-arg legacy calls
        elif len(args) == 2:
            bead_id, bucket = args
        else:
            raise ValueError(f"Expected 1 or 2 arguments, got {len(args)}")
        
        fast_retry = RetryPolicy(maximum_attempts=1)

        print(f"Workflow: Processing Task {bead_id} strictly for Bucket '{bucket}'")
        
        # --- STRICT PHASE ISOLATION ---
        
        # 1. DESIGN PHASE (Architect Agent ONLY)
        if bucket == "Design":
            print(f"[{bead_id}] Routing to Architect Agent.")
            return await workflow.execute_activity(
                "architect_activity", bead_id, # Using our new unified activity name
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=fast_retry
            )

        # 2. BREAKDOWN PHASE (Business Analyst ONLY)
        elif bucket == "Doing":
            print(f"[{bead_id}] Routing to Business Analyst Agent.")
            return await workflow.execute_activity(
                "execute_bead_activity", bead_id,
                start_to_close_timeout=timedelta(minutes=5),
                task_queue="ba-queue",
                retry_policy=fast_retry
            )

        # 3. EXECUTION PHASE (Dev -> Release ONLY)
        elif bucket == "Ready":
            print(f"[{bead_id}] Routing to Execution & Release Pipeline.")
            target_queue = await workflow.execute_activity(
                triage_task_queue, bead_id,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=fast_retry
            )
            
            dev_result = await workflow.execute_activity(
                "execute_bead_activity", bead_id,
                start_to_close_timeout=timedelta(minutes=10),
                task_queue=target_queue,
                retry_policy=fast_retry
            )
            
            release_result = await workflow.execute_activity(
                "release_bead_activity", bead_id,
                start_to_close_timeout=timedelta(minutes=15),
                task_queue="release-queue",
                retry_policy=fast_retry
            )
            return f"{dev_result} | {release_result}"

        # If it reaches here, it's an unmapped bucket (e.g., Backlog, To-Do, Done).
        print(f"[{bead_id}] Ignored bucket state: {bucket}")
        return f"Bucket '{bucket}' intentionally ignored."
