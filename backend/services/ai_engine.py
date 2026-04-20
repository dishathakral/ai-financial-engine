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
                wait_time = (attempt + 1) * 3
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


def _short_merchant(name: str) -> str:
    """Shorten a merchant name to max 3 words for clean LLM context."""
    noise = {"upi", "neft", "imps", "pvt", "ltd", "pv", "brk", "valid", "paid", "via", "elements", "dr", "cr"}
    words = name.strip().split()
    # Drop words that are purely noise (digits, bank codes, UPI ids, short tokens)
    clean = [w for w in words if not w.replace(",", "").isdigit() and len(w) > 1 and w.lower() not in noise]
    return " ".join(clean[:2]).title() if clean else name.title()


def _build_financial_context(stats: dict) -> str:
    """Build a rich financial context string from stats for AI consumption."""
    cat_totals = stats.get('category_totals', {})
    cat_pcts = stats.get('category_percentages', {})
    
    category_breakdown = "\n".join([
        f"  - {cat}: ₹{amt:,.0f} ({cat_pcts.get(cat, 0)}%)" 
        for cat, amt in cat_totals.items()
    ])
    
    top_lifestyle = stats.get('top_lifestyle_merchants', [])
    lifestyle_lines = "\n".join([
        f"  - {_short_merchant(m['merchant'])}: ₹{m['amount']:,.0f} ({m['count']} txns, category: {m.get('category', 'Other')})"
        for m in top_lifestyle
    ]) or "  None detected"
    
    top_overall = stats.get('top_merchants', [])
    overall_lines = "\n".join([
        f"  - {_short_merchant(m['merchant'])}: ₹{m['amount']:,.0f} ({m['count']} txns, category: {m.get('category', 'Other')})"
        for m in top_overall
    ]) or "  None detected"
    
    return f"""
Income: ₹{stats.get('total_income', 0):,.2f}
Total Expense: ₹{stats.get('total_expense', 0):,.2f}
Savings: ₹{stats.get('savings', 0):,.2f}
Expense Ratio: {stats.get('expense_ratio', 0)}% (< 100% = healthy, > 100% = danger)

Investments: ₹{stats.get('total_investment', 0):,.2f} ({stats.get('investment_ratio', 0)}% of expenses)
Lifestyle Expense (non-investment): ₹{stats.get('lifestyle_expense', 0):,.2f}

Category Breakdown:
{category_breakdown}

Top Lifestyle Spenders (non-investment):
{lifestyle_lines}

Top Overall Spenders:
{overall_lines}
"""


def generate_top_banner(stats: dict) -> str:
    """Generate a single-line top insight banner for the UI."""
    expense_ratio = stats.get('expense_ratio', 0)
    savings = stats.get('savings', 0)
    investment_ratio = stats.get('investment_ratio', 0)
    total_investment = stats.get('total_investment', 0)
    
    if expense_ratio > 100:
        if investment_ratio > 30:
            return f"⚠️ You're spending {expense_ratio - 100:.0f}% more than you earn, despite strong investment habits (₹{total_investment:,.0f}). Rebalancing is critical."
        else:
            return f"🔴 Your expenses exceed income by ₹{abs(savings):,.0f}. Expense ratio is {expense_ratio:.0f}% — immediate action needed."
    elif expense_ratio > 90:
        return f"⚠️ You're saving only {100 - expense_ratio:.0f}% of your income. One unexpected expense could tip you into deficit."
    elif investment_ratio > 40:
        return f"🟢 Strong financial discipline — ₹{total_investment:,.0f} allocated to investments ({investment_ratio:.0f}% of spending). Savings: ₹{savings:,.0f}."
    else:
        return f"🟢 Healthy finances — saving ₹{savings:,.0f} ({100 - expense_ratio:.0f}% of income). Keep it up."


def generate_insights(stats: dict) -> str:
    context = _build_financial_context(stats)
    
    system_prompt = """You are an elite AI Financial Advisor — not a template robot. You speak with confidence, warmth, and brutal honesty like a trusted friend who happens to be a finance expert.

CRITICAL RULES:
1. Investments (Groww, Zerodha, SIPs, Mutual Funds) are NOT wasteful spending. NEVER say "reduce spending on investments."
2. Only warn about LIFESTYLE overspending (Food, Shopping, Entertainment, Travel).
3. Always use ₹ (Rupees), NEVER dollars.
4. Use the exact numbers from the data. Never invent merchants or amounts.
5. Sound like a human advisor, not a corporate report.
6. MERCHANT NAMES: Use SHORT, clean brand names only (e.g. "Groww", "Zomato", "Amazon"). NEVER paste raw UPI transaction strings, bank codes, or reference numbers. If a merchant name looks like "Groww Invest Tech Pv", just say "Groww"."""

    user_prompt = f"""
{context}

Based on this financial data, provide a sharp analysis in EXACTLY this format:

🔴 **Alert**: [1 sentence — the single most CRITICAL financial concern. Use CATEGORY names (Food, Shopping) not raw merchant strings. Include the ₹ amount.]

⚠️ **Why this matters**: [1 sentence — explain the real-world impact of this concern on their financial health.]

🟢 **Action**: [1 specific, actionable step with an exact ₹ amount to cut from a specific CATEGORY to fix the problem.]

🎯 **Goal**: [1 sentence — what achieving this action would result in. E.g. "This would bring your expense ratio from 106% to 92%, putting you back in the green."]
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    return call_openrouter(messages)


def chat_with_context(user_message: str, stats: dict, chat_history: list = None) -> str:
    if chat_history is None:
        chat_history = []
    
    context = _build_financial_context(stats)
        
    system_prompt = f"""You are an elite, razor-sharp AI Financial Advisor. You speak fluently and intelligently — like a trusted friend who's brilliant with money.

[FINANCIAL DATA]
{context}

[CORE DIRECTIVES]
1. CATEGORY INTELLIGENCE: When asked about spending, ALWAYS break down by category with percentages. Never just list merchants.
2. INVESTMENT AWARENESS: Investments (Groww, Zerodha, SIPs, Mutual Funds) are wealth-building, NOT wasteful spending. Praise this discipline when relevant. Only warn about lifestyle categories.
3. EXPENSE RATIO MASTERY: The expense ratio ({stats.get('expense_ratio', 0)}%) is the single most important metric. < 100% = healthy. > 100% = danger. Reference it when discussing financial health.
4. BRUTALLY HONEST & DIRECT: Use strong, definitive language. Not "consider reducing" but "cut ₹X from Shopping immediately."
5. CONCISENESS: Keep answers to 2-4 sentences max. No preamble, no summaries.
6. DATA-GROUNDED: Every claim must cite a specific ₹ amount or percentage from the data. Never generalize.
7. ACTIONABLE: When asked "how to save", give specific ₹ amounts to cut from specific categories.
8. Always use ₹ (Rupees). Never dollars.

EXAMPLE RESPONSES:
- "Where am I spending most?" → "Your biggest expense category is Investments at ₹57,000 (50% of spending), which is wealth-building. Your largest lifestyle drain is Shopping at ₹12,000 (11%). Food follows at ₹8,500 (7.5%)."
- "How can I save?" → "Cut Shopping by ₹5,000/month (40% reduction) and you'll flip from -₹6,499 to +₹3,500 in savings. Your Food at ₹8,500 has room for a ₹2,000 trim too."
- "Am I doing good?" → "Your expense ratio is 106% — you're spending more than you earn. However, ₹57,000 in investments shows strong discipline. The issue is lifestyle spending at ₹55,000."
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Append limited chat history
    for msg in chat_history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    # Append the new user message
    messages.append({"role": "user", "content": user_message})
    
    return call_openrouter(messages)
