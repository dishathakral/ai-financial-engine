import re

# Bank codes to strip (but preserve as brand when they ARE the brand, e.g. "SBI Card")
BANK_CODES = {
    "hdfc", "sbin", "utib", "yesb", "icic", "kkbk", "punb", "barb",
    "cnrb", "idfb", "ratn", "mahb", "ubin", "bkid", "cbin", "corp",
    "alla", "andb", "srcb", "fdrl", "indb", "oksbi"
}

# Noise tokens to always remove
NOISE_TOKENS = {
    "upi", "neft", "imps", "rtgs", "ach", "nach", "ecs",
    "paytmqr", "paytm", "ptys", "pty", "pvt", "ltd", "limited", "private",
    "dr", "cr", "paid", "via", "elements", "valid", "brk",
    "yesb0ptmupi", "yesb0mchupi", "hdfcomerupi", "hdfcmerupi",
    "phonepe", "gpay",  # payment processor noise (keep if it's the actual merchant)
    "ppi", "mer", "collect", "req", "trf", "tfr",
    "ent", "sent", "s ent", "bse", "nse"
}

# Pattern: investment keywords (2-layer detection)
INVESTMENT_PATTERNS = re.compile(
    r'\b(sip|mutual\s*fund|mf\s+purchase|mf\s+sip|nse\s+purchase|'
    r'amc\s+debit|nfo|elss|ppf|nps|systematic\s+investment)\b',
    re.IGNORECASE
)

# Known brand names to preserve intact
BRAND_PRESERVATIONS = {
    "icici prudential": "ICICI Prudential",
    "sbi card": "SBI Card",
    "sbi life": "SBI Life",
    "hdfc life": "HDFC Life",
    "hdfc ergo": "HDFC Ergo",
    "axis bank": "Axis Bank",
}


def clean_merchant_name(raw: str) -> str:
    """
    Cleans a raw merchant string from bank statement into a human-readable 
    brand-preserving name (max 3 words).
    
    Design principle: Keep 1 recognizable brand word + optional descriptor.
    Never over-clean to the point of losing identity.
    """
    if not raw or raw.strip() == "" or raw.strip().lower() == "unknown":
        return "Unknown"
    
    original = raw.strip().lower()
    
    # Check brand preservation first (exact substring matches)
    for pattern, brand in BRAND_PRESERVATIONS.items():
        if pattern in original:
            return brand
    
    # Step 1: Remove all purely numeric tokens and long digit sequences
    tokens = original.split()
    tokens = [t for t in tokens if not re.match(r'^\d+$', t)]
    
    # Step 2: Remove tokens that are bank codes
    tokens = [t for t in tokens if t not in BANK_CODES]
    
    # Step 3: Remove noise tokens
    tokens = [t for t in tokens if t not in NOISE_TOKENS]
    
    # Step 4: Remove tokens that look like UPI IDs (long alphanumeric with digits)
    tokens = [t for t in tokens if not re.match(r'^[a-z]*\d{4,}', t)]  # e.g. "d18886262998"
    tokens = [t for t in tokens if not re.match(r'^\d+[a-z]+\d*$', t)]  # e.g. "3oksbi"
    
    # Step 5: Remove very short meaningless tokens (1 char)
    tokens = [t for t in tokens if len(t) > 1]
    
    # Step 6: Remove trailing "upi" if it survived
    while tokens and tokens[-1] in ("upi", "pi", "up"):
        tokens.pop()
    
    # Step 7: Limit to first 3 meaningful words
    tokens = tokens[:3]
    
    # Step 8: Title case
    result = " ".join(tokens).title()
    
    # Fallback: if everything got stripped, extract first 2 alpha tokens from original
    if not result.strip():
        fallback_tokens = [t for t in original.split() if re.match(r'^[a-z]{2,}$', t)]
        fallback_tokens = [t for t in fallback_tokens if t not in NOISE_TOKENS and t not in BANK_CODES]
        result = " ".join(fallback_tokens[:2]).title()
    
    # Final fallback
    if not result.strip():
        return "Unknown"
    
    return result
