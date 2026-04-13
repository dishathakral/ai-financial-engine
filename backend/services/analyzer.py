def analyze_transactions(transactions: list[dict]) -> dict:
    total_income = 0.0
    total_expense = 0.0
    category_totals = {}
    merchant_totals = {}
    merchant_counts = {}
    
    for tx in transactions:
        amount = tx.get("amount", 0.0)
        if tx.get("type") == "credit":
            total_income += amount
        else:
            total_expense += amount
            cat = tx.get("category", "Other")
            category_totals[cat] = category_totals.get(cat, 0.0) + amount
            merchant = tx.get("merchant", "unknown")
            if merchant != "unknown":
                merchant_totals[merchant] = merchant_totals.get(merchant, 0.0) + amount
                merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1
            
    savings = total_income - total_expense
    
    # Sort categories by spending descending
    category_totals = dict(sorted(category_totals.items(), key=lambda item: item[1], reverse=True))
    merchant_totals = dict(sorted(merchant_totals.items(), key=lambda item: item[1], reverse=True))
    
    category_percentages = {}
    top_merchants = []
    top_merchant_dominance = 0.0
    
    if total_expense > 0:
        for cat, val in category_totals.items():
            category_percentages[cat] = round((val / total_expense) * 100, 2)
            
        top_merchants_list = list(merchant_totals.items())[:3]
        for m, val in top_merchants_list:
            top_merchants.append({
                "merchant": m.upper(), 
                "amount": round(val, 2), 
                "count": merchant_counts.get(m, 0)
            })
            
        if top_merchants:
            top_merchant_dominance = round((top_merchants[0]["amount"] / total_expense) * 100, 2)
            
    expense_ratio = 0.0
    if total_income > 0:
        expense_ratio = round((total_expense / total_income) * 100, 2)
    elif total_expense > 0:
        expense_ratio = 100.0
            
    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "savings": round(savings, 2),
        "category_totals": category_totals,
        "category_percentages": category_percentages,
        "top_merchants": top_merchants,
        "top_merchant_dominance": top_merchant_dominance,
        "expense_ratio": expense_ratio
    }
