from twilio.rest import Client
from ..config import settings

def get_twilio_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)

def create_outbound_call(task_id: int, to_number: str) -> str:
    client = get_twilio_client()
    call = client.calls.create(
        to=to_number,
        from_=settings.twilio_from_number,
        url=f"{settings.app_base_url}/twilio/outbound-twiml?task_id={task_id}",
        status_callback=f"{settings.app_base_url}/calls/status?task_id={task_id}",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
    )
    return call.sid
