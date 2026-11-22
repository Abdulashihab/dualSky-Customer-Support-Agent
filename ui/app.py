import subprocess
import sys
from pathlib import Path

# Streamlit runs this file from the ui folder, so we add the project folder
# to Python's search path. Without this, "from src..." would not work.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.agent.agent import chat_turn
from src.auth.login import request_otp, verify_otp
from src.tools.account import get_account
from src.tools.work_orders import get_work_orders

st.set_page_config(page_title="Dualsky Customer Support", page_icon="📡", layout="wide")


def apply_dualsky_theme():
    """Apply Dualsky teal, mint, and crisp card styling."""
    st.markdown(
        """
        <style>
        /* Branded Dualsky top header banner */
        .dualsky-banner {
            background: linear-gradient(135deg, #064E43 0%, #0E7C6B 100%);
            color: #FFFFFF;
            padding: 1.1rem 1.5rem;
            border-radius: 12px;
            margin-bottom: 1rem;
            box-shadow: 0 4px 14px rgba(6, 78, 67, 0.16);
        }
        .dualsky-banner h2 {
            color: #FFFFFF;
            margin: 0;
            font-size: 1.5rem;
            letter-spacing: 0.3px;
        }
        .dualsky-banner p {
            color: #D1FAE5;
            margin: 0.25rem 0 0 0;
            font-size: 0.92rem;
        }

        /* Primary buttons styled in Dualsky teal */
        div.stButton > button {
            background-color: #0E7C6B;
            color: #FFFFFF;
            border: none;
            border-radius: 8px;
            padding: 0.45rem 1rem;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        div.stButton > button:hover {
            background-color: #064E43;
            color: #FFFFFF;
            transform: translateY(-1px);
        }

        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            border-right: 1px solid #CBE3DD;
        }

        /* Status badges and pack pills */
        .status-active {
            display: inline-block;
            background-color: #D1FAE5;
            color: #065F46;
            padding: 0.2rem 0.65rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
            margin-bottom: 0.6rem;
        }
        .status-suspended {
            display: inline-block;
            background-color: #FEE2E2;
            color: #991B1B;
            padding: 0.2rem 0.65rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
            margin-bottom: 0.6rem;
        }
        .pack-pill {
            display: inline-block;
            background-color: #FFFFFF;
            color: #0E7C6B;
            border: 1px solid #0E7C6B;
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            margin: 0.15rem 0.25rem 0.15rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(subtitle="24/7 AI Support Assistant"):
    """Render the Dualsky branded header card."""
    st.markdown(
        f"""
        <div class="dualsky-banner">
            <h2>📡 Dualsky Customer Support</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


OTP_MESSAGES = {
    "wrong_code": "That code is not correct.",
    "otp_expired": "That code has expired. Please ask for a new one.",
    "too_many_attempts": "Too many wrong tries. Please ask for a new code.",
    "no_otp_requested": "Please ask for a code first.",
}

QUICK_PROMPTS = [
    ("💰 Check my balance & packs", "What is my current balance, monthly charge, and active packs?"),
    ("📺 Add or drop packs", "How do I add or drop packs on my connection?"),
    ("📡 No signal error", "My TV shows no signal. How can I fix it?"),
    ("⏸️ Temporary suspension", "How does temporary suspension work and what are the rules?"),
]


def start_state():
    """Create the values this page remembers between clicks."""
    defaults = {
        "stage": "phone",        # phone -> otp -> choose -> chat
        "rmn": "",
        "demo_code": "",
        "connections": [],
        "subscriber_id": None,
        "history": [],           # what the AI remembers
        "chat": [],              # what we show on the screen
        "queued_prompt": None,   # stores a clicked quick-action question
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def log_out():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def reset_demo_database():
    """Re-run seed.py to restore clean demo data and clear current chat."""
    subprocess.run([sys.executable, str(PROJECT_ROOT / "seed.py")], check=True)
    st.session_state.history = []
    st.session_state.chat = []
    st.session_state.queued_prompt = None
    st.toast("Demo database reset to clean initial state!", icon="✅")
    st.rerun()


def send_user_message(subscriber_id, text):
    """Send one message through the agent and store both sides in session state."""
    st.session_state.chat.append({"role": "user", "content": text})
    try:
        with st.spinner("Dualsky AI is checking your account and help docs..."):
            reply = chat_turn(subscriber_id, st.session_state.history, text)
    except Exception as error:
        reply = f"Sorry, something went wrong: {error}"
    st.session_state.chat.append({"role": "assistant", "content": reply})


def phone_page():
    render_header("Log in with your registered mobile number")
    st.caption("Demo tip: Try `9000000003` (Karthik) or `9000000010` (multi-connection account).")
    rmn = st.text_input("Registered mobile number", max_chars=10, placeholder="Enter 10-digit mobile number")
    if st.button("Send code"):
        result = request_otp(rmn.strip())
        if result["ok"]:
            st.session_state.rmn = rmn.strip()
            st.session_state.demo_code = result["otp"]
            st.session_state.stage = "otp"
            st.rerun()
        else:
            st.error("This mobile number is not registered.")


def otp_page():
    render_header("Verify your one-time login code")
    # DEMO ONLY: a real app would send the code by SMS instead of showing it.
    st.info(f"Demo only: your code is **{st.session_state.demo_code}**")
    code = st.text_input("6 digit code", max_chars=6, placeholder="Enter 6-digit OTP")
    if st.button("Log in"):
        result = verify_otp(st.session_state.rmn, code)
        if result["ok"]:
            st.session_state.connections = result["connections"]
            if len(result["connections"]) == 1:
                st.session_state.subscriber_id = result["connections"][0]["subscriber_id"]
                st.session_state.stage = "chat"
            else:
                st.session_state.stage = "choose"
            st.rerun()
        else:
            st.error(OTP_MESSAGES.get(result["reason"], "Something went wrong."))
            if result["reason"] != "wrong_code":
                st.session_state.stage = "phone"


def choose_page():
    render_header("Select your DTH connection")
    options = {
        f"{c['subscriber_id']} ({c['kind']})": c["subscriber_id"]
        for c in st.session_state.connections
    }
    label = st.radio("Which connection do you need help with?", list(options))
    if st.button("Continue"):
        st.session_state.subscriber_id = options[label]
        st.session_state.stage = "chat"
        st.rerun()


def chat_page():
    subscriber_id = st.session_state.subscriber_id
    account = get_account(subscriber_id)

    with st.sidebar:
        st.subheader(f"👤 {account['name']}")
        st.caption(f"Subscriber ID: **{subscriber_id}** ({account['kind']})")

        badge_class = "status-active" if account["status"] == "active" else "status-suspended"
        st.markdown(
            f'<span class="{badge_class}">● {account["status"].upper()}</span>',
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        col1.metric("Balance", f"₹{account['balance']:.0f}")
        col2.metric("Monthly", f"₹{account['monthly_charge']:.0f}")

        st.write(f"**Due date:** {account['due_date']}")

        st.write("**Active Packs:**")
        pills_html = "".join(
            f'<span class="pack-pill">{p["pack_id"]}</span>' for p in account["packs"]
        )
        st.markdown(pills_html, unsafe_allow_html=True)

        orders = get_work_orders(subscriber_id)
        if orders:
            st.markdown("---")
            st.write("**Work Orders:**")
            for order in orders:
                st.write(f"• `{order['wo_id']}`: {order['issue_type']} (*{order['status']}*)")

        st.markdown("---")
        c_reset, c_logout = st.columns(2)
        if c_reset.button("Reset Demo", help="Restore initial database state"):
            reset_demo_database()
        if c_logout.button("Log out"):
            log_out()

    render_header("Online • Ask about packs, balance, signal issues, or account changes")

    # Welcome greeting shown at the top of the conversation
    with st.chat_message("assistant", avatar="📡"):
        st.write(
            f"Hello **{account['name'].split()[0]}**! I am your **Dualsky AI Support** assistant. "
            "You can pick a quick question below or type anything in plain language."
        )

    # Render conversation history
    for item in st.session_state.chat:
        avatar = "👤" if item["role"] == "user" else "📡"
        with st.chat_message(item["role"], avatar=avatar):
            st.write(item["content"])

    # Quick-action prompt chips above the input box
    st.caption("Quick questions:")
    chip_cols = st.columns(len(QUICK_PROMPTS))
    for idx, (label, full_question) in enumerate(QUICK_PROMPTS):
        if chip_cols[idx].button(label, key=f"chip_{idx}", use_container_width=True):
            st.session_state.queued_prompt = full_question
            st.rerun()

    # Handle either a clicked chip or typed text input
    typed_prompt = st.chat_input("Type your message...")
    active_prompt = st.session_state.queued_prompt or typed_prompt
    if active_prompt:
        st.session_state.queued_prompt = None
        send_user_message(subscriber_id, active_prompt)
        st.rerun()


apply_dualsky_theme()
start_state()
stage = st.session_state.stage
if stage == "phone":
    phone_page()
elif stage == "otp":
    otp_page()
elif stage == "choose":
    choose_page()
else:
    chat_page()
