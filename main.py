import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from logger import logger
from tasks import create_task, run_analysis_pipeline, get_task_status

# Load environment variables
load_dotenv()

app = FastAPI(title="US Stock Financial & Trend Analyzer Backend")

# Enable CORS for local Streamlit communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development we can allow all, or restrict to http://localhost:8501
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "US Stock Analysis Backend is running."}

@app.post("/api/analyze")
def analyze_stock(ticker: str, background_tasks: BackgroundTasks):
    """
    Triggers the async background stock analysis pipeline.
    """
    if not ticker or not ticker.strip():
        raise HTTPException(status_code=400, detail="Ticker parameter is required.")
        
    ticker_clean = ticker.strip().upper()
    logger.info(f"Received API request to analyze ticker: {ticker_clean}")
    
    # 1. Create a task in state PENDING
    task_id = create_task(ticker_clean)
    
    # 2. Add pipeline task to background executor
    background_tasks.add_task(run_analysis_pipeline, task_id, ticker_clean)
    
    return {"task_id": task_id, "status": "PENDING"}

@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    """
    Retrieves the current status, stage, data, or error message of a task.
    """
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task
