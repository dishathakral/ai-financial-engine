from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .services.parser import parse_excel, extract_merchant
from .services.categorizer import categorize_transactions
from .services.analyzer import analyze_transactions
from .services.ai_engine import generate_insights, chat_with_context, generate_top_banner
from .services.merchant_cleaner import clean_merchant_name
from .services.storage import (
    generate_file_hash, check_duplicate_session, create_session, 
    get_all_sessions, get_session, update_session, update_learned_merchants,
    rename_session, delete_session
)
from pydantic import BaseModel

class InsightsRequest(BaseModel):
    session_id: str

class RecalculateRequest(BaseModel):
    session_id: str
    transactions: list
    merchant_changes: dict = {}

class ChatRequest(BaseModel):
    session_id: str
    message: str

class RenameRequest(BaseModel):
    session_id: str
    new_name: str

app = FastAPI(title="AI Financial Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/check_duplicate")
async def check_duplicate(file: UploadFile = File(...)):
    content = await file.read()
    file_hash = generate_file_hash(file.filename, content)
    session_id = check_duplicate_session(file_hash)
    if session_id:
        return {"exists": True, "session_id": session_id}
    return {"exists": False}

@app.post("/analyze")
async def analyze_statement(file: UploadFile = File(...), password: str = Form(None), force_duplicate: bool = Form(False)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported.")
    
    content = await file.read()
    
    if not force_duplicate:
        file_hash = generate_file_hash(file.filename, content)
        session_id = check_duplicate_session(file_hash)
        if session_id:
            return {"status": "exists", "session_id": session_id}
            
    try:
        transactions = parse_excel(content, password)
        transactions = categorize_transactions(transactions)
        stats = analyze_transactions(transactions)
        
        session_id = create_session(file.filename, content, transactions, stats)
        
        return {
            "status": "success",
            "session_id": session_id,
            "stats": stats,
            "transactions": transactions
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
async def list_sessions():
    return {"sessions": get_all_sessions()}

@app.get("/sessions/{session_id}")
async def fetch_session(session_id: str):
    data = get_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # --- Auto-heal stale sessions ---
    # Re-clean merchant names and recalculate stats for sessions saved
    # before merchant_cleaner or total_investment were added.
    transactions = data.get("transactions", [])
    needs_update = False
    
    # Check if stats are stale (missing total_investment key)
    stats = data.get("stats", {})
    if "total_investment" not in stats:
        needs_update = True
    
    # Check if merchants need re-cleaning (look for raw UPI noise)
    for tx in transactions:
        merchant = tx.get("merchant", "")
        # If any merchant contains telltale raw UPI noise, re-clean all
        if any(noise in merchant.lower() for noise in ["hdfcomerupi", "oksbi", "yesb", "paid via", "elements"]):
            needs_update = True
            break
    
    if needs_update:
        # Re-clean all merchant names
        for tx in transactions:
            raw_desc = tx.get("description", "")
            if raw_desc:
                tx["merchant"] = clean_merchant_name(extract_merchant(raw_desc))
        
        # Re-categorize with cleaned merchants
        transactions = categorize_transactions(transactions)
        
        # Recalculate stats with current analyzer logic
        stats = analyze_transactions(transactions)
        data["stats"] = stats
        data["transactions"] = transactions
        
        # Persist the healed data so this only happens once
        update_session(session_id, {
            "transactions": transactions,
            "stats": stats
        })
    
    return {"data": data}

@app.post("/session/insights")
async def get_session_insights(req: InsightsRequest):
    try:
        data = get_session(req.session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
            
        insight_text = generate_insights(data.get("stats", {}))
        update_session(req.session_id, {"insights": insight_text})
        return {"insights": insight_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/update")
async def session_update(req: RecalculateRequest):
    try:
        for merchant, category in req.merchant_changes.items():
            update_learned_merchants(merchant, category)
            
        stats = analyze_transactions(req.transactions)
        
        update_session(req.session_id, {
            "transactions": req.transactions,
            "stats": stats
        })
        
        return {"status": "success", "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/rename")
async def process_rename_session(req: RenameRequest):
    try:
        rename_session(req.session_id, req.new_name)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
async def remove_session(session_id: str):
    if delete_session(session_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@app.post("/session/chat")
async def session_chat(req: ChatRequest):
    data = get_session(req.session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
        
    stats = data.get("stats", {})
    history = data.get("chat_history", [])
    
    try:
        reply = chat_with_context(req.message, stats, history)
        
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": reply})
        
        update_session(req.session_id, {"chat_history": history})
        
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
