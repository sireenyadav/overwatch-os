import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from groq import Groq
from datetime import datetime

# --- 1. SYSTEM CONFIG ---
st.set_page_config(page_title="OVERWATCH v4", page_icon="🛡️", layout="wide")

# Initialize Connections
# We use try/except to handle setup errors gracefully
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error(f"⚠️ CONNECTIVITY ERROR: {e}")
    st.info("Did you add the Google Service Account JSON to Streamlit Secrets?")
    st.stop()

# --- 2. LOGIC ENGINE ---
def get_day_protocol():
    """Auto-detects MWS or TTS based on today's weekday."""
    day_num = datetime.now().weekday() # 0=Mon, 6=Sun
    
    # MWS: Mon(0), Wed(2), Fri(4)
    if day_num in [0, 2, 4]:
        return "MWS Protocol"
    # TTS: Tue(1), Thu(3), Sat(5)
    elif day_num in [1, 3, 5]:
        return "TTS Protocol"
    else:
        return "Sunday Special"

def get_data():
    # Load Sheets with 0 caching (Real-time)
    # Ensure you replace the URL below if your sheet name isn't found automatically
    df_logs = conn.read(worksheet="Logs", ttl=0)
    df_timetable = conn.read(worksheet="Timetable", ttl=0)
    
    # Cleanup Dates
    df_logs['Date'] = pd.to_datetime(df_logs['Date'], errors='coerce')
    return df_logs, df_timetable

def write_log(entry_data):
    df_logs = conn.read(worksheet="Logs", ttl=0)
    entry_df = pd.DataFrame([entry_data])
    updated_df = pd.concat([df_logs, entry_df], ignore_index=True)
    conn.update(worksheet="Logs", data=updated_df)

def calculate_kpi(df):
    if df.empty: return 0, 0, 0
    today = pd.Timestamp.now().normalize()
    # Filter for Metric logs only
    df_today = df[(df['Date'].dt.normalize() == today) & (df['Type'] == 'Metric')]
    
    if df_today.empty: return 0, 0, 0
    
    rot = int(df_today['Rot'].sum())
    # EFS Formula: (Duration * Focus) - (Rot * 1.5)
    efs = int(((df_today['Duration'] * (df_today['Focus']/100)) - (df_today['Rot'] * 1.5)).sum())
    
    # Velocity: Output / Hours
    hours = df_today['Duration'].sum() / 60
    velocity = round(df_today['Output'].sum() / hours, 2) if hours > 0 else 0
    
    return rot, efs, velocity

# --- 3. UI LAYOUT ---

# SIDEBAR: COMMAND CENTER
with st.sidebar:
    st.title("🛡️ OVERWATCH")
    protocol = get_day_protocol()
    
    # Status Indicators
    st.caption(f"STATUS: ONLINE | {protocol.upper()}")
    if protocol == "MWS Protocol":
        st.info("📅 FOCUS: Physics / Chemistry")
    elif protocol == "TTS Protocol":
        st.info("📅 FOCUS: Phy / Chem / Bio (NDA)")
    else:
        st.success("📅 SUNDAY: Revision / Mock / Backlog")

    st.divider()
    
    # PRIME AI (Always Available)
    st.header("🧠 PRIME UPLINK")
    user_query = st.text_input("Consult Prime...", placeholder="Am I efficient today?")
    
    if user_query:
        df_logs, df_time = get_data()
        today_str = datetime.now().strftime('%Y-%m-%d')
        stats = df_logs.tail(5).to_string()
        
        prompt = f"""
        User Query: {user_query}
        Date: {today_str} ({protocol})
        Recent Logs:
        {stats}
        
        You are PRIME. Military tone. Concise.
        User Schedule: MWS (Phy/Chem), TTS (NDA Bio), Sun (Flex).
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
    # Link to your actual sheet for edits
    st.markdown("[📝 Edit/Undo in Google Sheets](https://docs.google.com/spreadsheets)") 

# MAIN DASHBOARD

# 1. LIVE HUD
try:
    df_logs, df_timetable = get_data()
    rot, efs, vel = calculate_kpi(df_logs)
except:
    st.warning("Database Connection Initializing...")
    df_logs = pd.DataFrame()
    rot, efs, vel = 0, 0, 0

k1, k2, k3 = st.columns(3)
k1.metric("ROT (WASTED)", f"{rot} min", delta="Limit: 60", delta_color="inverse")
k2.metric("EFS SCORE", f"{efs}", delta="Target: 480")
k3.metric("VELOCITY", f"{vel}", help="Output per Hour")

# 2. LOGGING (Hidden in Expander to save screen space)
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
                "Sector": protocol, # Auto-fills MWS or TTS
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

# 3. WAR ROOM (Visuals)
st.subheader("Situation Report")

if not df_logs.empty:
    tab_day, tab_week = st.tabs(["TODAY", "WEEK"])
    
    with tab_day:
        today = pd.Timestamp.now().normalize()
        today_data = df_logs[df_logs['Date'].dt.normalize() == today]
        
        if not today_data.empty:
            # Bar Chart: Duration by Subject
            st.bar_chart(today_data, x="Subject", y="Duration", color="Activity")
            # Text List
            st.dataframe(today_data[['Subject', 'Duration', 'Output', 'Rot', 'Notes']], use_container_width=True)
        else:
            st.info("Awaiting today's data.")

    with tab_week:
        # Trend Line
        st.line_chart(df_logs, x="Date", y="Duration", color="Subject")

# 4. TIMETABLE CHECK
st.subheader(f"📅 Protocol: {protocol}")
if not df_timetable.empty:
    # Filter for today's protocol (Day_Type matches 'MWS' or 'TTS')
    # Use string matching (contains) to be safe
    today_schedule = df_timetable[df_timetable['Day_Type'].str.contains(protocol.split()[0], case=False, na=False)]
    
    if not today_schedule.empty:
        st.dataframe(today_schedule[['Time_Slot', 'Task']], use_container_width=True, hide_index=True)
    else:
        st.caption("No specific schedule found for today in Sheets.")
        st.dataframe(df_timetable) # Show all if filter fails
else:
    st.info("Timetable empty. Update in Google Sheets.")
        
