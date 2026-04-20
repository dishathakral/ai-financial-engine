import requests
from ..config import OPENROUTER_API_KEY
from .storage import get_learned_merchants

KNOWN_MERCHANTS = {
    "zomato": "Food",
    "blinkit": "Grocery",
    "amazon": "Shopping",
    "swiggy": "Food",
    "uber": "Travel",
    "ola": "Travel",
    "reliance": "Bills",
    "netflix": "Entertainment",
    "spotify": "Entertainment",
    "jio": "Bills",
    "airtel": "Bills",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "bigbasket": "Grocery",
    "dunzo": "Grocery",
    "rapido": "Travel",
    "hotstar": "Entertainment",
    "youtube": "Entertainment",
    "phonepe": "Bills",
    "cred": "Bills"
}

# 2-layer investment detection: brand keywords + financial patterns
INVESTMENT_KEYWORDS = [
    "groww", "zerodha", "kuvera", "coin", "upstox", "angelone",
    "angel broking", "motilal", "icicidirect", "smallcase",
    "et money", "paytm money", "5paisa", "dhan", "fi money",
    "icici prudential", "sbi life", "hdfc life", "lic", "bajaj finserv",
    "axis mutual", "hdfc mutual", "sbi mutual", "kotak mutual",
    "nippon", "tata mutual", "mirae", "dsp mutual", "franklin templeton"
]

INVESTMENT_PATTERNS = [
    "sip", "mutual fund", "mf purchase", "mf sip", "nse purchase",
    "amc debit", "nfo", "elss", "ppf", "nps", "systematic investment",
    "mf auto", "auto sip"
]


def is_investment(merchant: str) -> bool:
    """2-layer investment detection: keyword match + pattern match."""
    m_lower = merchant.lower()
    
    # Layer 1: Brand keyword match
    for keyword in INVESTMENT_KEYWORDS:
        if keyword in m_lower:
            return True
    
    # Layer 2: Financial pattern match
    for pattern in INVESTMENT_PATTERNS:
        if pattern in m_lower:
            return True
    
    return False


def categorize_transaction(merchant: str) -> dict:
    merchant_lower = merchant.lower()
    
    # Priority 1: Learned from User Customizations
    learned = get_learned_merchants()
    if merchant_lower in learned:
        return {"category": learned[merchant_lower], "confidence": "100% (Learned Mapping)"}
    
    # Priority 1.5: Investment Detection (2-layer)
    if is_investment(merchant_lower):
        return {"category": "Investments", "confidence": "95% (Investment Match)"}
    
    # Priority 2: Rule-based
    for known_merchant, category in KNOWN_MERCHANTS.items():
        if known_merchant in merchant_lower:
            return {"category": category, "confidence": "95% (Rule Match)"}
            
    # Priority 3: LLM fallback
    if OPENROUTER_API_KEY and OPENROUTER_API_KEY != "your_openrouter_api_key_here":
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a financial categorizer. Given a merchant name from a bank statement, reply with ONLY ONE WORD: Food, Travel, Shopping, Bills, Health, Education, Entertainment, Grocery, Investments, or Other. Do not add any extra text."},
                    {"role": "user", "content": f"Categorize this merchant: '{merchant}'"}
                ]
            }
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
                cat = response.json()["choices"][0]["message"]["content"].strip()
                cat = ''.join(e for e in cat if e.isalnum())
                return {"category": cat, "confidence": "70% (AI Inference)"}
        except Exception:
            pass
            
    return {"category": "Other", "confidence": "70% (Fallback)"}

def categorize_transactions(transactions: list[dict]) -> list[dict]:
    for tx in transactions:
        if tx.get("type", "debit") == "credit":
            tx["category"] = "Income"
            tx["confidence"] = "100% (Deterministic)"
        else:
            cat_result = categorize_transaction(tx.get("merchant", tx.get("description", "")))
            tx["category"] = cat_result["category"]
            tx["confidence"] = cat_result["confidence"]
    return transactions
