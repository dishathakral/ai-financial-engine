import streamlit as st
import requests
import pandas as pd
import os
st.set_page_config(page_title="AI Financial Intelligence", layout="wide", page_icon="💸")

# API_URL = "http://localhost:8000"


API_URL = os.getenv(
    "API_URL",
    "http://localhost:8000"   # fallback for local
)

# st.write("API URL:", API_URL)
# Modern styling override (for hackathon wow-factor)
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #4CAF50;
    }
    .metric-label {
        font-size: 1rem;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "file_name" not in st.session_state:
    st.session_state.file_name = "Unknown"
if "transactions" not in st.session_state:
    st.session_state.transactions = []
if "stats" not in st.session_state:
    st.session_state.stats = {}
if "insights" not in st.session_state:
    st.session_state.insights = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "duplicate_detected" not in st.session_state:
    st.session_state.duplicate_detected = False
if "duplicate_session_id" not in st.session_state:
    st.session_state.duplicate_session_id = None

def load_session(session_id):
    try:
        res = requests.get(f"{API_URL}/sessions/{session_id}")
        if res.status_code == 200:
            data = res.json()["data"]
            st.session_state.session_id = data.get("session_id")
            st.session_state.file_name = data.get("file_name", "Unknown")
            st.session_state.transactions = data.get("transactions", [])
            st.session_state.stats = data.get("stats", {})
            st.session_state.chat_history = data.get("chat_history", [])
            st.session_state.insights = data.get("insights", "")
            st.session_state.duplicate_detected = False
            st.session_state.duplicate_session_id = None
            st.success("Session loaded seamlessly!")
            return True
    except Exception as e:
        st.error(f"Failed to load session: {e}")
    return False

with st.sidebar:
    st.header("📂 Saved Sessions")
    try:
        resp = requests.get(f"{API_URL}/sessions")
        if resp.status_code == 200:
            sessions = resp.json().get("sessions", [])
            if sessions:
                options = { s["session_id"]: f"v{s['version']} - {s['file_name']} (Spent ₹{s.get('summary', {}).get('expense', 0):,.0f})" for s in sessions }
                selected = st.selectbox("Load Previous Session", options=list(options.keys()), format_func=lambda x: options[x])
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("Load Session", use_container_width=True):
                        if load_session(selected):
                            st.rerun()
                with btn_col2:
                    if st.button("🗑️ Delete", use_container_width=True, type="primary"):
                        st.session_state.confirm_delete = selected
                
                if st.session_state.get("confirm_delete") == selected:
                    st.warning(f"Delete **{options[selected]}**?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Yes, Delete", use_container_width=True):
                            resp_del = requests.delete(f"{API_URL}/sessions/{selected}")
                            if resp_del.status_code == 200:
                                st.session_state.confirm_delete = None
                                if st.session_state.session_id == selected:
                                    st.session_state.session_id = None
                                    st.session_state.transactions = []
                                    st.session_state.stats = {}
                                    st.session_state.insights = ""
                                    st.session_state.chat_history = []
                                st.success("Session deleted!")
                                st.rerun()
                    with c2:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.session_state.confirm_delete = None
                            st.rerun()
            else:
                st.info("No saved sessions yet.")
    except requests.exceptions.RequestException:
        st.warning("Could not connect to database.")
    except Exception as e:
        import streamlit as st
        # Prevent catching RerunException if it inherits from Exception in this version
        if type(e).__name__ == "RerunException":
            raise
        st.warning(f"Error loading sessions: {e}")

st.title("💸 AI Financial Intelligence System")
st.markdown("Upload your bank statement to get instant categorization and AI insights.")

if os.path.exists("frontend/demo_statement.xlsx"):
    with open("frontend/demo_statement.xlsx", "rb") as demo_f:
        st.download_button(
            label="📥 Download Demo Bank Statement",
            data=demo_f.read(),
            file_name="demo_bank_statement.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Download a sample SBI-format bank statement to test the system instantly.",
            use_container_width=True
        )
    st.caption("*No bank statement handy? Download our demo file above to try the system instantly.*")

uploaded_file = st.file_uploader("Upload your Bank Statement (Excel)", type=["xlsx", "xls"])
document_password = st.text_input("Document Password (if any)", type="password")

if uploaded_file is not None and not st.session_state.session_id:
    # Need to check duplicate or upload
    if st.session_state.duplicate_detected:
        st.warning("⚠️ Duplicate Session Detected! This exact file is already in your database.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Load Existing Session", use_container_width=True):
                if load_session(st.session_state.duplicate_session_id):
                    st.rerun()
        with col2:
            if st.button("Force Create New Copy", type="primary", use_container_width=True):
                st.session_state.duplicate_detected = False # Bypass next check
                # Force process
                with st.spinner("Processing New Copy..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/octet-stream")}
                    data_payload = {"password": document_password, "force_duplicate": "true"} if document_password else {"force_duplicate": "true"}
                    try:
                        response = requests.post(f"{API_URL}/analyze", files=files, data=data_payload)
                        response.raise_for_status()
                        data = response.json()
                        st.session_state.session_id = data.get("session_id")
                        st.session_state.file_name = uploaded_file.name
                        st.session_state.transactions = data.get("transactions", [])
                        st.session_state.stats = data.get("stats", {})
                        st.rerun()
                    except requests.exceptions.HTTPError as e:
                        error_detail = e.response.json().get("detail", str(e)) if "application/json" in e.response.headers.get("content-type", "") else str(e)
                        st.error(f"Engine Error: {error_detail}")
                    except Exception as e:
                        st.error(f"System Error: {e}")
    else:
        if st.button("Process Statement", use_container_width=True):
            with st.spinner("Scanning Document..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/octet-stream")}
                dup_resp = requests.post(f"{API_URL}/check_duplicate", files=files)
                
                if dup_resp.status_code == 200 and dup_resp.json().get("exists"):
                    st.session_state.duplicate_detected = True
                    st.session_state.duplicate_session_id = dup_resp.json().get("session_id")
                    st.rerun()
                else:
                    # Proceed with analyze
                    data_payload = {"password": document_password} if document_password else {}
                    try:
                        response = requests.post(f"{API_URL}/analyze", files=files, data=data_payload)
                        response.raise_for_status()
                        data = response.json()
                        st.session_state.session_id = data.get("session_id")
                        st.session_state.file_name = uploaded_file.name
                        st.session_state.transactions = data.get("transactions", [])
                        st.session_state.stats = data.get("stats", {})
                        st.rerun()
                    except requests.exceptions.HTTPError as e:
                        error_detail = e.response.json().get("detail", str(e)) if "application/json" in e.response.headers.get("content-type", "") else str(e)
                        st.error(f"Engine Error: {error_detail}")
                    except Exception as e:
                        st.error(f"System Error: {e}")

# If we have data, display it
if st.session_state.session_id and st.session_state.transactions:
    
    # Simple rename bar
    st.markdown("---")
    r_col1, r_col2 = st.columns([4, 1])
    with r_col1:
        new_name = st.text_input("Session Name", value=st.session_state.file_name, label_visibility="collapsed")
    with r_col2:
        if st.button("Rename Session", use_container_width=True):
            if new_name != st.session_state.file_name:
                try:
                    requests.post(f"{API_URL}/session/rename", json={"session_id": st.session_state.session_id, "new_name": new_name})
                    st.session_state.file_name = new_name
                    st.success("Renamed!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error renaming: {e}")
                    
    st.divider()
    
    stats = st.session_state.stats
    income = stats.get("total_income", 0)
    expense = stats.get("total_expense", 0)
    savings = stats.get("savings", 0)
    total_investment = stats.get("total_investment", 0)
    expense_ratio = stats.get("expense_ratio", 0)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Income</div><div class="metric-value">₹{income:,.2f}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card" style="border-bottom: 3px solid #ff4b4b"><div class="metric-label">Total Expense</div><div class="metric-value" style="color: #ff4b4b">₹{expense:,.2f}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card" style="border-bottom: 3px solid #00c0f2"><div class="metric-label">Net Savings</div><div class="metric-value" style="color: #00c0f2">₹{savings:,.2f}</div></div>', unsafe_allow_html=True)
    
    # Row 2: Investment + Expense Ratio
    col4, col5 = st.columns(2)
    with col4:
        inv_color = "#4ade80" if total_investment > 0 else "#888"
        st.markdown(f'<div class="metric-card" style="border-bottom: 3px solid {inv_color}"><div class="metric-label">💰 Investments</div><div class="metric-value" style="color: {inv_color}">₹{total_investment:,.2f}</div></div>', unsafe_allow_html=True)
    with col5:
        ratio_color = "#4ade80" if expense_ratio <= 100 else "#ff4b4b"
        st.markdown(f'<div class="metric-card" style="border-bottom: 3px solid {ratio_color}"><div class="metric-label">📊 Expense Ratio</div><div class="metric-value" style="color: {ratio_color}">{expense_ratio:.1f}%</div></div>', unsafe_allow_html=True)
    
    # ⭐ TOP INSIGHT BANNER — the WOW scannable feature
    investment_ratio = stats.get("investment_ratio", 0)
    if expense_ratio > 100:
        if investment_ratio > 30:
            banner_text = f"⚠️ You're spending {expense_ratio - 100:.0f}% more than you earn, despite strong investment habits (₹{total_investment:,.0f}). Rebalancing is critical."
        else:
            banner_text = f"🔴 Your expenses exceed income by ₹{abs(savings):,.0f}. Expense ratio is {expense_ratio:.0f}% — immediate action needed."
    elif expense_ratio > 90:
        banner_text = f"⚠️ You're saving only {100 - expense_ratio:.0f}% of your income. One unexpected expense could tip you into deficit."
    elif investment_ratio > 40:
        banner_text = f"🟢 Strong financial discipline — ₹{total_investment:,.0f} allocated to investments ({investment_ratio:.0f}% of spending). Savings: ₹{savings:,.0f}."
    else:
        banner_text = f"🟢 Healthy finances — saving ₹{savings:,.0f} ({100 - expense_ratio:.0f}% of income). Keep it up."
    
    banner_bg = "#1a1a2e" if savings >= 0 else "#2d1117"
    banner_border = "#4ade80" if savings >= 0 else "#ff4b4b"
    st.markdown(f"""
    <div style="background: {banner_bg}; border-left: 4px solid {banner_border}; padding: 16px 20px; border-radius: 8px; margin: 12px 0; font-size: 1.1rem;">
        {banner_text}
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    st.subheader("Section 1: 💸 Where your money went")
    cat_col, ins_col = st.columns([1, 1.2]) 
    
    with cat_col:
        st.markdown("##### Category Breakdown")
        category_totals = stats.get("category_totals", {})
        if category_totals:
            chart_data = pd.DataFrame(
                list(category_totals.items()),
                columns=['Category', 'Amount']
            ).set_index('Category')
            st.bar_chart(chart_data, height=300, use_container_width=True)
            
    with ins_col:
        st.markdown("##### 🔥 Top 3 Money Drainers")
        top_merchants = stats.get("top_merchants", [])
        if top_merchants:
            drainers_df = pd.DataFrame(top_merchants)
            drainers_df = drainers_df.rename(columns={"merchant": "Merchant", "amount": "Amount (₹)", "count": "Repeats"})
            st.dataframe(drainers_df, use_container_width=True, hide_index=True)
            
    st.divider()
    
    # Sections 2 & 3: Alerts and Actions generated by LLM
    if st.session_state.insights and not st.session_state.insights.startswith("Error"):
        st.subheader("Section 2 & 3: ⚠️ Alerts & 💡 Actions")
        st.markdown(st.session_state.insights)
    else:
        if st.button("Generate Decision Logic"):
            with st.spinner("Analyzing..."):
                 try:
                    ins_resp = requests.post(f"{API_URL}/session/insights", json={"session_id": st.session_state.session_id})
                    if ins_resp.status_code == 200:
                        st.session_state.insights = ins_resp.json().get("insights", "")
                        st.rerun()
                 except Exception as e:
                    st.error("Engine unavailable right now.")
                    
    st.divider()
    
    list_col = st.container()
    
    with list_col:
        st.subheader("📝 Transaction History")
        st.markdown("*Edit any category! Click 'Save Changes' to update your charts and train the AI.*")
        df = pd.DataFrame(st.session_state.transactions)
        
        # Interactive data editor
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            height=600,
            column_config={
                "merchant": st.column_config.TextColumn("Merchant", disabled=True),
                "confidence": st.column_config.TextColumn("Confidence / Source", disabled=True),
                "category": st.column_config.TextColumn("Category", help="Type a custom category!"),
                "amount": st.column_config.NumberColumn("Amount (₹)", format="₹%f")
            }
        )
        
        if st.button("💾 Save Changes & Update Analytics", type="primary"):
            old_txs = st.session_state.transactions
            new_txs = edited_df.to_dict('records')
            
            # PROTECT: Force all credit transactions back to Income — no overrides allowed
            for tx in new_txs:
                if tx.get("type") == "credit":
                    tx["category"] = "Income"
                    tx["confidence"] = "100% (Deterministic)"
            
            changes = {}
            for old_tx, new_tx in zip(old_txs, new_txs):
                # Skip credit transactions — their category is locked to Income
                if old_tx.get("type") == "credit":
                    continue
                if old_tx.get('category') != new_tx.get('category'):
                    merch = old_tx.get('merchant')
                    new_cat = new_tx.get('category')
                    changes[merch] = new_cat
            
            if changes:
                # Propagate changes strictly via merchant (debits only)
                for tx in new_txs:
                    if tx.get("type") == "credit":
                        continue
                    merch = tx.get('merchant')
                    if merch in changes:
                        tx['category'] = changes[merch]
                        tx['confidence'] = "100% (Learned Mapping)"
                        
                st.session_state.transactions = new_txs
                
                with st.spinner("Training Merchant Matrix..."):
                    try:
                        payload = {
                            "session_id": st.session_state.session_id,
                            "transactions": new_txs,
                            "merchant_changes": changes
                        }
                        resp = requests.post(f"{API_URL}/session/update", json=payload)
                        if resp.status_code == 200:
                            st.session_state.stats = resp.json().get("stats", {})
                            
                            # Optional: Refresh insights too
                            try:
                                ins_resp = requests.post(f"{API_URL}/session/insights", json={"session_id": st.session_state.session_id})
                                if ins_resp.status_code == 200:
                                    st.session_state.insights = ins_resp.json().get("insights", "")
                            except: pass
                            
                            st.success("Session Updated and Matrix Trained!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error updating analytics: {e}")
            else:
                st.info("No category changes detected.")
                
    st.divider()
        
    chat_col = st.container()
    with chat_col:
        st.subheader("💬 Financial Assistant")
        
        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state.chat_history:
                st.chat_message(msg["role"]).write(msg["content"])
                
        # --- Template Questions ---
        if not st.session_state.chat_history:
            st.markdown("###### 💡 Try asking:")
            template_questions = [
                "What kind of spender am I?",
                "Where is most of my money going?",
                "How can I save ₹5,000 this month?",
                "Am I investing enough?",
                "What's my biggest financial risk?",
                "Give me a 3-step plan to fix my finances"
            ]
            # Render as clickable buttons in a 3-column grid
            tq_cols = st.columns(3)
            for i, q in enumerate(template_questions):
                with tq_cols[i % 3]:
                    if st.button(q, key=f"tq_{i}", use_container_width=True):
                        st.session_state.chat_history.append({"role": "user", "content": q})
                        with st.spinner("Thinking..."):
                            try:
                                chat_payload = {"session_id": st.session_state.session_id, "message": q}
                                chat_resp = requests.post(f"{API_URL}/session/chat", json=chat_payload)
                                if chat_resp.status_code == 200:
                                    reply = chat_resp.json().get("reply", "")
                                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                                    st.rerun()
                            except Exception as e:
                                st.error("Chat engine unavailable.")
                                
        user_input = st.chat_input("E.g. What kind of spender am I?")
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with chat_container:
                st.chat_message("user").write(user_input)
                
            with st.spinner("Thinking..."):
                try:
                    chat_payload = {
                        "session_id": st.session_state.session_id,
                        "message": user_input
                    }
                    chat_resp = requests.post(f"{API_URL}/session/chat", json=chat_payload)
                    if chat_resp.status_code == 200:
                        reply = chat_resp.json().get("reply", "")
                        st.session_state.chat_history.append({"role": "assistant", "content": reply})
                        st.rerun()
                except Exception as e:
                    st.error("Chat engine unavailable.")
