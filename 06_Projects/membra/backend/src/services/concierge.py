import os
import json
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import IntentRequest, IntentOut
from src.services.orchestration import create_objective
from src.services.governance import log_audit_event

def parse_intent(data: IntentRequest) -> IntentOut:
    """
    IntentOS: Convert human chat into structured objectives.
    Uses Groq when available; falls back to deterministic parsing.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    parsed = None
    suggested = []

    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            system_prompt = (
                "You are MEMBRA IntentOS. Parse the user's message into a structured objective. "
                "Return ONLY valid JSON with keys: parsed_objective (string), suggested_actions (list of dicts with action and description)."
            )
            resp = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": data.message},
                ],
                max_tokens=512,
                temperature=0.2,
            )
            raw = resp.choices[0].message.content
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("\n", 1)[0]
            parsed = json.loads(raw)
        except Exception:
            parsed = None

    if not parsed:
        # Deterministic fallback
        parsed = _deterministic_parse(data.message)

    suggested = parsed.get("suggested_actions", [])
    conn = get_connection()
    iid = generate_id("int_")
    conn.execute(
        "INSERT INTO objectives (objective_id, owner_id, title, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (iid, data.user_id or "anon", parsed["parsed_objective"], data.message, "draft", "medium", now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()

    # Audit trail
    log_audit_event(
        event_type="intent_parsed",
        actor_id=data.user_id or "anon",
        target_type="objective",
        target_id=iid,
        details={"original": data.message, "parsed": parsed["parsed_objective"], "method": "llm" if groq_key else "deterministic"},
    )

    return IntentOut(
        intent_id=iid,
        user_id=data.user_id,
        original_message=data.message,
        parsed_objective=parsed["parsed_objective"],
        suggested_actions=suggested,
        created_at=now_iso(),
    )

def _deterministic_parse(message: str) -> dict:
    msg = message.lower()
    actions = []

    # Simple keyword-based intent parsing
    if any(w in msg for w in ("window", "car", "drill", "apartment", "room", "space")):
        actions.append({"action": "register_world_asset", "description": "Register user's physical asset in WorldBridge"})
    if any(w in msg for w in ("task", "work", "help", "job", "bounty", "need someone")):
        actions.append({"action": "create_job", "description": "Create a local job or bounty"})
    if any(w in msg for w in ("ad", "advertise", "campaign", "promote", "poster")):
        actions.append({"action": "create_ad_campaign", "description": "Create an ad campaign for available media"})
    if any(w in msg for w in ("rent", "book", "reserve", "use space")):
        actions.append({"action": "create_reservation", "description": "Book an asset visit"})
    if any(w in msg for w in ("kpi", "dashboard", "report", "analytics", "metrics")):
        actions.append({"action": "view_dashboard", "description": "Open the KPI dashboard"})
    if any(w in msg for w in ("money", "pay", "payout", "settlement", "invoice")):
        actions.append({"action": "check_settlement", "description": "Review settlement eligibility"})
    if any(w in msg for w in ("approve", "policy", "governance", "risk", "rule")):
        actions.append({"action": "create_approval", "description": "Submit an approval request"})

    if not actions:
        actions.append({"action": "chat", "description": "Continue conversation with Concierge"})

    return {
        "parsed_objective": message[:120],
        "suggested_actions": actions,
    }
