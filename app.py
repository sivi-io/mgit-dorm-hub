import streamlit as st
import datetime
import pandas as pd
import requests
import hashlib
from streamlit_gsheets import GSheetsConnection

# --- TELEGRAM CONFIGURATION ---
# This pulls the token securely from your Streamlit Secrets box automatically
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")

def send_telegram_alert(chat_id, message):
    if not chat_id: 
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except:
        return False

# --- USER DATABASE MOCKUP ---
if 'USER_DATABASE' not in st.session_state:
    st.session_state.USER_DATABASE = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Dorm Hub", page_icon="🏫", layout="centered")

# Initialize global application states if they don't exist
if 'logged_in_user' not in st.session_state: st.session_state.logged_in_user = None
if 'washing_machine_in_use' not in st.session_state: st.session_state.washing_machine_in_use = False
if 'mess_log' not in st.session_state: st.session_state.mess_log = []
if 'seats_occupied' not in st.session_state: st.session_state.seats_occupied = 0

# --- AUTHENTICATION SCREEN ---
if st.session_state.logged_in_user is None:
    st.title("🔒 Dorm Hub Access")
    login_tab, signup_tab = st.tabs(["Login", "Create Account"])
    
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("College Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user = st.session_state.USER_DATABASE.get(email)
                if user and user["password_hash"] == hash_password(password):
                    st.session_state.logged_in_user = user
                    st.session_state.logged_in_user['email'] = email
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
                    
    with signup_tab:
        with st.form("signup_form"):
            new_name = st.text_input("Full Name")
            new_email = st.text_input("College Email")
            new_password = st.text_input("Create Password", type="password")
            new_telegram = st.text_input("Telegram Chat ID")
            
            if st.form_submit_button("Create Account"):
                if not new_email.endswith("@mgit.ac.in"):
                    st.error("Must use a valid @mgit.ac.in email.")
                elif new_email in st.session_state.USER_DATABASE:
                    st.warning("Account exists.")
                elif not all([new_name, new_password, new_telegram]):
                    st.error("Fill in all fields.")
                else:
                    st.session_state.USER_DATABASE[new_email] = {
                        "password_hash": hash_password(new_password),
                        "role": "student",
                        "telegram_id": new_telegram,
                        "name": new_name
                    }
                    st.success("Account created! Log in above.")
    st.stop() # Stops the rest of the app from loading if not logged in

# --- MAIN DASHBOARD SCREEN (Only accessible after login) ---
user = st.session_state.logged_in_user
st.title(f"🏫 Welcome, {user['name']}")

# Logout option in sidebar
if st.sidebar.button("Logout"):
    st.session_state.logged_in_user = None
    st.rerun()

# This line defines the layout tabs explicitly so Python recognizes them
tab1, tab2, tab3 = st.tabs(["🧺 Laundry", "🍽️ Mess", "📓 Expenses"])

# --- TAB 1: LAUNDRY MANAGEMENT ---
with tab1:
    st.header("Washing Machine Status")
    if st.session_state.washing_machine_in_use:
        st.warning("🔴 IN USE")
        if st.button("Mark as Available"):
            st.session_state.washing_machine_in_use = False
            send_telegram_alert(user["telegram_id"], "🧺 You marked the washing machine as available.")
            st.rerun()
    else:
        st.info("🟢 AVAILABLE")
        if st.button("Mark as In Use"):
            st.session_state.washing_machine_in_use = True
            st.rerun()

# --- TAB 2: LIVE MESS SEATING ---
with tab2:
    st.header("🍽️ Live Mess Seating")
    available_seats = 50 - st.session_state.seats_occupied
    st.metric("Available Seats", available_seats)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("I took a seat") and available_seats > 0:
            st.session_state.seats_occupied += 1
            st.session_state.mess_log.insert(0, {"Time": datetime.datetime.now().strftime('%I:%M %p'), "User": user['name'], "Action": "Entered"})
            st.rerun()
    with col2:
        if st.button("Leaving") and st.session_state.seats_occupied > 0:
            st.session_state.seats_occupied -= 1
            st.session_state.mess_log.insert(0, {"Time": datetime.datetime.now().strftime('%I:%M %p'), "User": user['name'], "Action": "Left"})
            st.rerun()

# --- TAB 3: PRIVATE GOOGLE SHEETS EXPENSE LEDGER ---
with tab3:
    st.header("📓 Private Expense Ledger (Google Sheets)")
    
    # Securely connect to your Google Sheet using the secrets configured on the web dashboard
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Read the spreadsheet database safely
    try:
        df = conn.read(worksheet="Expenses", ttl=0)
    except Exception:
        df = pd.DataFrame(columns=["Email", "Date", "Category", "Amount", "Description"])

    # Form interface for entering a new entry
    with st.form("add_expense_gsheets"):
        category = st.selectbox("Category", ["Rent", "College Fees", "Laundry", "Food/Mess", "Other"])
        amount = st.number_input("Amount (₹)", min_value=0)
        desc = st.text_input("Description")
        
        if st.form_submit_button("Save to Cloud"):
            new_row = pd.DataFrame([{
                "Email": user['email'], 
                "Date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "Category": category, 
                "Amount": amount, 
                "Description": desc
            }])
            
            # Append new entry to existing data framework
            updated_df = pd.concat([df, new_row], ignore_index=True)
            
            # Send updated framework back up to Google Drive
            conn.update(worksheet="Expenses", data=updated_df)
            st.success("Saved securely to Google Cloud!")
            st.rerun()
            
    # Filter the cloud data frame dynamically so a user only sees their own values
    if not df.empty:
        user_df = df[df["Email"] == user['email']].drop(columns=["Email"])
        if not user_df.empty:
            st.dataframe(user_df, use_container_width=True)
            st.write(f"**Total Spent: ₹{pd.to_numeric(user_df['Amount']).sum()}**")