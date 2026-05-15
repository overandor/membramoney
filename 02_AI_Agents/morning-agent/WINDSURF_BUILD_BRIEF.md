# Windsurf Build Brief - Morning Agent

Paste this entire document into Windsurf to generate the complete Morning Agent scaffold.

---

## Project Overview

Build an App Store-ready MVP called "Morning Agent" - an iPhone app where users can type or dictate tasks in the morning, and the backend executes phone-call tasks autonomously during the day.

**Architecture:** SwiftUI iPhone app as control surface, Python FastAPI backend for telephony/task orchestration, Twilio for outbound calls, OpenAI Realtime API for speech-to-speech AI voice.

**App Store Safety:** Frame as "AI assistant calling on user's behalf with disclosure and controls" rather than impersonation. The voice assistant discloses it is calling on behalf of the user.

---

## Constraints

- iPhone app in SwiftUI
- Backend in Python FastAPI
- PostgreSQL-ready data model, SQLite acceptable for local MVP
- Twilio for outbound phone calls
- Twilio Media Streams for realtime call audio bridge
- OpenAI Realtime API for speech-to-speech handling
- Push notifications optional for MVP
- Clear disclosure model: voice assistant says it is calling on behalf of user
- No fake placeholders for endpoint names
- Production-style structure, env config, logging, health endpoint
- Must run locally first
- Must be clean enough to deploy to Render/Fly.io/Railway

---

## Repository Structure

```
morning-agent/
  backend/
    app/
      main.py
      config.py
      db.py
      models.py
      schemas.py
      services/
        tasks.py
        twilio_client.py
        openai_realtime.py
      routers/
        tasks.py
        twilio.py
    requirements.txt
    .env.example
  ios/
    MorningAgent/
      MorningAgentApp.swift
      ContentView.swift
      Models/
        TaskItem.swift
      Services/
        APIClient.swift
      Views/
        TaskListView.swift
        NewTaskView.swift
        TaskDetailView.swift
        SettingsView.swift
```

---

## Backend Files to Generate

### 1. backend/requirements.txt
```
fastapi==0.115.12
uvicorn[standard]==0.34.2
sqlmodel==0.0.24
twilio==9.5.2
python-dotenv==1.0.1
httpx==0.28.1
websockets==15.0.1
```

### 2. backend/.env.example
```
APP_BASE_URL=https://your-backend.example.com
PUBLIC_WS_BASE=wss://your-backend.example.com
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_FROM_NUMBER=+15555550123
OPENAI_API_KEY=sk-...
OPENAI_REALTIME_MODEL=gpt-realtime-1.5
SQLITE_PATH=./morning_agent.db
DISCLOSURE_LINE=Hello, this is Joseph's AI assistant calling on his behalf.
```

### 3. backend/app/config.py
```python
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")
    public_ws_base: str = os.getenv("PUBLIC_WS_BASE", "ws://localhost:8000")
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from_number: str = os.getenv("TWILIO_FROM_NUMBER", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_realtime_model: str = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-1.5")
    sqlite_path: str = os.getenv("SQLITE_PATH", "./morning_agent.db")
    disclosure_line: str = os.getenv(
        "DISCLOSURE_LINE",
        "Hello, this is Joseph's AI assistant calling on his behalf."
    )

settings = Settings()
```

### 4. backend/app/db.py
```python
from sqlmodel import SQLModel, create_engine, Session
from .config import settings

engine = create_engine(f"sqlite:///{settings.sqlite_path}", echo=False)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
```

### 5. backend/app/models.py
```python
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    instructions: str
    phone_number: str
    status: str = "queued"  # queued, calling, completed, failed, needs_review
    call_sid: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 6. backend/app/schemas.py
```python
from typing import Optional
from pydantic import BaseModel

class TaskCreate(BaseModel):
    title: str
    instructions: str
    phone_number: str

class TaskRead(BaseModel):
    id: int
    title: str
    instructions: str
    phone_number: str
    status: str
    call_sid: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None

class StartTaskResponse(BaseModel):
    task_id: int
    status: str
    call_sid: Optional[str]
```

### 7. backend/app/services/twilio_client.py
```python
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
```

### 8. backend/app/services/openai_realtime.py
```python
import json
import websockets
from ..config import settings

class RealtimeBridge:
    def __init__(self, task_id: int, instructions: str):
        self.task_id = task_id
        self.instructions = instructions
        self.transcript_parts: list[str] = []

    async def open(self):
        self.ws = await websockets.connect(
            "wss://api.openai.com/v1/realtime",
            additional_headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "OpenAI-Beta": "realtime=v1",
            },
        )
        session_update = {
            "type": "session.update",
            "session": {
                "model": settings.openai_realtime_model,
                "instructions": (
                    f"{settings.disclosure_line} "
                    "You are a phone agent. Complete the task if possible. "
                    "Do not claim to be the user. "
                    f"Task instructions: {self.instructions}"
                )
            }
        }
        await self.ws.send(json.dumps(session_update))

    async def close(self):
        if getattr(self, "ws", None):
            await self.ws.close()
```

### 9. backend/app/routers/tasks.py
```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Task
from ..schemas import TaskCreate, StartTaskResponse
from ..services.twilio_client import create_outbound_call

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("")
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    task = Task(
        title=payload.title,
        instructions=payload.instructions,
        phone_number=payload.phone_number,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@router.get("")
def list_tasks(session: Session = Depends(get_session)):
    return session.exec(select(Task).order_by(Task.id.desc())).all()

@router.get("/{task_id}")
def get_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/{task_id}/start", response_model=StartTaskResponse)
def start_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    call_sid = create_outbound_call(task_id=task.id, to_number=task.phone_number)
    task.call_sid = call_sid
    task.status = "calling"
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    return StartTaskResponse(task_id=task.id, status=task.status, call_sid=call_sid)
```

### 10. backend/app/routers/twilio.py
```python
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
```

### 11. backend/app/main.py
```python
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlmodel import Session
from .db import engine, init_db
from .models import Task
from .routers.tasks import router as tasks_router
from .routers.twilio import router as twilio_router
from .services.openai_realtime import RealtimeBridge

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
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            await ws.close(code=1008)
            return
        bridge = RealtimeBridge(task_id=task.id, instructions=task.instructions)
    await bridge.open()
    transcript_parts: list[str] = []
    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)
            event = data.get("event")
            if event == "start":
                pass
            elif event == "media":
                # TODO: Decode Twilio base64 audio, forward to OpenAI, receive response, send back to Twilio
                pass
            elif event == "stop":
                break
    except WebSocketDisconnect:
        pass
    finally:
        await bridge.close()
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if task:
                task.transcript = "\n".join(transcript_parts) if transcript_parts else task.transcript
                task.summary = task.summary or "Call finished. Review transcript."
                task.updated_at = datetime.utcnow()
                session.add(task)
                session.commit()
```

---

## iOS Files to Generate

### 12. ios/MorningAgent/MorningAgentApp.swift
```swift
import SwiftUI

@main
struct MorningAgentApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
```

### 13. ios/MorningAgent/Models/TaskItem.swift
```swift
import Foundation

struct TaskItem: Codable, Identifiable {
    let id: Int
    let title: String
    let instructions: String
    let phoneNumber: String?
    let status: String
    let callSid: String?
    let transcript: String?
    let summary: String?

    enum CodingKeys: String, CodingKey {
        case id, title, instructions, status, transcript, summary
        case phoneNumber = "phone_number"
        case callSid = "call_sid"
    }
}

struct CreateTaskRequest: Codable {
    let title: String
    let instructions: String
    let phone_number: String
}
```

### 14. ios/MorningAgent/Services/APIClient.swift
```swift
import Foundation

@MainActor
final class APIClient: ObservableObject {
    static let shared = APIClient()
    private let baseURL = URL(string: "http://localhost:8000")!

    func fetchTasks() async throws -> [TaskItem] {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appendingPathComponent("tasks"))
        return try JSONDecoder().decode([TaskItem].self, from: data)
    }

    func createTask(title: String, instructions: String, phone: String) async throws -> TaskItem {
        var request = URLRequest(url: baseURL.appendingPathComponent("tasks"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            CreateTaskRequest(title: title, instructions: instructions, phone_number: phone)
        )
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(TaskItem.self, from: data)
    }

    func startTask(id: Int) async throws {
        var request = URLRequest(url: baseURL.appendingPathComponent("tasks/\(id)/start"))
        request.httpMethod = "POST"
        _ = try await URLSession.shared.data(for: request)
    }

    func fetchTask(id: Int) async throws -> TaskItem {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appendingPathComponent("tasks/\(id)"))
        return try JSONDecoder().decode(TaskItem.self, from: data)
    }
}
```

### 15. ios/MorningAgent/Views/TaskListView.swift
```swift
import SwiftUI

struct TaskListView: View {
    @State private var tasks: [TaskItem] = []
    @State private var showingNewTask = false
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            List(tasks) { task in
                NavigationLink(destination: TaskDetailView(taskID: task.id)) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(task.title).font(.headline)
                        Text(task.status.capitalized).font(.subheadline)
                        if let summary = task.summary, !summary.isEmpty {
                            Text(summary).font(.footnote).foregroundStyle(.secondary).lineLimit(2)
                        }
                    }
                }
            }
            .navigationTitle("Morning Agent")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingNewTask = true } label: { Image(systemName: "plus") }
                }
            }
            .sheet(isPresented: $showingNewTask) {
                NewTaskView { await load() }
            }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            tasks = try await APIClient.shared.fetchTasks()
        } catch {
            print("Failed to fetch tasks:", error)
        }
    }
}
```

### 16. ios/MorningAgent/Views/NewTaskView.swift
```swift
import SwiftUI

struct NewTaskView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var instructions = ""
    @State private var phone = ""
    @State private var isSaving = false
    let onSaved: () async -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Task") {
                    TextField("Title", text: $title)
                    TextField("Phone number", text: $phone)
                    TextEditor(text: $instructions).frame(minHeight: 160)
                }
            }
            .navigationTitle("New Task")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Save") { Task { await save() } }
                    .disabled(isSaving || title.isEmpty || phone.isEmpty || instructions.isEmpty)
                }
            }
        }
    }

    private func save() async {
        guard !isSaving else { return }
        isSaving = true
        defer { isSaving = false }
        do {
            let task = try await APIClient.shared.createTask(title: title, instructions: instructions, phone: phone)
            try await APIClient.shared.startTask(id: task.id)
            await onSaved()
            dismiss()
        } catch {
            print("Save failed:", error)
        }
    }
}
```

### 17. ios/MorningAgent/Views/TaskDetailView.swift
```swift
import SwiftUI

struct TaskDetailView: View {
    let taskID: Int
    @State private var task: TaskItem?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let task {
                    Text(task.title).font(.title2).bold()
                    Text("Status: \(task.status)")
                    Text(task.instructions)
                    if let summary = task.summary {
                        Group {
                            Text("Summary").font(.headline)
                            Text(summary)
                        }
                    }
                    if let transcript = task.transcript {
                        Group {
                            Text("Transcript").font(.headline)
                            Text(transcript).font(.footnote).textSelection(.enabled)
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .padding()
        }
        .navigationTitle("Task")
        .task { await load() }
    }

    private func load() async {
        do {
            task = try await APIClient.shared.fetchTask(id: taskID)
        } catch {
            print("Load failed:", error)
        }
    }
}
```

### 18. ios/MorningAgent/ContentView.swift
```swift
import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            TaskListView()
                .tabItem { Label("Tasks", systemImage: "checklist") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}
```

### 19. ios/MorningAgent/Views/SettingsView.swift
```swift
import SwiftUI

struct SettingsView: View {
    var body: some View {
        NavigationStack {
            Form {
                Section("Agent") {
                    Text("This assistant places calls on your behalf.")
                    Text("Recommended: always disclose that the assistant is acting for you.")
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
    }
}
```

---

## Next Steps for Windsurf

After generating the scaffold, implement these 4 upgrades in order:

1. **Finish the Twilio ↔ OpenAI Realtime websocket bridge** in `/media-stream` - decode Twilio base64 audio, forward to OpenAI, receive response, send back to Twilio
2. **Add transcript persistence** and a final task summarizer
3. **Add retry logic**, voicemail detection, and escalation statuses
4. **Replace polling in SwiftUI** with push notifications or server-sent updates

---

## Local Run Instructions

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Twilio and OpenAI credentials
uvicorn app.main:app --reload
```

**iPhone App:**
- Create project in Xcode first (see XCODE_WINDSURF_WORKFLOW.md)
- Copy Swift files to Xcode project
- Add files to Xcode project navigator
- Configure signing
- Run in simulator (Cmd+R)
