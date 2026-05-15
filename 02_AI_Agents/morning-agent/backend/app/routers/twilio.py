from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlmodel import Session

from ..config import settings
from ..db import get_session
from ..models import Task

router = APIRouter(tags=["twilio"])

@router.post("/twilio/outbound-twiml")
@router.get("/twilio/outbound-twiml")
async def outbound_twiml(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        xml = """<?xml version="1.0" encoding="UTF-8"?><Response><Say>Task not found.</Say></Response>"""
        return Response(content=xml, media_type="application/xml")

    # Twilio will request this TwiML after the outbound call is created.
    # <Connect><Stream> enables bidirectional audio over WebSockets.
    stream_url = f"{settings.public_ws_base}/media-stream?task_id={task_id}"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>{settings.disclosure_line}</Say>
  <Connect>
    <Stream url="{stream_url}" />
  </Connect>
</Response>
"""
    return Response(content=xml, media_type="application/xml")

@router.post("/calls/status")
async def calls_status(task_id: int, request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    call_status = str(form.get("CallStatus", "unknown"))

    task = session.get(Task, task_id)
    if task:
        if call_status == "completed" and task.status == "calling":
            task.status = "completed" if task.summary else "needs_review"
        elif call_status in {"busy", "no-answer", "failed", "canceled"}:
            task.status = "failed"
        task.updated_at = datetime.utcnow()
        session.add(task)
        session.commit()

    return {"ok": True}
