import streamlit as st
import pandas as pd
import plotly.express as px
from groq import Groq
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SYSTEM CONFIG ---
st.set_page_config(page_title="OVERWATCH v4", page_icon="🛡️", layout="wide")

# --- 2. DATABASE CONNECTION (DIRECT MODE) ---
def connect_to_gsheet():
    # Define the Scope
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Load Credentials from Streamlit Secrets
    try:
        # We construct the credentials dictionary manually from secrets
        creds_dict = {
            "type": st.secrets["connections"]["gsheets"]["type"],
            "project_id": st.secrets["connections"]["gsheets"]["project_id"],
            "private_key_id": st.secrets["connections"]["gsheets"]["private_key_id"],
            "private_key": st.secrets["connections"]["gsheets"]["private_key"],
            "client_email": st.secrets["connections"]["gsheets"]["client_email"],
            "client_id": st.secrets["connections"]["gsheets"]["client_id"],
            "auth_uri": st.secrets["connections"]["gsheets"]["auth_uri"],
            "token_uri": st.secrets["connections"]["gsheets"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["connections"]["gsheets"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["connections"]["gsheets"]["client_x509_cert_url"],
        }
        
        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=scopes
        )
        
        gc = gspread.authorize(credentials)
        # Open by URL
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_url(url)
        return sh
    except Exception as e:
        st.error(f"DATABASE ERROR: {e}")
        st.stop()

# Initialize API
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    sh = connect_to_gsheet()
    worksheet_logs = sh.worksheet("Logs")
    worksheet_timetable = sh.worksheet("Timetable")
except Exception as e:
    st.error(f"Connection Failed: {e}")
    st.stop()

# --- 3. LOGIC ENGINE ---
def get_day_protocol():
    day_num = datetime.now().weekday()
    if day_num in [0, 2, 4]: return "MWS Protocol"
    elif day_num in [1, 3, 5]: return "TTS Protocol"
    else: return "Sunday Special"

def get_data():
    # Get all values as list of lists
    data_logs = worksheet_logs.get_all_records()
    data_time = worksheet_timetable.get_all_records()
    
    df_logs = pd.DataFrame(data_logs)
    df_timetable = pd.DataFrame(data_time)
    
    # Cleanup Dates
    if not df_logs.empty:
        df_logs['Date'] = pd.to_datetime(df_logs['Date'], errors='coerce')
        # Force numeric conversion for math columns
        cols = ['Duration', 'Output', 'Rot', 'Focus']
        for c in cols:
            df_logs[c] = pd.to_numeric(df_logs[c], errors='coerce').fillna(0)
            
    return df_logs, df_timetable

def write_log(entry_data):
    # Prepare row data in specific order
    row = [
        entry_data["Date"],
        entry_data["Time"],
        entry_data["Type"],
        entry_data["Sector"],
        entry_data["Subject"],
        entry_data["Activity"],
        entry_data["Duration"],
        entry_data["Output"],
        entry_data["Rot"],
        entry_data["Focus"],
        entry_data["Notes"]
    ]
    worksheet_logs.append_row(row)

def calculate_kpi(df):
    if df.empty: return 0, 0, 0
    today = pd.Timestamp.now().normalize()
    # Filter for Metric logs only
    df_today = df[(df['Date'].dt.normalize() == today) & (df['Type'] == 'Metric')]
    
    if df_today.empty: return 0, 0, 0
    
    rot = int(df_today['Rot'].sum())
    # EFS: (Duration * Focus/100) - (Rot * 1.5)
    efs = int(((df_today['Duration'] * (df_today['Focus']/100)) - (df_today['Rot'] * 1.5)).sum())
    
    hours = df_today['Duration'].sum() / 60
    velocity = round(df_today['Output'].sum() / hours, 2) if hours > 0 else 0
    
    return rot, efs, velocity

# --- 4. UI LAYOUT ---

with st.sidebar:
    st.title("🛡️ OVERWATCH")
    protocol = get_day_protocol()
    
    st.caption(f"STATUS: ONLINE | {protocol}")
    if protocol == "MWS Protocol": st.info("📅 FOCUS: Physics / Chemistry")
    elif protocol == "TTS Protocol": st.info("📅 FOCUS: Phy / Chem / Bio (NDA)")
    else: st.success("📅 SUNDAY: Revision")

    st.divider()
    
    # PRIME AI
    st.header("🧠 PRIME UPLINK")
    user_query = st.text_input("Consult Prime...", placeholder="Analyze my week...")
    
    if user_query:
        # Load data for context
        df_logs, _ = get_data()
        stats = df_logs.tail(5).to_string() if not df_logs.empty else "No Data"
        
        prompt = f"""
        User Query: {user_query}
        Current Protocol: {protocol}
        Recent Logs:
        {stats}
        
        You are PRIME. Military tone. Concise.
        """
        
        with st.spinner("Prime computing..."):
            try:
                chat = client.chat.completions.create(
                    messages=[{"role": "system", "content": prompt}],
                    model="llama-3.3-70b-versatile"
                )
                st.info(chat.choices[0].message.content)
            except:
                st.error("Prime Offline.")

    st.divider()
    st.markdown("[📝 Edit/Undo in Google Sheets](https://docs.google.com/spreadsheets)") 

# MAIN DASHBOARD

try:
    df_logs, df_timetable = get_data()
    rot, efs, vel = calculate_kpi(df_logs)
except:
    df_logs = pd.DataFrame()
    df_timetable = pd.DataFrame()
    rot, efs, vel = 0, 0, 0

k1, k2, k3 = st.columns(3)
k1.metric("ROT (WASTED)", f"{rot} min", delta="Limit: 60", delta_color="inverse")
k2.metric("EFS SCORE", f"{efs}", delta="Target: 480")
k3.metric("VELOCITY", f"{vel}", help="Output per Hour")

# LOGGING
with st.expander("📝 LOG DATA (TAP TO OPEN)", expanded=False):
    with st.form("log_entry"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date")
            subject = st.selectbox("Subject", ["Math", "Physics", "Chemistry", "Biology", "English", "GAT"])
            activity = st.selectbox("Activity", ["Deep Study", "Mock Test", "Revision", "Class"])
        with col2:
            duration = st.number_input("Duration (Min)", min_value=0, step=15)
            output = st.number_input("Output (Qty)", min_value=0)
            rot_input = st.number_input("Rot (Min)", min_value=0)
            focus = st.slider("Focus %", 0, 100, 80)
        
        notes = st.text_input("Notes")
        
        if st.form_submit_button("COMMIT TO CLOUD"):
            new_data = {
                "Date": date.strftime("%Y-%m-%d"),
                "Time": datetime.now().strftime("%H:%M:%S"),
                "Type": "Metric",
                "Sector": protocol,
                "Subject": subject,
                "Activity": activity,
                "Duration": duration,
                "Output": output,
                "Rot": rot_input,
                "Focus": focus,
                "Notes": notes
            }
            try:
                write_log(new_data)
                st.success("SYNCED.")
                st.rerun()
            except Exception as e:
                st.error(f"Sync Failed: {e}")

# CHARTS
st.subheader("Situation Report")

if not df_logs.empty:
    tab_day, tab_week = st.tabs(["TODAY", "WEEK"])
    
    with tab_day:
        today = pd.Timestamp.now().normalize()
        today_data = df_logs[df_logs['Date'].dt.normalize() == today]
        
        if not today_data.empty:
            st.bar_chart(today_data, x="Subject", y="Duration", color="Activity")
            st.dataframe(today_data[['Subject', 'Duration', 'Output', 'Rot', 'Notes']], use_container_width=True)
        else:
            st.info("Awaiting today's data.")

    with tab_week:
        st.line_chart(df_logs, x="Date", y="Duration", color="Subject")

# TIMETABLE
st.subheader(f"📅 Protocol: {protocol}")
if not df_timetable.empty:
    # Filter roughly by protocol name in Day_Type
    today_schedule = df_timetable[df_timetable['Day_Type'].astype(str).str.contains(protocol.split()[0], case=False, na=False)]
    
    if not today_schedule.empty:
        st.dataframe(today_schedule[['Time_Slot', 'Task']], use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_timetable)
else:
    st.info("Timetable empty.")
    
