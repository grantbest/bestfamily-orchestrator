import asyncio
import os
import json
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from src.workers.polecat_activities import polecat_developer_activity
from src.workers.refinery_workflow import RefineryWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Templates ---

EPIC_TEMPLATE = """<h1>🏆 EPIC: {title}</h1>
<hr>
<h2>🎯 Product Vision (BA)</h2>
<p>{product_analysis}</p>

<h3>🛠 Automation Strategy</h3>
<ul>
{automation_strategy}
</ul>
<hr>
<h2>🏗 System Architecture (Architect)</h2>
<div>{technical_design}</div>
<hr>
<h2>🛡 Operations & Infrastructure (SRE/CICD)</h2>
<ul>
  <li><strong>IaC Impact:</strong><br>{iac_impact}</li>
  <li><strong>Security Posture:</strong><br>Standard BestFam security rules apply.</li>
  <li><strong>Resiliency:</strong><br>Automatic SRE Fallback enabled.</li>
</ul>
<hr>
<p><em>Status: In Design Review. Please see comments for outstanding questions.</em></p>
"""

STORY_TEMPLATE = """<h1>📝 STORY: {title}</h1>
<hr>
<h2>📋 Requirements (BA)</h2>
<p>{product_analysis}</p>
<hr>
<h2>📐 Technical Implementation (Architect)</h2>
<div>{technical_design}</div>
<hr>
<h2>🚦 Deployment & Safety (SRE)</h2>
<ul>
  <li><strong>Fast-Path Eligibility:</strong><br>Yes (Directory Hashing enabled)</li>
  <li><strong>Rollback Plan:</strong><br>Docker Compose revert</li>
</ul>
<hr>
<p><em>Status: Ready for implementation pending design clarifications.</em></p>
"""

# --- Activities ---

def _is_epic(title: str) -> bool:
    t = title.upper()
    return "[EPIC]" in t or t.startswith("EPIC:") or t.startswith("EPIC ")

def _is_story(title: str) -> bool:
    return "[STORY]" in title.upper()


@activity.defn
async def triage_task_queue(bead_id: str) -> str:
    """Uses LLM to determine the implementer queue."""
    from beads_manager import read_bead
    from src.utils.model_router import ModelRouter

    bead_data = read_bead(bead_id)
    title = bead_data.get('title', '')
    desc = bead_data.get('description', '')

    prompt = (
        f"Triage this development task to one of these queues:\n"
        f"- 'betting-app-queue': code changes to the MLB betting engine or its frontend\n"
        f"- 'homelab-queue': infrastructure, Docker, Vikunja, Temporal, or homelab config changes\n"
        f"- 'sre-queue': incident response, debugging, or reliability fixes\n\n"
        f"Task: {title}\n{desc[:500]}\n\n"
        f"Respond ONLY with the queue name."
    )

    router = ModelRouter()
    try:
        result = await router.chat(prompt=prompt, preferred_model="fast", json_mode=False)
        queue = (result if isinstance(result, str) else str(result)).strip().lower()
        logger.info(f"Mayor Triage: {queue}")
    except Exception as e:
        logger.error(f"Triage failed, defaulting to betting-app-queue: {e}")
        return "betting-app-queue"

    if "betting" in queue:
        return "betting-app-queue"
    if "sre" in queue:
        return "sre-queue"
    if "homelab" in queue:
        return "homelab-queue"
    return "betting-app-queue"


@activity.defn
async def ba_design_activity(bead_id: str) -> dict:
    from src.agents.product_expert import ProductExpertAgent
    from beads_manager import read_bead
    bead_data = read_bead(bead_id)
    pe = ProductExpertAgent()
    return await pe.define_scope(bead_data.get("title", ""), bead_data.get("description", ""))


@activity.defn
async def architect_design_activity(scope: dict) -> dict:
    from src.agents.architect import ArchitectAgent
    agent = ArchitectAgent()
    return await agent.analyze("System Design", json.dumps(scope, indent=2), "Refining technical details based on BA scope.")


@activity.defn
async def game_designer_activity(task_title: str, description: str) -> list:
    from src.agents.game_designer import GameDesignerAgent
    agent = GameDesignerAgent()
    return await agent.review_design(task_title, description)


@activity.defn
async def domain_experts_activity(design: dict, task_title: str) -> list:
    """SRE, Security, and Lead Dev panel review — uses ModelRouter with Ollama as final fallback."""
    from src.utils.model_router import ModelRouter

    prompt = (
        f"You are a panel of domain experts (SRE, Security, Lead Developer).\n"
        f"Review this design for '{task_title}':\n{json.dumps(design)}\n\n"
        f"Provide 3 critical technical questions for the user.\n"
        f"Respond with JSON: {{\"questions\": [\"question1\", \"question2\", \"question3\"]}}"
    )

    router = ModelRouter()
    try:
        result = await router.chat(prompt=prompt, preferred_model="fast", json_mode=True)
        questions = result.get("questions", [])
        if isinstance(questions, list) and questions:
            return questions
    except Exception as e:
        logger.warning(f"domain_experts_activity failed: {e}")

    return [
        "Could you clarify the expected traffic volume and any SLA requirements?",
        "Are there any new secrets or environment variables required for this feature?",
        "What is the rollback strategy if this change causes a production issue?"
    ]


@activity.defn
async def quarterback_synthesis_activity(bead_id: str, scope: dict, design: dict, infra_questions: list, game_questions: list) -> str:
    from beads_manager import read_bead, update_bead, add_comment
    bead_data = read_bead(bead_id)
    title = bead_data.get('title', 'Unknown Task')
    is_epic = _is_epic(title)

    def to_html_bullets(item):
        if isinstance(item, list):
            return "\n".join([f"<li>{i}</li>" for i in item])
        if isinstance(item, str) and "\n" in item:
            return "\n".join([f"<li>{line.strip('- ').strip()}</li>" for line in item.split("\n") if line.strip()])
        return f"<li>{item}</li>"

    automation_html = to_html_bullets(scope.get('automation_strategy', []))
    infra_q_html = to_html_bullets(infra_questions)
    game_q_html = to_html_bullets(game_questions) if game_questions else "<li>N/A — no game design concerns identified.</li>"
    analysis = scope.get('product_analysis', '').replace('\n\n', '</p><p>').replace('\n', '<br>')

    if is_epic:
        doc = EPIC_TEMPLATE.format(
            title=title,
            product_analysis=analysis,
            automation_strategy=automation_html,
            technical_design=design.get('updated_description', '').replace('\n', '<br>'),
            iac_impact=scope.get('iac_pipeline_impact', '').replace('\n', '<br>'),
        )
    else:
        doc = STORY_TEMPLATE.format(
            title=title,
            product_analysis=analysis,
            technical_design=design.get('updated_description', '').replace('\n', '<br>'),
        )

    doc += f"""
<br><hr>
<h2>🎮 Gameplay & Engagement (Game Designer)</h2>
<ul>
{game_q_html}
</ul>

<br>
<h2>🛡 Infrastructure & Ops (SRE/Architect)</h2>
<ul>
{infra_q_html}
</ul>
<p><em>Please answer these in the comments below to finalize the design. [AGENT_SIGNATURE]</em></p>
"""

    update_bead(bead_id, {"description": doc, "status": "designing"})
    add_comment(bead_id, "👋 **Design Review complete!** I've combined feedback from our Game Designer, Architect, and SRE. Please check the description for outstanding questions and reply in the comments. [AGENT_SIGNATURE]")
    return "Design synthesized."


@activity.defn
async def design_refine_activity(bead_id: str, user_comment: str) -> str:
    """Incorporates a user's comment reply into the existing design and asks follow-up questions."""
    from beads_manager import read_bead, update_bead, add_comment
    from src.utils.model_router import ModelRouter

    bead_data = read_bead(bead_id)
    current_design = bead_data.get("description", "")
    title = bead_data.get("title", "")

    prompt = (
        f"You are continuing a design review for: {title}\n\n"
        f"CURRENT DESIGN DOCUMENT:\n{current_design[:3000]}\n\n"
        f"THE USER REPLIED:\n{user_comment}\n\n"
        f"1. Update the design to incorporate the user's clarification.\n"
        f"2. If any questions remain unanswered, include them.\n"
        f"3. If design is complete, say so.\n\n"
        f"Respond with JSON: {{\"updated_design\": \"<full updated HTML design doc>\", \"follow_up\": \"<short comment to post>\", \"design_complete\": false}}"
    )

    router = ModelRouter()
    try:
        result = await router.chat(prompt=prompt, preferred_model="complex", json_mode=True)
        updated_doc = result.get("updated_design", current_design)
        follow_up = result.get("follow_up", "Thanks for the clarification — design updated!")
        design_complete = result.get("design_complete", False)

        update_bead(bead_id, {"description": updated_doc})

        if design_complete:
            add_comment(bead_id, f"✅ **Design is complete!** Move this task to **Doing** when you're ready to start implementation. [AGENT_SIGNATURE]")
        else:
            add_comment(bead_id, f"📝 **Design updated** based on your feedback.\n\n{follow_up} [AGENT_SIGNATURE]")

    except Exception as e:
        logger.error(f"design_refine_activity failed: {e}")
        add_comment(bead_id, f"⚠️ Could not process your reply automatically. Please continue the conversation manually. [AGENT_SIGNATURE]")

    return "Design refined."


@activity.defn
async def breakdown_activity(bead_id: str) -> str:
    """
    Breaks an Epic into Stories.
    Does NOT call link_beads (that fires task.updated on the epic and causes loops).
    Does NOT move stories to Doing (the fan-out in the workflow does that AFTER starting
    child workflows, so the webhook sees the child workflow already running and skips).
    """
    from beads_manager import read_bead, create_bead, add_comment
    from src.utils.model_router import ModelRouter

    bead_data = read_bead(bead_id)

    prompt = (
        f"EPIC TITLE: {bead_data.get('title')}\n"
        f"EPIC DESIGN: {bead_data.get('description', '')[:2000]}\n\n"
        f"Break this Epic into 3-5 modular, independently implementable STORIES.\n"
        f"Each story should be completable by a single developer agent.\n\n"
        f"Respond ONLY with JSON:\n"
        f"{{\"stories\": [{{\"title\": \"Story Title\", \"description\": \"Clear implementation requirements\"}}]}}"
    )

    router = ModelRouter()
    try:
        result = await router.chat(prompt=prompt, preferred_model="complex", json_mode=True)
        stories = result.get("stories", [])
        if not stories and isinstance(result, list):
            stories = result
    except Exception as e:
        error_msg = f"Breakdown failed: {e}"
        add_comment(bead_id, f"❌ **Breakdown Failed:** {error_msg} [AGENT_SIGNATURE]")
        return error_msg

    if not isinstance(stories, list) or not stories:
        add_comment(bead_id, "❌ **Breakdown Failed:** Could not parse stories from LLM response. [AGENT_SIGNATURE]")
        return "Breakdown failed: no stories parsed."

    created_ids = []
    for story in stories:
        child_id = create_bead(
            title=f"[STORY] {story['title']}",
            description=story['description'],
            requesting_agent="quarterback-breakdown",
            parent_id=bead_id
        )
        created_ids.append(child_id)

    add_comment(bead_id, f"✅ **Epic Breakdown Complete!** Created {len(stories)} stories. Starting parallel implementation. [AGENT_SIGNATURE]")
    return json.dumps(created_ids)


@activity.defn
async def get_task_title_activity(bead_id: str) -> str:
    """Fetches task title from Vikunja. Used in workflow code to avoid direct I/O."""
    from beads_manager import read_bead
    return read_bead(bead_id).get("title", "")


@activity.defn
async def get_bead_context_activity(bead_id: str) -> dict:
    """Fetches bead context. Used for alert payloads."""
    from beads_manager import read_bead
    return read_bead(bead_id).get("context", {})


@activity.defn
async def mark_breakdown_started_activity(bead_id: str) -> None:
    """
    Stamps [BREAKDOWN_STARTED] into the epic description so the webhook ignores
    any Vikunja retry events for this epic while breakdown is in progress.
    Removed once the epic moves to Validation.
    """
    from beads_manager import read_bead, update_bead
    bead = read_bead(bead_id)
    desc = bead.get("description", "")
    if "[BREAKDOWN_STARTED]" not in desc:
        update_bead(bead_id, {"description": desc + "\n\n[BREAKDOWN_STARTED]"})


@activity.defn
async def clear_breakdown_marker_activity(bead_id: str) -> None:
    """Removes the [BREAKDOWN_STARTED] marker so the epic can be re-triggered later."""
    from beads_manager import read_bead, update_bead
    bead = read_bead(bead_id)
    desc = bead.get("description", "").replace("\n\n[BREAKDOWN_STARTED]", "").replace("[BREAKDOWN_STARTED]", "")
    update_bead(bead_id, {"description": desc})


@activity.defn
async def move_task_activity(bead_id: str, bucket_name: str) -> str:
    """Moves a Vikunja task and updates metadata stage."""
    from beads_manager import update_bead
    update_bead(bead_id, {"stage": bucket_name.upper()})
    return f"Moved {bead_id} to {bucket_name}"


@activity.defn
async def post_comment_activity(bead_id: str, message: str) -> None:
    """Posts a comment on a Vikunja task. Safe to call from workflow via execute_activity."""
    from beads_manager import add_comment
    add_comment(bead_id, message)


@activity.defn
async def check_epic_completion_activity(bead_id: str) -> str:
    """
    After a story completes Validation, check if all sibling stories under the
    parent Epic are done. If so, post a summary on the Epic and move it to Validation.
    """
    import httpx
    import os
    from beads_manager import read_bead, add_comment, move_to_bucket

    story = read_bead(bead_id)
    parent_epic_id = story.get("context", {}).get("parent_epic_id")
    if not parent_epic_id:
        return "SKIPPED: No parent epic on this task."

    epic = read_bead(parent_epic_id)
    internal_id = epic["id"]

    vikunja_url = os.getenv("VIKUNJA_BASE_URL", "https://tracker.bestfam.us/api/v1")
    headers = {
        "Authorization": f"Bearer {os.getenv('VIKUNJA_API_TOKEN')}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client() as client:
            response = client.get(f"{vikunja_url}/tasks/{internal_id}", headers=headers)
            response.raise_for_status()
            task_data = response.json()
    except Exception as e:
        logger.error(f"check_epic_completion: could not fetch epic {parent_epic_id}: {e}")
        return f"ERROR: {e}"

    subtasks = task_data.get("related_tasks", {}).get("subtask", [])
    if not subtasks:
        return "SKIPPED: Epic has no subtasks."

    total = len(subtasks)
    done_count = sum(1 for s in subtasks if s.get("done", False))
    logger.info(f"Epic {parent_epic_id}: {done_count}/{total} stories done.")

    if done_count < total:
        return f"In progress: {done_count}/{total} stories complete."

    # All stories done — update epic and move to Validation
    add_comment(
        parent_epic_id,
        f"🏆 **All {total} stories complete!** This Epic is ready for review. Moving to Validation. [AGENT_SIGNATURE]"
    )
    move_to_bucket(parent_epic_id, "Validation")
    return f"Epic {parent_epic_id} moved to Validation — all {total} stories done."


# --- Mayor Workflow ---

@workflow.defn
class MayorWorkflow:
    @workflow.run
    async def run(self, *args) -> str:
        # Normalize args: may be called as (list,) or (id, bucket) or (id, bucket, comment)
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]

        bead_id = str(args[0])
        bucket = args[1] if len(args) > 1 else "Design"
        extra = args[2] if len(args) > 2 else None

        retry = RetryPolicy(initial_interval=timedelta(seconds=2), maximum_attempts=3)
        fast_retry = RetryPolicy(maximum_attempts=1)

        # ─── DESIGN: full pipeline ────────────────────────────────────────────
        if bucket == "Design":
            scope = await workflow.execute_activity(
                ba_design_activity, bead_id,
                start_to_close_timeout=timedelta(minutes=15), retry_policy=retry)

            design = await workflow.execute_activity(
                architect_design_activity, scope,
                start_to_close_timeout=timedelta(minutes=15), retry_policy=retry)

            # title/desc for game designer is read inside ba_design_activity scope dict
            game_questions = await workflow.execute_activity(
                game_designer_activity,
                args=[scope.get("title", ""), scope.get("product_analysis", "")],
                start_to_close_timeout=timedelta(minutes=10), retry_policy=retry)

            infra_questions = await workflow.execute_activity(
                domain_experts_activity,
                args=[design, scope.get("title", "")],
                start_to_close_timeout=timedelta(minutes=5), retry_policy=retry)

            return await workflow.execute_activity(
                quarterback_synthesis_activity,
                args=[bead_id, scope, design, infra_questions, game_questions],
                start_to_close_timeout=timedelta(minutes=2))

        # ─── DESIGN REFINE: incorporate user reply ────────────────────────────
        elif bucket == "DesignRefine":
            user_comment = extra or ""
            return await workflow.execute_activity(
                design_refine_activity,
                args=[bead_id, user_comment],
                start_to_close_timeout=timedelta(minutes=10), retry_policy=retry)

        # ─── DOING: epic → breakdown; story → implement → hand off to Validation ─
        elif bucket == "Doing":
            title = await workflow.execute_activity(
                get_task_title_activity, bead_id,
                start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)

            logger.info(f"[{bead_id}] Mayor Doing: title='{title}'")

            # GASTOWN ALERTING (V2.5)
            if title.startswith("[ALERT]"):
                context = await workflow.execute_activity(
                    get_bead_context_activity, bead_id,
                    start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)

                if context.get("type") == "DISCORD_ALERT":
                    alert_data = context.get("alert_data")
                    from src.workers.polecat_activities import discord_alert_activity
                    res = await workflow.execute_activity(
                        discord_alert_activity, alert_data,
                        start_to_close_timeout=timedelta(minutes=1),
                        task_queue="betting-app-queue", retry_policy=retry)

                    await workflow.execute_activity(
                        move_task_activity, args=[bead_id, "Done"],
                        start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)
                    return f"Alert dispatched: {res}"

            if _is_story(title):
                logger.info(f"[{bead_id}] Mayor: Story detected — routing to Polecat.")
                target_queue = await workflow.execute_activity(
                    triage_task_queue, bead_id,
                    start_to_close_timeout=timedelta(seconds=60), retry_policy=fast_retry)

                dev_result = await workflow.execute_activity(
                    polecat_developer_activity, bead_id,
                    start_to_close_timeout=timedelta(minutes=30),
                    task_queue=target_queue, retry_policy=fast_retry)

                if isinstance(dev_result, str) and ("ERROR" in dev_result.upper() or "EXCEPTION" in dev_result.upper()):
                    raise Exception(f"Implementation Failed: {dev_result}")

                await workflow.execute_activity(
                    move_task_activity, args=[bead_id, "Validation"],
                    start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)

                return f"Doing complete — Dev: {dev_result} | Moved to Validation."

            else:
                # Epic → breakdown into stories, then fan-out and await all.
                # ANTI-LOOP: mark the epic description FIRST so that Vikunja webhook
                # retries see [BREAKDOWN_STARTED] and are ignored by the webhook filter.
                await workflow.execute_activity(
                    mark_breakdown_started_activity, bead_id,
                    start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)
                logger.info(f"[{bead_id}] Mayor: Epic detected — initiating breakdown.")
                breakdown_result = await workflow.execute_activity(
                    breakdown_activity, bead_id,
                    start_to_close_timeout=timedelta(minutes=10), retry_policy=retry)

                try:
                    story_ids = json.loads(breakdown_result)
                except Exception:
                    return f"Breakdown complete (no story IDs returned): {breakdown_result}"

                # Fan-out: start child workflow FIRST, then move story to "Doing" in Vikunja.
                # Order matters: start_child_workflow before move_task_activity so that
                # the webhook (triggered by move_to_bucket) sees the child already running
                # and returns "skipped" instead of starting a duplicate.
                story_handles = []
                for story_id in story_ids:
                    handle = await workflow.start_child_workflow(
                        MayorWorkflow,
                        args=[[str(story_id), "Doing"]],
                        id=f"agile-task-{story_id}-doing-entry",
                        task_queue="main-orchestrator-queue",
                    )
                    story_handles.append(handle)
                    # Move to Doing in UI AFTER child workflow is started
                    await workflow.execute_activity(
                        move_task_activity, args=[str(story_id), "Doing"],
                        start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)

                # Fan-in: wait for all stories to complete
                logger.info(f"[{bead_id}] Mayor: Waiting for {len(story_handles)} stories to complete.")
                await asyncio.gather(*story_handles, return_exceptions=True)

                # All stories done — clear breakdown marker, move epic to Validation
                await workflow.execute_activity(
                    clear_breakdown_marker_activity, bead_id,
                    start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)
                await workflow.execute_activity(
                    post_comment_activity,
                    args=[bead_id, f"🏆 **All {len(story_ids)} stories complete!** Moving Epic to Validation. [AGENT_SIGNATURE]"],
                    start_to_close_timeout=timedelta(seconds=30))
                await workflow.execute_activity(
                    move_task_activity, args=[bead_id, "Validation"],
                    start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)
                return f"Epic complete — {len(story_ids)} stories done. Moved to Validation."

        # ─── VALIDATION: run Refinery gates → Done ────────────────────────────
        elif bucket == "Validation":
            logger.info(f"[{bead_id}] Mayor: Validation triggered — starting Refinery.")
            try:
                refinery_result = await workflow.execute_child_workflow(
                    "RefineryWorkflow", bead_id,
                    id=f"refinery-{bead_id}",
                    task_queue="refinery-queue")
                if isinstance(refinery_result, str) and refinery_result.startswith("FAILED"):
                    raise Exception(f"Refinery Gate Failed: {refinery_result}")
                return f"Validation complete: {refinery_result}"
            except Exception as e:
                logger.error(f"[{bead_id}] Mayor: Refinery Failed! Engaging SRE Agent.")
                await workflow.execute_activity(
                    post_comment_activity,
                    args=[bead_id, f"🚨 **Refinery Gate Failed:** Engaging SRE Agent to investigate logs and heal the system. Error: {str(e)}"],
                    start_to_close_timeout=timedelta(seconds=30)
                )
                # Trigger SRE Healing
                sre_result = await workflow.execute_child_workflow(
                    "SREHealingWorkflow",
                    id=f"sre-healing-{bead_id}",
                    task_queue="sre-queue"
                )
                return f"Refinery failed, but SRE Healing completed: {sre_result}"

        return f"Mayor ignored bucket: {bucket}"
