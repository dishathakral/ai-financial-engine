import json
import os
import hashlib
from datetime import datetime
import uuid

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')
LEARNED_MERCHANTS_FILE = os.path.join(DATA_DIR, 'learned_merchants.json')

os.makedirs(SESSIONS_DIR, exist_ok=True)

def generate_file_hash(filename: str, content: bytes) -> str:
    hash_md5 = hashlib.md5()
    hash_md5.update(filename.encode('utf-8'))
    hash_md5.update(content)
    return hash_md5.hexdigest()

def check_duplicate_session(file_hash: str) -> str:
    """Returns session_id if a session with this file_hash already exists, else None."""
    for f in os.listdir(SESSIONS_DIR):
        if f.endswith('.json'):
            try:
                with open(os.path.join(SESSIONS_DIR, f), 'r') as file:
                    data = json.load(file)
                    if data.get('file_hash') == file_hash:
                        return data.get('session_id')
            except: pass
    return None

def create_session(filename: str, content: bytes, transactions: list, stats: dict) -> str:
    session_id = str(uuid.uuid4())
    file_hash = generate_file_hash(filename, content)
    
    top_merchants = stats.get('top_merchants', [])
    top_merchant = top_merchants[0]['merchant'] if top_merchants else "None"
    
    data = {
        "session_id": session_id,
        "file_name": filename,
        "file_hash": file_hash,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "version": 1,
        "summary": {
            "income": stats.get("total_income", 0),
            "expense": stats.get("total_expense", 0),
            "top_merchant": top_merchant
        },
        "transactions": transactions,
        "stats": stats,
        "chat_history": []
    }
    
    with open(os.path.join(SESSIONS_DIR, f"session_{session_id}.json"), 'w') as f:
        json.dump(data, f, indent=2)
        
    return session_id

def get_session(session_id: str) -> dict:
    filepath = os.path.join(SESSIONS_DIR, f"session_{session_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return None

def get_all_sessions() -> list:
    sessions = []
    for f in os.listdir(SESSIONS_DIR):
        if f.endswith('.json'):
            try:
                with open(os.path.join(SESSIONS_DIR, f), 'r') as file:
                    data = json.load(file)
                    sessions.append({
                        "session_id": data.get("session_id"),
                        "file_name": data.get("file_name"),
                        "created_at": data.get("created_at"),
                        "version": data.get("version", 1),
                        "summary": data.get("summary", {})
                    })
            except: pass
            
    # Sort by created_at descending
    sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return sessions

def update_session(session_id: str, updates: dict):
    data = get_session(session_id)
    if data:
        for k, v in updates.items():
            if k == 'chat_history':
                data[k] = v[-20:] # Truncate chat to last 20 messages
            else:
                data[k] = v
                
        # If updating transactions/stats, increment version
        if 'transactions' in updates:
            data['version'] = data.get('version', 1) + 1
            
            # Extract summary updates from stats if passed
            stats = updates.get("stats")
            if stats:
                top_merchants = stats.get('top_merchants', [])
                top_merchant = top_merchants[0]['merchant'] if top_merchants else "None"
                data['summary'] = {
                    "income": stats.get("total_income", 0),
                    "expense": stats.get("total_expense", 0),
                    "top_merchant": top_merchant
                }

        data['last_updated'] = datetime.now().isoformat()
        
        with open(os.path.join(SESSIONS_DIR, f"session_{session_id}.json"), 'w') as f:
            json.dump(data, f, indent=2)

def rename_session(session_id: str, new_name: str):
    data = get_session(session_id)
    if data:
        data['file_name'] = new_name
        data['last_updated'] = datetime.now().isoformat()
        with open(os.path.join(SESSIONS_DIR, f"session_{session_id}.json"), 'w') as f:
            json.dump(data, f, indent=2)
            
def get_learned_merchants() -> dict:
    if os.path.exists(LEARNED_MERCHANTS_FILE):
        with open(LEARNED_MERCHANTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def update_learned_merchants(merchant: str, category: str):
    merchants = get_learned_merchants()
    merchants[merchant.lower()] = category
    with open(LEARNED_MERCHANTS_FILE, 'w') as f:
        json.dump(merchants, f, indent=2)
