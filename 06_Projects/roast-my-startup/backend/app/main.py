from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import HttpUrl
from typing import Dict, Any
import uuid
from datetime import datetime
import asyncio
from .models import RoastRequest, RoastJob, RoastReport
from .services.scraper import WebScraper
from .services.llm_generator import LLMGenerator

app = FastAPI(title="Roast My Startup API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scraper = WebScraper()
llm_generator = LLMGenerator()

roast_jobs: Dict[str, Dict[str, Any]] = {}
roast_reports: Dict[str, Dict[str, Any]] = {}

async def process_roast(job_id: str, url: str, description: str, intensity: str):
    """Background task to process a roast request."""
    try:
        roast_jobs[job_id]["status"] = "processing"
        roast_jobs[job_id]["stage"] = "Fetching page..."
        
        evidence = await scraper.scrape(str(url))
        
        roast_jobs[job_id]["stage"] = "Analyzing with AI agents..."
        
        report = llm_generator.generate_roast(evidence, intensity)
        
        slug = f"{report['startup_name'].lower().replace(' ', '-')}-{job_id[:8]}"
        
        roast_reports[slug] = {
            **report,
            "slug": slug,
            "created_at": datetime.utcnow().isoformat(),
            "job_id": job_id
        }
        
        roast_jobs[job_id]["status"] = "completed"
        roast_jobs[job_id]["stage"] = "Complete"
        roast_jobs[job_id]["slug"] = slug
        
    except Exception as e:
        roast_jobs[job_id]["status"] = "failed"
        roast_jobs[job_id]["error"] = str(e)

@app.post("/api/roasts")
async def create_roast(request: RoastRequest, background_tasks: BackgroundTasks):
    """Create a new roast job."""
    job_id = str(uuid.uuid4())
    
    roast_jobs[job_id] = {
        "id": job_id,
        "url": str(request.url),
        "status": "queued",
        "stage": "Waiting to start...",
        "created_at": datetime.utcnow().isoformat(),
        "intensity": request.intensity,
        "visibility": request.visibility
    }
    
    background_tasks.add_task(
        process_roast,
        job_id,
        request.url,
        request.description,
        request.intensity
    )
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/roasts/{job_id}")
async def get_roast_status(job_id: str):
    """Get the status of a roast job."""
    if job_id not in roast_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return roast_jobs[job_id]

@app.get("/api/reports/{slug}")
async def get_report(slug: str):
    """Get a roast report by slug."""
    if slug not in roast_reports:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return roast_reports[slug]

@app.get("/api/gallery")
async def get_gallery():
    """Get public roast gallery."""
    public_reports = [
        r for r in roast_reports.values()
        if r.get("visibility", "public") == "public"
    ]
    return sorted(public_reports, key=lambda x: x["created_at"], reverse=True)[:20]

@app.get("/")
async def root():
    return {"message": "Roast My Startup API"}
