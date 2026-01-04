import streamlit as st
import pandas as pd
import plotly.express as px
from groq import Groq
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SYSTEM CONFIG ---
st.set_page_config(page_title="OVERWATCH v5.0", page_icon="🛡️", layout="wide")

# TIMEZONE CONFIG (INDIA)
IST = pytz.timezone('Asia/Kolkata')

# --- 2. DATABASE CONNECTION ---
def connect_to_gsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
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
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        return gc.open_by_url(url)
    except Exception as e:
        st.error(f"🔐 AUTH ERROR: {e}")
        st.stop()

def get_or_create_worksheet(sh, name, headers):
    try:
        return sh.worksheet(name)
    except:
        ws = sh.add_worksheet(title=name, rows=1000, cols=12)
        ws.append_row(headers)
        return ws

# INITIALIZE SYSTEM
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    sh = connect_to_gsheet()
    worksheet_logs = get_or_create_worksheet(sh, "Logs", ["Date", "Time", "Type", "Sector", "Subject", "Activity", "Duration", "Output", "Rot", "Focus", "Notes"])
    worksheet_timetable = get_or_create_worksheet(sh, "Timetable", ["Day_Type", "Time_Slot", "Task"])
except Exception as e:
    st.error(f"💥 SYSTEM FAILURE: {e}")
    st.stop()

# --- 3. LOGIC ENGINE ---
def get_current_time():
    return datetime.now(IST)

def get_day_protocol():
    day_num = get_current_time().weekday()
    if day_num in [0, 2, 4]: return "MWS Protocol"
    elif day_num in [1, 3, 5]: return "TTS Protocol"
    else: return "Sunday Special"

def get_data():
    data_logs = worksheet_logs.get_all_records()
    data_time = worksheet_timetable.get_all_records()
    
    df_logs = pd.DataFrame(data_logs)
    df_timetable = pd.DataFrame(data_time)
    
    if not df_logs.empty:
        df_logs['Date'] = pd.to_datetime(df_logs['Date'], errors='coerce')
        for c in ['Duration', 'Output', 'Rot', 'Focus']:
            df_logs[c] = pd.to_numeric(df_logs[c], errors='coerce').fillna(0)
            
    return df_logs, df_timetable

def write_log(entry_data):
    row = list(entry_data.values())
    worksheet_logs.append_row(row)

def add_timetable_slot(day_type, time_slot, task):
    worksheet_timetable.append_row([day_type, time_slot, task])

def calculate_kpi(df):
    if df.empty: return 0, 0, 0
    today = get_current_time().normalize()
    # Fix timezone of dataframe dates if naive
    if df['Date'].dt.tz is None:
        # Assume naive dates are local
        pass 
    
    df_today = df[(df['Date'].dt.date == today.date()) & (df['Type'] == 'Metric')]
    
    if df_today.empty: return 0, 0, 0
    
    rot = int(df_today['Rot'].sum())
    efs = int(((df_today['Duration'] * (df_today['Focus']/100)) - (df_today['Rot'] * 1.5)).sum())
    hours = df_today['Duration'].sum() / 60
    velocity = round(df_today['Output'].sum() / hours, 2) if hours > 0 else 0
    return rot, efs, velocity

# --- 4. UI LAYOUT ---

# SIDEBAR (Status Only)
with st.sidebar:
    st.title("🛡️ OVERWATCH")
    current_now = get_current_time()
    protocol = get_day_protocol()
    
    st.markdown(f"**🕒 {current_now.strftime('%H:%M')} (IST)**")
    st.markdown(f"**📅 {current_now.strftime('%d %b %Y')}**")
    st.info(f"PROTOCOL: {protocol}")
    
    if protocol == "MWS Protocol": st.caption("Focus: Physics / Chemistry")
    elif protocol == "TTS Protocol": st.caption("Focus: Phy / Chem / Bio (NDA)")
    
    st.divider()
    st.markdown("[📝 Edit Sheet Manually](https://docs.google.com/spreadsheets)")

# MAIN DASHBOARD

# 1. LOAD DATA
try:
    df_logs, df_timetable = get_data()
    rot, efs, vel = calculate_kpi(df_logs)
except:
    df_logs, df_timetable = pd.DataFrame(), pd.DataFrame()
    rot, efs, vel = 0, 0, 0

# 2. KPI METRICS
k1, k2, k3 = st.columns(3)
k1.metric("ROT (WASTED)", f"{rot} min", delta="Limit: 60", delta_color="inverse")
k2.metric("EFS SCORE", f"{efs}", delta="Target: 480")
k3.metric("VELOCITY", f"{vel}", help="Output per Hour")

st.divider()

# 3. PRIME COMMAND CENTER (MAIN AREA)
st.subheader("🧠 PRIME COMMAND CENTER")

# The "Big Button" Analysis
if st.button("🚨 ANALYZE SITUATION & COMMAND ME", type="primary", use_container_width=True):
    with st.spinner("PRIME IS ANALYZING BIOMETRICS & LOGS..."):
        # Context Gathering
        current_time_str = get_current_time().strftime('%H:%M')
        stats_recent = df_logs.tail(5).to_string() if not df_logs.empty else "No Logs Today"
        
        # Find Current Scheduled Task
        current_task = "Unknown"
        if not df_timetable.empty:
            # Simple string match for protocol
            today_sched = df_timetable[df_timetable['Day_Type'].astype(str).str.contains(protocol.split()[0], case=False, na=False)]
            # In a real app, we'd parse time ranges. For now, we send the whole schedule to AI.
            sched_str = today_sched.to_string()
        else:
            sched_str = "No Timetable Found"

        prompt = f"""
        **SITUATION REPORT**
        - Time: {current_time_str} (IST)
        - Protocol: {protocol}
        - Today's Stats: Rot={rot}m, EFS={efs}, Velocity={vel}
        
        **RECENT LOGS:**
        {stats_recent}
        
        **SCHEDULE:**
        {sched_str}
        
        **YOUR ORDERS:**
        1. Compare Current Time ({current_time_str}) to Schedule. Is user on track?
        2. Analyze ROT. If > 20, roast them.
        3. Give ONE specific command on what to do RIGHT NOW.
        """
        
        try:
            chat = client.chat.completions.create(
                messages=[{"role": "system", "content": "You are PRIME. Ruthless. Military. Concise."}, 
                          {"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile"
            )
            st.success(chat.choices[0].message.content)
        except Exception as e:
            st.error(f"PRIME OFFLINE: {e}")

# Chat Bar
user_input = st.chat_input("Ask Prime specific questions...")
if user_input:
    with st.chat_message("user"):
        st.write(user_input)
    with st.chat_message("assistant"):
        # Simple chat logic (can be expanded)
        st.write("Processing...")
        # (You can copy the AI logic from above here if you want chat history)

# 4. TABS: LOGGING & TIMETABLE
tab_log, tab_schedule, tab_visuals = st.tabs(["📝 LOG DATA", "📅 TIMETABLE MANAGER", "📈 WAR ROOM"])

# --- TAB 1: LOGGING ---
with tab_log:
    with st.form("log_entry"):
        col1, col2 = st.columns(2)
        with col1:
            date_val = st.date_input("Date", value=get_current_time())
            subject = st.selectbox("Subject", ["Math", "Physics", "Chemistry", "Biology", "English", "GAT"])
            activity = st.selectbox("Activity", ["Deep Study", "Mock Test", "Revision", "Class"])
        with col2:
            duration = st.number_input("Duration (Min)", min_value=0, step=15)
            output = st.number_input("Output (Qty)", min_value=0)
            rot_input = st.number_input("Rot (Min)", min_value=0)
            focus = st.slider("Focus %", 0, 100, 80)
        
        notes = st.text_input("Notes")
        
        if st.form_submit_button("COMMIT LOG"):
            new_data = {
                "Date": date_val.strftime("%Y-%m-%d"),
                "Time": get_current_time().strftime("%H:%M:%S"),
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
            write_log(new_data)
            st.success("SYNCED.")
            st.rerun()

# --- TAB 2: TIMETABLE MANAGER ---
with tab_schedule:
    st.subheader("Current Protocol Orders")
    
    # 1. View Current Schedule
    if not df_timetable.empty:
        # Filter for today
        filter_mask = df_timetable['Day_Type'].astype(str).str.contains(protocol.split()[0], case=False, na=False)
        today_view = df_timetable[filter_mask]
        if not today_view.empty:
            st.dataframe(today_view, use_container_width=True, hide_index=True)
        else:
            st.info(f"No slots found for {protocol}.")
            st.dataframe(df_timetable) # Show all if none for today
    else:
        st.warning("Timetable Empty.")

    st.divider()
    
    # 2. Add New Slot Form
    st.markdown("#### ➕ Add New Command Slot")
    with st.form("add_slot"):
        c1, c2, c3 = st.columns(3)
        with c1:
            # Dropdown to select MWS or TTS
            day_select = st.selectbox("Protocol Day", ["MWS (Mon/Wed/Fri)", "TTS (Tue/Thu/Sat)", "Sunday"])
        with c2:
            time_select = st.text_input("Time Slot (e.g. 06:00 - 08:00)")
        with c3:
            task_select = st.text_input("Task (e.g. Physics - Optics)")
            
        if st.form_submit_button("ADD SLOT"):
            # Map selection to simple code
            if "MWS" in day_select: d_code = "MWS"
            elif "TTS" in day_select: d_code = "TTS"
            else: d_code = "Sunday"
            
            add_timetable_slot(d_code, time_select, task_select)
            st.success(f"Added {task_select} to {d_code}")
            st.rerun()

# --- TAB 3: VISUALS ---
with tab_visuals:
    if not df_logs.empty:
        today = pd.Timestamp.now().normalize()
        # Fix date comparison
        df_logs['Date_Only'] = pd.to_datetime(df_logs['Date']).dt.date
        today_data = df_logs[df_logs['Date_Only'] == get_current_time().date()]
        
        if not today_data.empty:
            st.bar_chart(today_data, x="Subject", y="Duration", color="Activity")
            st.dataframe(today_data[['Subject', 'Duration', 'Output', 'Rot']], use_container_width=True)
        else:
            st.info("No data for today.")
        
