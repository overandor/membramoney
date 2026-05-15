import json
import base64
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from .db import engine, init_db
from .models import Task
from .routers.tasks import router as tasks_router
from .routers.twilio import router as twilio_router
from .services.openai_realtime import RealtimeBridge
from .services.groq_llm import get_groq_llm
from .services.stt_service import STTService
from .services.tts_service import TTSService

app = FastAPI(title="Morning Agent Backend")

app.include_router(tasks_router)
app.include_router(twilio_router)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.websocket("/media-stream")
async def media_stream(ws: WebSocket):
    await ws.accept()
    task_id = int(ws.query_params["task_id"])

    # DB read
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            await ws.close(code=1008)
            return
        bridge = RealtimeBridge(task_id=task.id, instructions=task.instructions)
        groq_llm = get_groq_llm()
        stt_service = STTService()
        tts_service = TTSService()

    await bridge.open()

    transcript_parts: list[str] = []
    conversation_history = []

    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)

            event = data.get("event")
            if event == "start":
                # Connection established
                print(f"Media stream started for task {task_id}")
            elif event == "media":
                # Audio frame received from Twilio
                try:
                    # 1) Decode Twilio base64 audio payload
                    payload = data.get("media", {}).get("payload")
                    if not payload:
                        continue
                    
                    # 2) Use STT service to convert to text
                    text = await stt_service.transcribe_from_base64(payload)
                    
                    if text and text != "[AUDIO RECEIVED - STT SERVICE NOT CONFIGURED]":
                        # 3) Process with Groq LLM
                        response = await groq_llm.process(
                            text=text,
                            instructions=task.instructions,
                            conversation_history=conversation_history
                        )
                        
                        # Update conversation history
                        conversation_history.append({"role": "user", "content": text})
                        conversation_history.append({"role": "assistant", "content": response})
                        
                        # Add to transcript
                        transcript_parts.append(f"Caller: {text}")
                        transcript_parts.append(f"Agent: {response}")
                        
                        # 4) Use TTS service to convert response to audio
                        audio_response = await tts_service.synthesize_to_base64(response)
                        
                        # 5) Send audio back to Twilio if TTS succeeded
                        if audio_response:
                            await ws.send(json.dumps({
                                "event": "media",
                                "media": {"payload": audio_response}
                            }))
                        else:
                            # TTS not configured, log text response
                            print(f"Agent response (TTS stub): {response}")
                    
                except Exception as e:
                    print(f"Error processing media frame: {e}")
                    
            elif event == "stop":
                # Call ended
                print(f"Media stream stopped for task {task_id}")
                break
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        print(f"Error in media stream: {e}")
    finally:
        await bridge.close()
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if task:
                task.transcript = "\n".join(transcript_parts) if transcript_parts else task.transcript
                
                # Use Groq to summarize if we have a transcript
                if task.transcript and not task.summary:
                    try:
                        task.summary = await groq_llm.summarize_transcript(
                            task.transcript, 
                            task.instructions
                        )
                        
                        # Check task completion
                        completion_check = await groq_llm.check_task_completion(
                            task.transcript,
                            task.instructions
                        )
                        if completion_check.get("completed"):
                            task.status = "completed"
                        else:
                            task.status = "needs_review"
                    except Exception as e:
                        print(f"Error summarizing with Groq: {e}")
                        task.summary = task.summary or "Call finished. Review transcript."
                
                task.updated_at = datetime.utcnow()
                session.add(task)
                session.commit()
