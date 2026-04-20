def analyze_transactions(transactions: list[dict]) -> dict:
    total_income = 0.0
    total_expense = 0.0
    total_investment = 0.0
    category_totals = {}
    merchant_totals = {}
    merchant_counts = {}
    merchant_categories = {}  # Track category per merchant
    
    for tx in transactions:
        amount = tx.get("amount", 0.0)
        cat = tx.get("category", "") or ""
        cat = cat.strip().title() if cat and cat.lower() not in ("null", "none", "nan", "") else "Other"
        tx["category"] = cat  # Write normalized category back to transaction
        
        # Credits are ALWAYS income — no exceptions, ignore any manual category override
        if tx.get("type") == "credit" or cat == "Income":
            total_income += amount
            continue
        
        total_expense += amount
        category_totals[cat] = category_totals.get(cat, 0.0) + amount
        
        # Track investment total
        if cat == "Investments":
            total_investment += amount
        
        merchant = tx.get("merchant", "unknown")
        if merchant != "unknown":
            merchant_totals[merchant] = merchant_totals.get(merchant, 0.0) + amount
            merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1
            merchant_categories[merchant] = cat
            
    savings = total_income - total_expense
    lifestyle_expense = total_expense - total_investment
    
    # Sort categories by spending descending
    category_totals = dict(sorted(category_totals.items(), key=lambda item: item[1], reverse=True))
    merchant_totals = dict(sorted(merchant_totals.items(), key=lambda item: item[1], reverse=True))
    
    category_percentages = {}
    top_merchants = []
    top_lifestyle_merchants = []
    top_merchant_dominance = 0.0
    
    if total_expense > 0:
        for cat, val in category_totals.items():
            category_percentages[cat] = round((val / total_expense) * 100, 2)
            
        # Top 3 overall merchants
        top_merchants_list = list(merchant_totals.items())[:3]
        for m, val in top_merchants_list:
            top_merchants.append({
                "merchant": m.title(), 
                "amount": round(val, 2), 
                "count": merchant_counts.get(m, 0),
                "category": merchant_categories.get(m, "Other")
            })
        
        # Top 3 lifestyle merchants (excluding Investments)
        lifestyle_merchants = [(m, v) for m, v in merchant_totals.items() 
                               if merchant_categories.get(m) != "Investments"]
        for m, val in lifestyle_merchants[:3]:
            top_lifestyle_merchants.append({
                "merchant": m.title(),
                "amount": round(val, 2),
                "count": merchant_counts.get(m, 0),
                "category": merchant_categories.get(m, "Other")
            })
            
        if top_merchants:
            top_merchant_dominance = round((top_merchants[0]["amount"] / total_expense) * 100, 2)
            
    expense_ratio = 0.0
    investment_ratio = 0.0
    if total_income > 0:
        expense_ratio = round((total_expense / total_income) * 100, 2)
    elif total_expense > 0:
        expense_ratio = 100.0
    
    if total_expense > 0:
        investment_ratio = round((total_investment / total_expense) * 100, 2)
            
    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "savings": round(savings, 2),
        "total_investment": round(total_investment, 2),
        "lifestyle_expense": round(lifestyle_expense, 2),
        "investment_ratio": investment_ratio,
        "category_totals": category_totals,
        "category_percentages": category_percentages,
        "top_merchants": top_merchants,
        "top_lifestyle_merchants": top_lifestyle_merchants,
        "top_merchant_dominance": top_merchant_dominance,
        "expense_ratio": expense_ratio
    }
