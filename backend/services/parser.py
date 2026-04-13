import pandas as pd
import io
import re

COLUMN_MAP = {
    "date": ["date", "txn date", "value date", "transaction date"],
    "description": ["details", "narration", "description", "particulars"],
    "debit": ["debit", "withdrawal"],
    "credit": ["credit", "deposit"]
}

def clean_description(desc: str) -> str:
    desc = str(desc).strip()
    # We will ONLY remove the trailing branch suffix that confuses the LLM
    desc = re.sub(r'\s+AT\s+\d+.*$', '', desc, flags=re.IGNORECASE)
    return desc.strip()

def extract_merchant(desc: str) -> str:
    """Extracts a clean merchant string from a raw bank description."""
    merchant = desc
    
    # Check for UPI format: UPI/DR/123456/MERCHANT NAME/BANK
    upi_match = re.search(r'UPI/(?:DR|CR|dr|cr)/\d+/(.*?)(?:\s+AT\s+\d+.*)?$', desc, re.IGNORECASE)
    if upi_match:
        parts = upi_match.group(1).split('/')
        if len(parts) > 0:
            merchant = parts[0]
            
    # Check for NEFT/IMPS
    elif re.search(r'(?:NEFT|IMPS)[/\-A-Z0-9]+[/\-](.*?)(?:\s+AT\s+\d+.*)?$', desc, re.IGNORECASE):
        match = re.search(r'(?:NEFT|IMPS)[/\-A-Z0-9]+[/\-](.*?)(?:\s+AT\s+\d+.*)?$', desc, re.IGNORECASE)
        parts = match.group(1).split('/')
        if len(parts) > 0:
            merchant = parts[0]
            
    # Aggressively normalize the merchant name
    merchant = re.sub(r'[^a-zA-Z0-9\s]', ' ', merchant) # replace non-alphanumerics with space
    merchant = ' '.join(merchant.split()).lower() # compress spaces and lowercase
    
    # Fallback to 'unknown' if it evaporated
    if not merchant or merchant.strip() == "":
        merchant = "unknown"
        
    return merchant

def parse_excel(file_bytes: bytes, password: str = None) -> list[dict]:
    """
    Parses an Excel file containing bank transactions (SBI, HDFC).
    Detects the header row dynamically.
    """
    file_obj = io.BytesIO(file_bytes)
    
    if password:
        try:
            import msoffcrypto
            office_file = msoffcrypto.OfficeFile(file_obj)
            office_file.load_key(password=password)
            decrypted = io.BytesIO()
            office_file.decrypt(decrypted)
            file_obj = decrypted
        except Exception as e:
            raise ValueError(f"Failed to decrypt file. Invalid password: {e}")
            
    # read without headers to find the table start
    df_raw = pd.read_excel(file_obj, header=None)
    
    header_row_index = -1
    
    for i, row in df_raw.iterrows():
        row_str = ' '.join([str(x).lower() for x in row if pd.notna(x)])
        
        has_date = any(kw in row_str for kw in COLUMN_MAP["date"])
        has_money = any(kw in row_str for kw in (COLUMN_MAP["debit"] + COLUMN_MAP["credit"] + ["amount", "balance"]))
        
        if has_date and has_money:
            header_row_index = i
            break
            
    if header_row_index == -1:
        # fallback if not detected
        header_row_index = 0
        
    df = pd.read_excel(file_obj, header=header_row_index)
    df.columns = df.columns.str.lower().str.strip()
    
    transactions = []
    
    # Map columns to standard names based on COLUMN_MAP
    date_col = next((col for col in df.columns if pd.notna(col) and any(kw in str(col).lower() for kw in COLUMN_MAP["date"])), None)
    desc_col = next((col for col in df.columns if pd.notna(col) and any(kw in str(col).lower() for kw in COLUMN_MAP["description"])), None)
    debit_col = next((col for col in df.columns if pd.notna(col) and any(kw in str(col).lower() for kw in COLUMN_MAP["debit"])), None)
    credit_col = next((col for col in df.columns if pd.notna(col) and any(kw in str(col).lower() for kw in COLUMN_MAP["credit"])), None)
    amount_col = next((col for col in df.columns if col == 'amount'), None)
    
    for _, row in df.iterrows():
        try:
            date = str(row[date_col]) if date_col and pd.notna(row[date_col]) else ""
            desc = str(row[desc_col]) if desc_col and pd.notna(row[desc_col]) else ""
            
            amount = 0.0
            type_ = "debit"
            
            if credit_col and debit_col:
                c_val = pd.to_numeric(str(row[credit_col]).replace(',', ''), errors='coerce')
                d_val = pd.to_numeric(str(row[debit_col]).replace(',', ''), errors='coerce')
                
                if pd.notna(c_val) and c_val > 0:
                    amount = float(c_val)
                    type_ = "credit"
                elif pd.notna(d_val) and d_val > 0:
                    amount = float(d_val)
                    type_ = "debit"
            elif amount_col:
                val = pd.to_numeric(str(row[amount_col]).replace(',', ''), errors='coerce')
                if pd.notna(val):
                    amount = abs(float(val))
                    type_ = "credit" if val > 0 else "debit"
            
            desc = str(desc).strip()
            desc = ' '.join(desc.split())
            desc = clean_description(desc)
            
            # --- Protections against Statement Summary rows ---
            if not desc or desc.lower() == 'nan' or desc.isdigit():
                continue
            
            date_str = str(date).lower()
            if 'cr' in date_str or 'dr' in date_str or 'balance' in date_str or 'summary' in date_str:
                continue
            # --------------------------------------------------
            
            if amount > 0:
                transactions.append({
                    "date": date,
                    "description": desc,
                    "merchant": extract_merchant(desc),
                    "amount": round(amount, 2),
                    "type": type_
                })
        except Exception:
            continue
            
    return transactions
