import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime, timedelta
from groq import Groq
import io

# --- 1. SYSTEM CONFIGURATION & CONSTANTS ---
st.set_page_config(
    page_title="OVERWATCH // ENTERPRISE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Corporate Styling
st.markdown("""
<style>
    .reportview-container { background: #0e1117; }
    .big-font { font-size:20px !important; font-weight: bold; }
    .stMetric { background-color: #262730; padding: 10px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ORCHESTRATOR (CLASS) ---
class DataManager:
    def __init__(self):
        # Default State Structure
        if 'db' not in st.session_state:
            st.session_state.db = {
                "logs": [],        # Metrics & Anomalies
                "subjects": ["Math", "Physics", "Chemistry", "English", "GAT", "Current Affairs"],
                "timetable": [],   # [{"time": "06:00", "task": "Math"}]
                "profile": {"name": "Cadet", "efs_target": 8, "rot_limit": 60}
            }

    def get_logs_df(self):
        if not st.session_state.db['logs']:
            return pd.DataFrame(columns=["Date", "Type", "Sector", "Subject", "Activity", "Duration", "Output", "Rot", "Focus", "Notes"])
        
        df = pd.DataFrame(st.session_state.db['logs'])
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df

    def add_log(self, entry):
        st.session_state.db['logs'].append(entry)

    def add_subject(self, new_subject):
        if new_subject not in st.session_state.db['subjects']:
            st.session_state.db['subjects'].append(new_subject)

    def update_timetable(self, timetable_data):
        st.session_state.db['timetable'] = timetable_data

    def export_data(self):
        return json.dumps(st.session_state.db, indent=4)

    def import_data(self, uploaded_file):
        try:
            data = json.load(uploaded_file)
            # Validate schema roughly
            if "logs" in data:
                st.session_state.db = data
                return True
            return False
        except Exception as e:
            return False

# --- 3. ANALYTICS ENGINE (CLASS) ---
class AnalyticsEngine:
    @staticmethod
    def calculate_daily_metrics(df):
        if df.empty: return 0, 0, 0, 0
        
        today = pd.Timestamp.now().normalize()
        # Filter for METRICS only, not Anomalies
        df_today = df[(df['Date'].dt.normalize() == today) & (df['Type'] == 'Metric')].copy()
        
        if df_today.empty: return 0, 0, 0, 0

        # Calculations
        total_rot = df_today['Rot'].sum()
        
        # EFS = (Duration * Focus%) - (Rot * 1.5)
        df_today['EFS_Calc'] = (df_today['Duration'] * (df_today['Focus'] / 100)) - (df_today['Rot'] * 1.5)
        daily_efs = int(df_today['EFS_Calc'].sum())
        
        total_hours = df_today['Duration'].sum() / 60
        velocity = round(df_today['Output'].sum() / total_hours, 2) if total_hours > 0 else 0
        
        return total_rot, daily_efs, velocity, total_hours

    @staticmethod
    def get_subject_distribution(df):
        if df.empty: return pd.DataFrame()
        df_metrics = df[df['Type'] == 'Metric']
        return df_metrics.groupby("Subject")["Duration"].sum().reset_index()

# --- 4. PRIME INTELLIGENCE (CLASS) ---
class PrimeAI:
    def __init__(self):
        if "GROQ_API_KEY" in st.secrets:
            self.client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            self.enabled = True
        else:
            self.enabled = False

    def consult(self, mode, data_context, timetable=None):
        if not self.enabled:
            return "SYSTEM ERROR: API KEY NOT FOUND. DEPLOY SECRETS."

        system_prompt = """
        You are PRIME. A ruthless, corporate-grade performance AI.
        Your goal is maximum efficiency for an NDA Cadet.
        Tone: Military, Precise, Analytical. No sympathy for laziness.
        1. Contextualize 'Anomalies' (Sickness/Family) as legitimate constraints.
        2. Treat 'Rot' (distraction) without anomaly as a violation of duty.
        3. Compare actions against the Timetable if provided.
        """

        prompts = {
            "MORNING": f"Review yesterday's logs and today's Timetable: {timetable}. Previous Data: {data_context}. Generate a tactical plan.",
            "INTERVENTION": f"User logged High Rot. Data: {data_context}. Roast them. Demand a penalty.",
            "WEEKLY": f"Analyze the last 7 days. Identify the weakest subject and efficiency trends. Data: {data_context}"
        }

        try:
            completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompts.get(mode, "Analyze this.")}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.6,
                max_tokens=400
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"PRIME OFFLINE: {str(e)}"

# --- 5. INITIALIZATION ---
data_manager = DataManager()
analytics = AnalyticsEngine()
prime = PrimeAI()

# --- 6. UI LAYOUT ---

# SIDEBAR: PERSISTENCE & CONFIG
with st.sidebar:
    st.title("🛡️ OVERWATCH OS")
    st.caption("v3.0 ENTERPRISE")
    
    # 1. Memory Core
    st.header("💾 Memory Core")
    uploaded_file = st.file_uploader("Inject JSON", type="json")
    if uploaded_file and st.button("Load Data"):
        if data_manager.import_data(uploaded_file):
            st.success("System Restored.")
            st.rerun()
        else:
            st.error("Corrupt File.")
            
    # Download
    json_data = data_manager.export_data()
    st.download_button("⬇️ Extract Data (Save)", json_data, f"overwatch_backup_{datetime.now().strftime('%Y%m%d')}.json", "application/json")
    
    st.divider()
    
    # 2. Dynamic Configuration
    with st.expander("⚙️ System Config"):
        st.write("Manage Subjects")
        new_sub = st.text_input("Add Subject")
        if st.button("Add"):
            data_manager.add_subject(new_sub)
            st.success(f"Added {new_sub}")
            st.rerun()
            
        st.write("Target Settings")
        st.session_state.db['profile']['efs_target'] = st.number_input("Target EFS", value=st.session_state.db['profile']['efs_target'])

# MAIN TABS
tab_tactical, tab_strategic, tab_ops, tab_schedule = st.tabs(["📊 TACTICAL DASHBOARD", "📈 STRATEGIC WAR ROOM", "📝 OPS LOGGING", "📅 TIMETABLE"])

# --- TAB 1: TACTICAL (TODAY) ---
with tab_tactical:
    df = data_manager.get_logs_df()
    rot, efs, vel, hours = analytics.calculate_daily_metrics(df)
    
    # KPI ROW
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ROT (WASTED)", f"{rot} min", delta="Limit: 60", delta_color="inverse")
    col2.metric("EFS SCORE", f"{efs}", delta=f"Target: {st.session_state.db['profile']['efs_target']*60}")
    col3.metric("VELOCITY", f"{vel}", help="Output per Hour")
    col4.metric("ACTIVE HOURS", f"{round(hours, 2)}")
    
    # WARNING SYSTEM
    if rot > st.session_state.db['profile']['rot_limit']:
        st.error(f"🚨 ROT LIMIT BREACHED. INITIATE PENALTY PROTOCOL.")
        
    # PRIME INTERFACE
    st.subheader("🗣️ Prime Directive")
    if st.button("REQUEST MORNING BRIEFING"):
        with st.spinner("Prime is analyzing schedule and history..."):
            # Get last 5 logs + Timetable
            history = df.tail(5).to_dict() if not df.empty else "No Data"
            timetable = st.session_state.db['timetable']
            response = prime.consult("MORNING", str(history), str(timetable))
            st.info(response)

    # TODAY'S FEED
    st.subheader("Today's Operations")
    if not df.empty:
        today = pd.Timestamp.now().normalize()
        df_today = df[df['Date'].dt.normalize() == today]
        if not df_today.empty:
            # Color code types
            st.dataframe(df_today[['Type', 'Subject', 'Duration', 'Rot', 'Notes']], use_container_width=True)
        else:
            st.caption("No operations logged today.")

# --- TAB 2: STRATEGIC (TRENDS) ---
with tab_strategic:
    df = data_manager.get_logs_df()
    if not df.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🕸️ Subject Radar (Balance)")
            radar_df = analytics.get_subject_distribution(df)
            if not radar_df.empty:
                fig = px.line_polar(radar_df, r='Duration', theta='Subject', line_close=True, template="plotly_dark")
                fig.update_traces(fill='toself')
                st.plotly_chart(fig, use_container_width=True)
                
        with col2:
            st.markdown("### 📉 Rot vs Efficiency")
            # Filter metrics
            df_metrics = df[df['Type'] == 'Metric']
            if not df_metrics.empty:
                fig2 = px.scatter(df_metrics, x="Duration", y="Output", color="Subject", size="Focus", title="Output Efficiency Bubble")
                st.plotly_chart(fig2, use_container_width=True)
                
        st.markdown("### 🧬 Anomaly History (Context)")
        df_anomalies = df[df['Type'] == 'Anomaly']
        if not df_anomalies.empty:
            st.dataframe(df_anomalies[['Date', 'Notes']], use_container_width=True)
    else:
        st.info("Insufficient data for strategic analysis.")

# --- TAB 3: OPS LOGGING (INPUT) ---
with tab_ops:
    st.subheader("📝 Operation Entry")
    
    entry_mode = st.radio("Log Type", ["Standard Protocol (Study)", "Anomaly (Life Event)"], horizontal=True)
    
    with st.form("logging_form"):
        date = st.date_input("Date")
        
        if entry_mode == "Standard Protocol (Study)":
            col1, col2 = st.columns(2)
            with col1:
                sector = st.selectbox("Sector", ["NDA (Speed)", "BOARDS (Depth)", "SKILL"])
                # Dynamic Subjects from DB
                subject = st.selectbox("Subject", st.session_state.db['subjects'])
                activity = st.selectbox("Activity", ["Deep Work", "Mock Test", "Revision", "Class"])
            with col2:
                duration = st.number_input("Duration (Mins)", min_value=0, step=15)
                output = st.number_input("Output (Qty)", min_value=0)
                rot = st.number_input("Rot (Mins Wasted)", min_value=0)
                focus = st.slider("Focus Quality", 0, 100, 80)
            
            notes = st.text_input("Debrief Notes")
            type_tag = "Metric"
            
        else:
            st.warning("Log external factors affecting performance (Sickness, Fights, Travel).")
            notes = st.text_area("Situation Report")
            # Defaults
            sector, subject, activity = "LIFE", "CONTEXT", "ANOMALY"
            duration, output, rot, focus = 0, 0, 0, 0
            type_tag = "Anomaly"
            
        if st.form_submit_button("COMMIT TO DATABASE"):
            entry = {
                "Date": str(date), "Type": type_tag, "Sector": sector,
                "Subject": subject, "Activity": activity, "Duration": duration,
                "Output": output, "Rot": rot, "Focus": focus, "Notes": notes
            }
            data_manager.add_log(entry)
            st.success("Entry Logged.")
            
            # Auto-Trigger Prime on High Rot
            if rot > 20 and type_tag == "Metric":
                alert = prime.consult("INTERVENTION", f"Rot: {rot}, Subject: {subject}")
                st.error(alert)

# --- TAB 4: TIMETABLE MANAGER ---
with tab_schedule:
    st.subheader("📅 Standard Operating Procedure (Timetable)")
    
    # View Current
    current_schedule = st.session_state.db.get('timetable', [])
    if current_schedule:
        st.table(pd.DataFrame(current_schedule))
    else:
        st.info("No timetable defined.")
        
    st.divider()
    st.write("Add Time Slot")
    c1, c2, c3 = st.columns(3)
    t_start = c1.time_input("Start Time")
    t_end = c2.time_input("End Time")
    t_task = c3.selectbox("Task", st.session_state.db['subjects'] + ["Break", "Physical Training"])
    
    if st.button("Add Slot"):
        slot = {
            "Start": str(t_start),
            "End": str(t_end),
            "Task": t_task
        }
        # Append to existing
        current = st.session_state.db.get('timetable', [])
        current.append(slot)
        data_manager.update_timetable(current)
        st.success("Slot Added.")
        st.rerun()
        
    if st.button("Clear Timetable"):
        data_manager.update_timetable([])
        st.rerun()
