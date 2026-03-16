import asyncio
import os
import json
from src.agents.product_expert import ProductExpertAgent
from src.agents.architect import ArchitectAgent
from src.agents.sre import SREAgent

async def run_discovery_audit():
    """
    Simulates the 'Meta-Discovery' phase: 
    Product Expert defines scope -> Architect validates design -> SRE assesses infra impact.
    """
    pe = ProductExpertAgent()
    
    epic_title = "The Autonomous Feature Factory"
    user_vision = (
        "Replace human components in the SDLC while keeping humans in the outer loop via Vikunja. "
        "Focus on MVP Phase-1: New Capabilities, Enhancements, and Support (Bugs/Security). "
        "Leverage IaC, pipeline-driven solutions, meta-testing evidence, and SRE fallback."
    )

    print(f"--- 🧠 PRODUCT EXPERT: Defining Scope for '{epic_title}' ---")
    scope = await pe.define_scope(epic_title, user_vision)
    
    # Store evidence
    evidence_path = "tests/evidence/FACTORY_DISCOVERY"
    os.makedirs(evidence_path, exist_ok=True)
    
    with open(f"{evidence_path}/scope_requirements.json", "w") as f:
        json.dump(scope, f, indent=2)
    
    print("\n✅ Meta-Testing Evidence: Product Scope Defined and Archived.")
    print(json.dumps(scope, indent=2))

if __name__ == "__main__":
    # Ensure environment is loaded for discovery
    if os.path.exists("../../Homelab/shared-services/.env"):
        from pathlib import Path
        with open("../../Homelab/shared-services/.env") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v

    asyncio.run(run_discovery_audit())
