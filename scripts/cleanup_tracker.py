import os
import sys

# Add scripts to path
sys.path.append(os.path.join(os.getcwd(), "BestFam-Orchestrator", "scripts"))
from beads_manager import list_beads, delete_bead

TEST_KEYWORDS = [
    "TDD Regression", "Manual Test", "Modular Regression", "LIFECYCLE TEST",
    "VALIDATION TARGET TEST", "ATOMIC MOVE TASK", "VIEW MOVE DEMO", 
    "PROVEN MOVE TASK", "DIRECT DESIGN TASK", "MIRROR DIAG TASK",
    "PROVEN PATH TASK", "GRAIL TEST TASK", "DIAGNOSTIC TEST TASK",
    "FIXED MOVE DEMO", "VIEW VISIBILITY TEST", "REPRO DIAG TASK",
    "PERSIST TEST TASK", "VIEW PERSISTENCE TASK", "DIRECT VIEW TASK",
    "FLOW TEST TASK", "KANBAN INTEGRATION", "DIRECT DESIGN TASK",
    "MIRROR DIAG TASK", "RESEARCH CREATE TASK", "PROVEN PATH TASK",
    "Modular TDD", "Modular Implementation", "FINAL VISIBILITY TEST",
    "Parent Epic", "Child Story", "PROVEN MOVE TASK", "INITIAL BUCKET TEST",
    "BUCKET ASSIGN DEMO", "BUCKET ASSIGN POST DEMO"
]

TEST_AGENTS = [
    "regression-tester", "tester", "agent-test", "researcher", 
    "demo-agent", "quarterback-breakdown"
]

def cleanup():
    print("🧹 STARTING TRACKER CLEANUP...")
    
    all_beads = list_beads()
    print(f"Total tasks found: {len(all_beads)}")
    
    deleted_count = 0
    for bead in all_beads:
        should_delete = False
        
        # Check keywords in title
        for kw in TEST_KEYWORDS:
            if kw.upper() in bead['title'].upper():
                should_delete = True
                break
        
        # Check requesting agent
        if not should_delete and bead.get('requesting_agent') in TEST_AGENTS:
            should_delete = True
            
        if should_delete:
            print(f"🗑️ Deleting: [{bead['stage']}] #{bead['index']}: {bead['title']}")
            delete_bead(bead['id'])
            deleted_count += 1
            
    print(f"\n✨ CLEANUP COMPLETE. Deleted {deleted_count} test tasks.")

if __name__ == "__main__":
    cleanup()
