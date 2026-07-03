import os
import time
import httpx
import streamlit as st
import streamlit.components.v1 as components

# Configure Streamlit page parameters
st.set_page_config(
    page_title="Action Guardrail — Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Server Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Premium Dark Mode Glassmorphism Styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;600&display=swap');
    
    /* Main body background and fonts */
    .stApp {
        background-color: #0E1117;
        color: #E2E8F0;
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Glassmorphic Cards */
    .glass-card {
        background: rgba(30, 41, 59, 0.45);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.15);
    }
    
    /* Headers styling */
    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 600;
        letter-spacing: -0.5px;
    }
    
    .gradient-text {
        background: linear-gradient(135deg, #00C0F2 0%, #8E2DE2 50%, #4A00E0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 6px 12px;
        font-size: 0.85rem;
        font-weight: 600;
        border-radius: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        text-align: center;
    }
    .badge-allowed {
        background-color: rgba(46, 204, 113, 0.15);
        color: #2ECC71;
        border: 1px solid rgba(46, 204, 113, 0.3);
    }
    .badge-blocked {
        background-color: rgba(231, 76, 60, 0.15);
        color: #E74C3C;
        border: 1px solid rgba(231, 76, 60, 0.3);
    }
    .badge-pending {
        background-color: rgba(243, 156, 18, 0.15);
        color: #F39C12;
        border: 1px solid rgba(243, 156, 18, 0.3);
    }
    .badge-none {
        background-color: rgba(149, 165, 166, 0.15);
        color: #95A5A6;
        border: 1px solid rgba(149, 165, 166, 0.3);
    }
    
    /* Custom input/form fields customization */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input, .stTextArea>div>div>textarea {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
    }
    .stButton>button {
        background: linear-gradient(135deg, #4A00E0 0%, #8E2DE2 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 24px !important;
        box-shadow: 0 4px 15px rgba(142, 45, 226, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(142, 45, 226, 0.5) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Helper function to check health status
def check_api_health() -> tuple[bool, dict]:
    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{API_URL}/health")
            if response.status_code == 200:
                return True, response.json()
    except Exception:
        pass
    return False, {}

# Check health initially
api_online, health_data = check_api_health()

# Layout Header
col_title, col_status = st.columns([4, 1])

with col_title:
    st.markdown('<h1 class="gradient-text" style="margin-bottom: 0px; font-size: 2.8rem;">🛡️ Action Guardrail</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #94A3B8; font-size: 1.1rem; margin-top: 5px;">Real-time AI Agent tool interception & safety gate</p>', unsafe_allow_html=True)

with col_status:
    if api_online:
        st.markdown(
            f"""
            <div style="background-color: rgba(46, 204, 113, 0.1); border: 1px solid rgba(46, 204, 113, 0.3); border-radius: 12px; padding: 12px; text-align: center; margin-top: 15px;">
                <span style="color: #2ECC71; font-weight: bold; font-size: 0.9rem;">● SYSTEM ONLINE</span><br/>
                <span style="color: #94A3B8; font-size: 0.75rem;">v{health_data.get('version', '1.0')}</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style="background-color: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.3); border-radius: 12px; padding: 12px; text-align: center; margin-top: 15px;">
                <span style="color: #E74C3C; font-weight: bold; font-size: 0.9rem;">● SYSTEM OFFLINE</span><br/>
                <span style="color: #E74C3C; font-size: 0.75rem;">Cannot reach API server</span>
            </div>
            """,
            unsafe_allow_html=True
        )

# Sidebar - Settings and manual triggers
st.sidebar.markdown('<h3 style="margin-top: 0px;">🛡️ Navigation</h3>', unsafe_allow_html=True)
section = st.sidebar.radio("Go to:", ["Control Panel", "Live Audit Logs", "HITL Review Queue"])

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ API Settings")
api_endpoint_input = st.sidebar.text_input("FastAPI Server URL", value=API_URL)
if api_endpoint_input != API_URL:
    API_URL = api_endpoint_input

# Hidden refresh button to trigger rerun
if st.sidebar.button("Force Refresh", key="refresh_sidebar"):
    st.rerun()

# Automatically register HTML autorefresh to hit "Force Refresh" button every 5 seconds
# if on Audit Logs or Queue view
if section in ["Live Audit Logs", "HITL Review Queue"]:
    components.html(
        """
        <script>
        const triggerRefresh = () => {
            const buttons = window.parent.document.querySelectorAll("button");
            const refreshBtn = Array.from(buttons).find(el => el.innerText === "Force Refresh");
            if (refreshBtn) {
                refreshBtn.click();
            }
        };
        setTimeout(triggerRefresh, 5000);
        </script>
        """,
        height=0,
        width=0
    )

if not api_online:
    st.warning("⚠️ API server is currently unreachable. Make sure uvicorn is running, or check the URL in the sidebar.")

# ----------------- SECTION 1: CONTROL PANEL -----------------
if section == "Control Panel":
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<h3>🎮 Policy Playground</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color: #94A3B8; font-size: 0.9rem;">Submit a raw tool action directly to evaluate security conditions.</p>', unsafe_allow_html=True)
        
        # Tool selector
        tool_choice = st.selectbox(
            "Select Tool",
            ["delete_records", "send_email", "read_file"]
        )
        
        # Dynamic parameter forms based on selected tool
        params = {}
        if tool_choice == "delete_records":
            params["table"] = st.text_input("Database Table", value="customers")
            params["count"] = st.number_input("Delete Count", min_value=1, value=5, step=1)
        elif tool_choice == "send_email":
            params["to"] = st.text_input("Recipient Name", value="alice")
            params["domain"] = st.text_input("Domain", value="gmail.com")
            params["body"] = st.text_area("Email Body", value="Important update for customer account info.")
        elif tool_choice == "read_file":
            params["path"] = st.text_input("File Path", value="/data/confidential/financials.csv")
            
        dry_run = st.checkbox("Dry Run (Evaluate rules but do not execute tool)", value=False)
        
        submit_action = st.button("Evaluate Action", disabled=not api_online)
        st.markdown('</div>', unsafe_allow_html=True)
        
        if submit_action and api_online:
            with st.spinner("Evaluating policy..."):
                try:
                    payload = {"tool": tool_choice, "params": params, "dry_run": dry_run}
                    response = httpx.post(f"{API_URL}/act", json=payload, timeout=5.0)
                    
                    if response.status_code == 200:
                        res = response.json()
                        outcome = res.get("outcome", "unknown")
                        matched_rule = res.get("matched_rule", "none")
                        reason = res.get("reason", "")
                        executed = res.get("executed", False)
                        result = res.get("result", None)
                        
                        st.markdown("### 🔍 Evaluation Result")
                        
                        # Outcome Display Card
                        badge_class = "badge-allowed"
                        if outcome == "blocked":
                            badge_class = "badge-blocked"
                        elif outcome == "pending_review":
                            badge_class = "badge-pending"
                            
                        st.markdown(
                            f"""
                            <div style="background-color: #1E293B; border-radius: 12px; padding: 20px; border-left: 6px solid {'#2ECC71' if outcome == 'allowed' else '#E74C3C' if outcome == 'blocked' else '#F39C12'};">
                                <span class="badge {badge_class}" style="margin-bottom: 10px;">{outcome}</span>
                                <h4 style="margin: 5px 0px;">Matched Rule: <code>{matched_rule}</code></h4>
                                <p style="color: #94A3B8; font-size: 0.95rem; margin: 5px 0px;">{reason}</p>
                                <p style="font-weight: bold; margin-top: 10px;">Executed: <span style="color: {'#2ECC71' if executed else '#E74C3C'}">{'Yes ✓' if executed else 'No ✗'}</span></p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        if result:
                            st.json(result)
                    else:
                        st.error(f"Error evaluating action: {response.text}")
                except Exception as e:
                    st.error(f"Failed to submit request to API: {e}")
                    
    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<h3>🤖 LLM Agent Sandbox</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color: #94A3B8; font-size: 0.9rem;">Type a request in plain English. Claude will translate it into a tool call which is then governed by the guardrail.</p>', unsafe_allow_html=True)
        
        user_message = st.text_area(
            "Agent Instruction", 
            placeholder="e.g. Delete 50 inactive customer records from the database..."
        )
        
        agent_dry_run = st.checkbox("Dry Run (Agent)", value=False, key="agent_dry_run")
        submit_agent = st.button("Send Instruction", disabled=not api_online)
        st.markdown('</div>', unsafe_allow_html=True)
        
        if submit_agent and api_online:
            if not user_message.strip():
                st.error("Please enter a non-empty instruction for the agent.")
            else:
                with st.spinner("Agent thinking & safety evaluation running..."):
                    try:
                        payload = {"user_message": user_message, "dry_run": agent_dry_run}
                        response = httpx.post(f"{API_URL}/request", json=payload, timeout=15.0)
                        
                        if response.status_code == 200:
                            res = response.json()
                            outcome = res.get("outcome", "none")
                            matched_rule = res.get("matched_rule", "none")
                            reason = res.get("reason", "")
                            executed = res.get("executed", False)
                            action_decided = res.get("action_decided", None)
                            result = res.get("result", None)
                            
                            st.markdown("### 🤖 Agent Thought & Action")
                            
                            if action_decided:
                                st.markdown("##### 📦 Tool Action Decided by Agent:")
                                st.code(f"Tool: {action_decided.get('tool')}\nParams: {action_decided.get('params')}", language="json")
                                
                                badge_class = "badge-allowed"
                                if outcome == "blocked":
                                    badge_class = "badge-blocked"
                                elif outcome == "pending_review":
                                    badge_class = "badge-pending"
                                    
                                st.markdown(
                                    f"""
                                    <div style="background-color: #1E293B; border-radius: 12px; padding: 20px; border-left: 6px solid {'#2ECC71' if outcome == 'allowed' else '#E74C3C' if outcome == 'blocked' else '#F39C12'}; margin-top: 15px;">
                                        <span class="badge {badge_class}" style="margin-bottom: 10px;">{outcome}</span>
                                        <h4 style="margin: 5px 0px;">Matched Rule: <code>{matched_rule}</code></h4>
                                        <p style="color: #94A3B8; font-size: 0.95rem; margin: 5px 0px;">{reason}</p>
                                        <p style="font-weight: bold; margin-top: 10px;">Executed: <span style="color: {'#2ECC71' if executed else '#E74C3C'}">{'Yes ✓' if executed else 'No ✗'}</span></p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                                
                                if result:
                                    st.json(result)
                            else:
                                st.markdown(
                                    """
                                    <div style="background-color: #1E293B; border-radius: 12px; padding: 20px; border-left: 6px solid #95A5A6;">
                                        <span class="badge badge-none" style="margin-bottom: 10px;">NONE</span>
                                        <h4 style="margin: 5px 0px;">No Tool Triggered</h4>
                                        <p style="color: #94A3B8; font-size: 0.95rem; margin: 5px 0px;">Claude determined that this query did not require executing any registered database, file, or email tools.</p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                        else:
                            st.error(f"Error running agent sandbox: {response.text}")
                    except Exception as e:
                        st.error(f"Failed to submit agent request: {e}")

# ----------------- SECTION 2: LIVE AUDIT LOGS -----------------
elif section == "Live Audit Logs":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<h3>📜 Real-time Guardrail Audit Log</h3>', unsafe_allow_html=True)
    st.markdown('<p style="color: #94A3B8; font-size: 0.9rem;">Auto-refreshes every 5 seconds. Displays recent policy decisions and execution status.</p>', unsafe_allow_html=True)
    
    col_filter, col_limit = st.columns([2, 1])
    with col_filter:
        outcome_filter = st.selectbox(
            "Filter by Outcome",
            ["All", "allowed", "blocked", "pending_review"]
        )
    with col_limit:
        limit_count = st.number_input("Limit entries", min_value=5, max_value=200, value=20, step=5)
        
    st.markdown('</div>', unsafe_allow_html=True)
    
    if api_online:
        try:
            params = {"limit": limit_count}
            if outcome_filter != "All":
                params["outcome"] = outcome_filter
                
            response = httpx.get(f"{API_URL}/audit", params=params, timeout=5.0)
            if response.status_code == 200:
                logs = response.json()
                if not logs:
                    st.info("No audit logs found matching selected filter.")
                else:
                    for log in logs:
                        log_id = log.get("id")
                        timestamp = log.get("timestamp")
                        tool = log.get("tool")
                        outcome = log.get("outcome", "unknown")
                        matched_rule = log.get("matched_rule", "none")
                        reason = log.get("reason", "")
                        executed = log.get("executed", False)
                        tool_params = log.get("params", {})
                        
                        # Style parameters based on outcome
                        badge_class = "badge-allowed"
                        border_color = "#2ECC71"
                        if outcome == "blocked":
                            badge_class = "badge-blocked"
                            border_color = "#E74C3C"
                        elif outcome == "pending_review":
                            badge_class = "badge-pending"
                            border_color = "#F39C12"
                            
                        # Format local timestamp cleanly
                        try:
                            clean_time = timestamp.split(".")[0].replace("T", " ")
                        except Exception:
                            clean_time = timestamp
                            
                        # Build a clean details summary
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(30, 41, 59, 0.35); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 18px; margin-bottom: 12px; border-left: 5px solid {border_color};">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                    <div>
                                        <span class="badge {badge_class}">{outcome}</span>
                                        <span style="font-weight: bold; margin-left: 10px; font-size: 1rem;">#{log_id} - Tool: <code>{tool}</code></span>
                                    </div>
                                    <span style="color: #64748B; font-size: 0.85rem;">{clean_time} (UTC)</span>
                                </div>
                                <div style="color: #E2E8F0; font-size: 0.95rem; margin-bottom: 8px;">
                                    <strong>Condition Triggered:</strong> <code>{matched_rule}</code> &mdash; {reason}
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <div style="font-size: 0.85rem; color: #94A3B8;">
                                        <strong>Params:</strong> <code>{tool_params}</code>
                                    </div>
                                    <div style="font-size: 0.9rem;">
                                        <strong>Executed:</strong> <span style="color: {'#2ECC71' if executed else '#E74C3C'}; font-weight: bold;">{'Yes ✓' if executed else 'No ✗'}</span>
                                    </div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            else:
                st.error("Failed to retrieve audit logs from API.")
        except Exception as e:
            st.error(f"Error fetching audit logs: {e}")

# ----------------- SECTION 3: HITL REVIEW QUEUE -----------------
elif section == "HITL Review Queue":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<h3>📥 Human-In-The-Loop Pending Review Queue</h3>', unsafe_allow_html=True)
    st.markdown('<p style="color: #94A3B8; font-size: 0.9rem;">Actions flagged as <code>pending_review</code> are held here. Approving them runs the tool immediately; rejecting blocks execution.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    if api_online:
        try:
            response = httpx.get(f"{API_URL}/review", timeout=5.0)
            if response.status_code == 200:
                pending_items = response.json()
                if not pending_items:
                    st.success("🎉 All clear! There are no actions pending human review.")
                else:
                    st.markdown(f"##### Total actions waiting for review: **{len(pending_items)}**")
                    
                    for item in pending_items:
                        item_id = item.get("id")
                        tool = item.get("tool")
                        params_val = item.get("params", {})
                        reason = item.get("reason", "")
                        timestamp = item.get("timestamp", "")
                        
                        try:
                            clean_time = timestamp.split(".")[0].replace("T", " ")
                        except Exception:
                            clean_time = timestamp
                            
                        # Show card
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(243, 156, 18, 0.05); border: 1px solid rgba(243, 156, 18, 0.2); border-radius: 12px; padding: 20px; margin-bottom: 20px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                    <span class="badge badge-pending">PENDING DECISION</span>
                                    <span style="color: #64748B; font-size: 0.85rem;">Held at: {clean_time} (UTC)</span>
                                </div>
                                <h4 style="margin: 5px 0px;">Action Request #{item_id}: <code>{tool}</code></h4>
                                <p style="font-size: 0.9rem; color: #94A3B8; margin-top: 5px;"><strong>Reason for hold:</strong> {reason}</p>
                                <p style="font-family: monospace; font-size: 0.85rem; background-color: #0E1117; padding: 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">Params: {params_val}</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        # Form for resolving review
                        with st.form(key=f"review_form_{item_id}"):
                            col_reviewer, col_notes = st.columns([1, 2])
                            with col_reviewer:
                                reviewer_name = st.text_input("Reviewer Name", placeholder="e.g. Security Admin", key=f"reviewer_{item_id}")
                            with col_notes:
                                review_notes = st.text_input("Reviewer Notes / Reason", placeholder="Explain approval/rejection details", key=f"notes_{item_id}")
                                
                            col_approve, col_reject, _ = st.columns([1, 1, 4])
                            with col_approve:
                                approve_submitted = st.form_submit_button("Approve Action")
                            with col_reject:
                                reject_submitted = st.form_submit_button("Reject Action")
                                
                            if approve_submitted:
                                if not reviewer_name.strip():
                                    st.error("Please enter a Reviewer Name to approve.")
                                else:
                                    try:
                                        payload = {"reviewer_name": reviewer_name, "notes": review_notes}
                                        res = httpx.post(f"{API_URL}/review/{item_id}/approve", json=payload, timeout=5.0)
                                        if res.status_code == 200:
                                            st.success(f"✓ Approved and executed action #{item_id} successfully!")
                                            time.sleep(1.0)
                                            st.rerun()
                                        else:
                                            st.error(f"Failed to approve: {res.text}")
                                    except Exception as err:
                                        st.error(f"Approval endpoint request failed: {err}")
                                        
                            if reject_submitted:
                                if not reviewer_name.strip():
                                    st.error("Please enter a Reviewer Name to reject.")
                                elif not review_notes.strip():
                                    st.error("Please provide rejection notes / reason.")
                                else:
                                    try:
                                        payload = {"reviewer_name": reviewer_name, "reason": review_notes}
                                        res = httpx.post(f"{API_URL}/review/{item_id}/reject", json=payload, timeout=5.0)
                                        if res.status_code == 200:
                                            st.warning(f"✗ Action #{item_id} rejected and blocked.")
                                            time.sleep(1.0)
                                            st.rerun()
                                        else:
                                            st.error(f"Failed to reject: {res.text}")
                                    except Exception as err:
                                        st.error(f"Rejection endpoint request failed: {err}")
            else:
                st.error("Failed to query reviews from server.")
        except Exception as e:
            st.error(f"Error querying pending review items: {e}")
