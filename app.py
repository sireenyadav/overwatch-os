import streamlit as st
import pandas as pd
import plotly.express as px
from groq import Groq
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SYSTEM CONFIG ---
st.set_page_config(page_title="OVERWATCH v7.0", page_icon="🛡️", layout="wide")

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
    worksheet_config = get_or_create_worksheet(sh, "Config", ["Category", "Item"])
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

def get_subjects():
    # Fetch subjects from Config sheet + Defaults
    data = worksheet_config.get_all_records()
    df = pd.DataFrame(data)
    
    defaults = ["Math", "Physics", "Chemistry", "Biology", "English", "GAT", "Python", "Chess"]
    
    if not df.empty and 'Category' in df.columns:
        # Get items where Category is 'Subject'
        custom_subs = df[df['Category'] == 'Subject']['Item'].tolist()
        final_list = sorted(list(set(defaults + custom_subs)))
    else:
        final_list = sorted(defaults)
        
    return final_list

def add_new_subject(new_sub):
    worksheet_config.append_row(["Subject", new_sub])

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
    if df['Date'].dt.tz is None: pass 
    
    df_today = df[(df['Date'].dt.date == today.date()) & (df['Type'] == 'Metric')]
    
    if df_today.empty: return 0, 0, 0
    
    rot = int(df_today['Rot'].sum())
    efs = int(((df_today['Duration'] * (df_today['Focus']/100)) - (df_today['Rot'] * 1.5)).sum())
    hours = df_today['Duration'].sum() / 60
    velocity = round(df_today['Output'].sum() / hours, 2) if hours > 0 else 0
    return rot, efs, velocity

# --- 4. UI LAYOUT ---

# INITIALIZE CHAT MEMORY (The "Brain")
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- TOP BAR HUD ---
current_now = get_current_time()
protocol = get_day_protocol()
date_str = current_now.strftime('%d %B %Y')
time_str = current_now.strftime('%H:%M IST')

st.markdown(f"""
    <style>
    .hud-container {{
        display: flex;
        justify-content: space-between;
        background-color: #0E1117;
        padding: 15px;
        border-bottom: 2px solid #FF4B4B;
        margin-bottom: 20px;
        align-items: center;
    }}
    .hud-time {{ font-size: 20px; font-weight: bold; color: #FF4B4B; font-family: monospace; }}
    .hud-protocol {{ font-size: 14px; color: #00FF00; letter-spacing: 1px; }}
    </style>
    <div class="hud-container">
        <div style="font-size: 24px; font-weight: bold;">🛡️ OVERWATCH OS</div>
        <div style="text-align: right;">
            <div class="hud-time">{time_str}</div>
            <div>{date_str}</div>
            <div class="hud-protocol">STATUS: {protocol.upper()}</div>
        </div>
    </div>
""", unsafe_allow_html=True)


# --- DASHBOARD LOGIC ---
try:
    df_logs, df_timetable = get_data()
    rot, efs, vel = calculate_kpi(df_logs)
    subject_list = get_subjects() 
except:
    df_logs, df_timetable = pd.DataFrame(), pd.DataFrame()
    rot, efs, vel = 0, 0, 0
    subject_list = ["Math", "Physics", "Chemistry"]

# KPI Metrics
k1, k2, k3 = st.columns(3)
k1.metric("ROT (WASTED)", f"{rot} min", delta="Limit: 60", delta_color="inverse")
k2.metric("EFS SCORE", f"{efs}", delta="Target: 480")
k3.metric("VELOCITY", f"{vel}", help="Output per Hour")

# TABS
tab_log, tab_schedule, tab_visuals = st.tabs(["📝 LOG DATA", "📅 TIMETABLE", "📈 WAR ROOM"])

# TAB 1: LOGGING & SUBJECTS
with tab_log:
    # ➕ ADD SUBJECT FEATURE
    with st.expander("⚙️ Manage Subjects (Add New)"):
        st.caption("Add a subject here. It will be saved to the database forever.")
        c_sub1, c_sub2 = st.columns([3, 1])
        with c_sub1:
            new_sub_input = st.text_input("New Subject Name", label_visibility="collapsed", placeholder="e.g. History")
        with c_sub2:
            if st.button("Add Subject", type="secondary"):
                if new_sub_input and new_sub_input not in subject_list:
                    add_new_subject(new_sub_input)
                    st.success(f"Added {new_sub_input}!")
                    st.rerun()
                elif new_sub_input in subject_list:
                    st.warning("Exists.")

    st.divider()

    with st.form("log_entry"):
        col1, col2 = st.columns(2)
        with col1:
            date_val = st.date_input("Date", value=current_now)
            # The list now updates dynamically
            subject = st.selectbox("Subject", subject_list)
            activity = st.selectbox("Activity", ["Deep Study", "Mock Test", "Revision", "Class"])
        with col2:
            duration = st.number_input("Duration (Min)", min_value=0, step=15)
            output = st.number_input("Output (Qty)", min_value=0)
            rot_input = st.number_input("Rot (Min)", min_value=0)
            focus = st.slider("Focus %", 0, 100, 80)
        
        notes = st.text_input("Notes")
        
        if st.form_submit_button("COMMIT LOG", type="primary"):
            new_data = {
                "Date": date_val.strftime("%Y-%m-%d"),
                "Time": current_now.strftime("%H:%M:%S"),
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

# TAB 2: TIMETABLE
with tab_schedule:
    st.subheader("Current Protocol Orders")
    if not df_timetable.empty:
        # Filter for today's protocol
        filter_mask = df_timetable['Day_Type'].astype(str).str.contains(protocol.split()[0], case=False, na=False)
        today_view = df_timetable[filter_mask]
        
        # Prepare context string for AI later
        schedule_context = today_view.to_string() if not today_view.empty else "No schedule found for today."
        
        if not today_view.empty:
            st.dataframe(today_view, use_container_width=True, hide_index=True)
        else:
            st.info(f"No specific orders for {protocol}.")
            st.dataframe(df_timetable) 
    else:
        st.warning("Timetable Empty.")
        schedule_context = "Timetable is completely empty."

    st.divider()
    st.markdown("#### ➕ Add Command Slot")
    with st.form("add_slot"):
        c1, c2, c3 = st.columns(3)
        with c1:
            day_select = st.selectbox("Protocol Day", ["MWS (Mon/Wed/Fri)", "TTS (Tue/Thu/Sat)", "Sunday"])
        with c2:
            time_select = st.text_input("Time", placeholder="06:00 - 08:00")
        with c3:
            task_select = st.text_input("Task", placeholder="Physics - Optics")
        if st.form_submit_button("ADD SLOT"):
            if "MWS" in day_select: d_code = "MWS"
            elif "TTS" in day_select: d_code = "TTS"
            else: d_code = "Sunday"
            add_timetable_slot(d_code, time_select, task_select)
            st.success(f"Added to {d_code}")
            st.rerun()

# TAB 3: VISUALS
with tab_visuals:
    if not df_logs.empty:
        today = pd.Timestamp.now().normalize()
        df_logs['Date_Only'] = pd.to_datetime(df_logs['Date']).dt.date
        today_data = df_logs[df_logs['Date_Only'] == current_now.date()]
        if not today_data.empty:
            st.bar_chart(today_data, x="Subject", y="Duration", color="Activity")
            st.dataframe(today_data[['Subject', 'Duration', 'Output', 'Rot']], use_container_width=True)
        else:
            st.info("No data for today.")

# --- 5. PRIME CHAT INTERFACE (THE CORTEX) ---
st.divider()
st.subheader("💬 PRIME UPLINK (PERSONAL AI)")

# 1. Display Chat History (So it doesn't disappear)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 2. The Input Box
if prompt := st.chat_input("Ask Prime (e.g., 'Am I on track?' or 'Explain Calculus')"):
    
    # Show User Message immediately
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 3. Generate Response with FULL CONTEXT
    with st.chat_message("assistant"):
        with st.spinner("Accessing Neural Network..."):
            
            # Prepare the Data Context
            stats_recent = df_logs.tail(5).to_string() if not df_logs.empty else "No Data Logs yet."
            
            # This is the "God Prompt" - It gives the AI everything about you
            system_instruction = f"""
            You are PRIME, a dedicated AI military tactical advisor for this student.
            
            **CURRENT BIOMETRICS:**
            - Date/Time: {date_str} {time_str}
            - Protocol Phase: {protocol}
            - Today's Performance: ROT (Wasted)={rot}m, EFS={efs}, Velocity={vel}
            
            **RECENT LOGS (Last 5):**
            {stats_recent}
            
            **INSTRUCTIONS:**
            1. If the user asks about their progress, analyze the logs above.
            2. If the user asks a general question (Math, Physics, Life), answer it accurately like a tutor.
            3. Always maintain a concise, "tough love" military tone. Do not be soft.
            """
            
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    model="llama-3.3-70b-versatile"
                )
                response = chat_completion.choices[0].message.content
                
                # Show Response
                st.markdown(response)
                
                # Save Response to History
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                st.error(f"PRIME OFFLINE: {e}")
    
