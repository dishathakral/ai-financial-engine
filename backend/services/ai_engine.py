import json
import time
import requests
from ..config import OPENROUTER_API_KEY

def call_openrouter(messages: list[dict]) -> str:
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        return "⚠️ I am unable to provide AI insights right now because the OpenRouter API key is missing. Please configure it in the .env file."
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": messages
    }
    
    # Retry up to 3 times with exponential backoff for rate limits (429)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 429:
                wait_time = (attempt + 1) * 3  # 3s, 6s, 9s
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.HTTPError as e:
            if attempt < max_retries - 1 and response.status_code == 429:
                time.sleep((attempt + 1) * 3)
                continue
            return f"Error communicating with AI model: {e}"
        except Exception as e:
            return f"Error communicating with AI model: {e}"
    
    return "⚠️ The AI service is currently rate-limited. Please wait a moment and try again."

def generate_insights(stats: dict) -> str:
    system_prompt = "You are an expert AI financial decision engine. Use ONLY the provided merchants and numbers. Do not invent data, hallucinate merchants, or guess numbers not in the payload. Your decisions must be deterministic."
    
    top_dominance = stats.get('top_merchant_dominance', 0)
    top_merch_list = stats.get('top_merchants', [])
    top_name = top_merch_list[0]['merchant'] if top_merch_list else 'Unknown'
    
    user_prompt = f"""
    Context Data:
    Income: ₹ {stats.get('total_income', 0):,.2f}
    Expense: ₹ {stats.get('total_expense', 0):,.2f}
    Top merchants (Actionable Entities): {json.dumps(top_merch_list, indent=2)}
    Top merchant expense dominance: {top_dominance}%
    
    Format your response EXACTLY like this (using markdown):
    
    🔴 **Alert**: [State exactly what merchant is dominating their expenses cleanly separated by spaces. Example: "You are overspending heavily on {top_name}."]
    
    ⚠️ **Why this matters**: [State functionally why this destroys their wealth. Example: "This single merchant alone is driving your financial imbalance."]
    
    🟢 **Action**: [Provide a literal, confident physical action using exactly ₹ (Rupees), NEVER Dollars].
    
    🎯 **Goal**: [Calculate 50% of the top merchant's amount and tell them to reduce spending on {top_name} by that exact ₹ amount to reach stability]
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    return call_openrouter(messages)

def chat_with_context(user_message: str, stats: dict, chat_history: list = None) -> str:
    if chat_history is None:
        chat_history = []
        
    top_categories = list(stats.get('category_totals', {}).items())[:2]
    
    clean_stats = f"""
    Income: ₹ {stats.get('total_income', 0):,.2f}
    Expense: ₹ {stats.get('total_expense', 0):,.2f}
    Top Categories: {json.dumps(top_categories, indent=2)}
    Top Merchants (with frequency counts): {json.dumps(stats.get('top_merchants', []), indent=2)}
    Merchant Dominance: {stats.get('top_merchant_dominance', 0)}%
    Expense Ratio: {stats.get('expense_ratio', 0)}%
    """
        
    system_prompt = f"""You are an elite, razor-sharp AI Financial Analyst. You speak fluently and intelligently, not like a template robot.

[STRICT DATA PAYLOAD]
{clean_stats}

[CORE DIRECTIVES]
1. CONVERSATIONAL FLUIDITY: Speak naturally and dynamically. NEVER use rigid templates or robotic summaries.
2. BRUTALLY HONEST & DIRECT: Use strong, definitive verbs. Do not use weak words like "suggests", "indicates", or "consider". NEVER use the phrase "In short".
3. DATA-DRIVEN IMPACT: Ground your claims heavily in the detailed payload. Provide distinct math (e.g., cutting a specific merchant by X%) when asked about saving. Always use ₹. Avoid focusing on the 'Other' category unless specifically queried.
4. CONCISENESS: Keep answers to exactly 2-3 sentences max. Get straight to the intelligence without preamble.
5. RESPONSIVENESS: 
   - If they ask something generic like "give me questions to ask", provide 3 highly engaging, specific questions targeting their exact merchants.
   - If they ask about habits, explicitly cite their transaction frequency counts.
6. STRIKING CLOSING: Do NOT use summary formats. End simply with a punchy, confident assessment (e.g., "Chirpy iOS is single-handedly causing your deficit.") linked to the data.
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Append limited chat history
    for msg in chat_history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    # Append the new user message
    messages.append({"role": "user", "content": user_message})
    
    return call_openrouter(messages)
