import streamlit as st
import pandas as pd
import plotly.express as px
import time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import datetime
from datetime import timedelta
import hashlib

# Setup page configuration
st.set_page_config(
    page_title="NFC Access Hub",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        font-weight: 500;
        color: #6B7280;
    }
    .card {
        padding: 1.5rem;
        border-radius: 0.5rem;
        background-color: white;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        margin-bottom: 1rem;
    }
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 0.5rem;
    }
    .status-online {
        background-color: #10B981;
    }
    .status-offline {
        background-color: #EF4444;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Firebase
@st.cache_resource
def initialize_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(
            r"C:\Users\aswin\Stocky\app\app\nfc-based-lock-system-firebase-adminsdk-fbsvc-e5d1b46fff.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://nfc-based-lock-system-default-rtdb.firebaseio.com/'
        })
    return True


initialize_firebase()


# Helper function to hash UID
def hash_uid(uid):
    return hashlib.md5(uid.encode()).hexdigest()


# Helper function to update user in Firebase
def update_user(uid, user_data):
    try:
        hashed_uid = hash_uid(uid)
        user_ref = db.reference(f'AuthorizedUsers/{hashed_uid}')
        user_ref.update(user_data)
        return True
    except Exception as e:
        st.error(f"Error updating user: {e}")
        return False


# Helper function to add user
def add_user(uid, user_data):
    try:
        hashed_uid = hash_uid(uid)
        user_ref = db.reference(f'AuthorizedUsers/{hashed_uid}')
        user_ref.set(user_data)
        return True
    except Exception as e:
        st.error(f"Error adding user: {e}")
        return False


# Toast/notification function
def show_toast(title, message, type="info"):
    if type == "info":
        st.info(f"**{title}** - {message}")
    elif type == "success":
        st.success(f"**{title}** - {message}")
    elif type == "warning":
        st.warning(f"**{title}** - {message}")
    elif type == "error":
        st.error(f"**{title}** - {message}")


# Show welcome toast
if 'shown_welcome' not in st.session_state:
    show_toast("Welcome to NFC Access Hub!", "Explore the dashboard to manage and monitor your NFC access system.")
    st.session_state.shown_welcome = True

# Sidebar navigation
st.sidebar.title("NFC Access Hub")
st.sidebar.caption("Manage your NFC access system")

nav_items = [
    "Real-time Status",
    "Live Access Logs",
    "Remote Control",
    "User Management",
    "Anomaly Detection"
]

nav_icons = {
    "Real-time Status": "🏠",
    "Live Access Logs": "📋",
    "Remote Control": "⚙️",
    "User Management": "👤",
    "Anomaly Detection": "🛡️"
}

selected_nav = st.sidebar.radio("", nav_items, format_func=lambda x: f"{nav_icons[x]} {x}")
st.sidebar.markdown("---")
st.sidebar.caption("Firebase Studio")


# Fetch data functions
def get_access_logs():
    logs_ref = db.reference('AccessLogs')
    logs = logs_ref.get()
    if logs:
        logs_list = []
        for key, value in logs.items():
            value['id'] = key
            logs_list.append(value)
        df = pd.DataFrame(logs_list)
        if 'Timestamp' in df.columns:
            try:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'].str.replace('_', ' '),
                                                 format='%Y-%m-%d %H-%M-%S',
                                                 errors='coerce')
                df['Timestamp'].fillna(pd.Timestamp.now(), inplace=True)
            except Exception as e:
                st.error(f"Error processing timestamps: {e}")
        df = df.sort_values('Timestamp', ascending=False)
        return df
    return pd.DataFrame()


def get_system_status():
    status_ref = db.reference('SystemStatus')
    status = status_ref.get()
    if not status:
        status = {
            'LockStatus': 'Unknown',
            'Online': False,
            'LastAccess': {
                'UID': 'None',
                'Timestamp': datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            }
        }
    return status


def get_users():
    users_ref = db.reference('AuthorizedUsers')
    users = users_ref.get()
    if users:
        users_list = []
        for uid, details in users.items():
            if isinstance(details, dict):
                details['HashedUID'] = uid
                users_list.append(details)
            else:
                users_list.append({
                    'HashedUID': uid,
                    'Name': 'Unknown',
                    'OriginalUID': uid
                })
        return pd.DataFrame(users_list)
    return pd.DataFrame()


# Component: Real-time Status
def real_time_status_component():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])

    with col1:
        status = get_system_status()
        lock_status = status.get('LockStatus', 'Unknown')
        online_status = status.get('Online', False)

        st.markdown(f"""
        <h3>System Status</h3>
        <p>
            <span class="status-indicator {'status-online' if lock_status == 'Locked' else 'status-offline'}"></span>
            <strong>Lock:</strong> {lock_status}
        </p>
        <p>
            <span class="status-indicator {'status-online' if online_status else 'status-offline'}"></span>
            <strong>Connection:</strong> {'Online' if online_status else 'Offline'}
        </p>
        """, unsafe_allow_html=True)

        last_access = status.get('LastAccess', {})
        st.markdown("### Last Access")
        if last_access:
            timestamp = last_access.get('Timestamp', 'Unknown')
            if '_' in str(timestamp):
                timestamp = str(timestamp).replace('_', ' ')
            st.markdown(f"""
            <p><strong>UID:</strong> {last_access.get('UID', 'Unknown')}</p>
            <p><strong>Time:</strong> {timestamp}</p>
            <p><strong>Status:</strong> {last_access.get('Status', 'Unknown')}</p>
            """, unsafe_allow_html=True)

    with col2:
        logs_df = get_access_logs()
        if not logs_df.empty:
            if 'Timestamp' in logs_df.columns:
                now = pd.Timestamp.now()
                logs_24h = logs_df[logs_df['Timestamp'] > (now - pd.Timedelta(days=1))]
                if not logs_24h.empty:
                    logs_24h['hour'] = logs_24h['Timestamp'].dt.hour
                    hourly_counts = logs_24h.groupby(['hour', 'Status']).size().reset_index(name='count')
                    fig = px.bar(hourly_counts, x='hour', y='count', color='Status',
                                 labels={'hour': 'Hour of Day', 'count': 'Number of Access Attempts'},
                                 title='Access Activity (Last 24 Hours)')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No access activity in the last 24 hours")
        else:
            st.info("No access data available")

    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Data"):
        st.rerun()


# Component: Live Access Logs
def live_access_logs_component():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_date = st.date_input("Filter by Date", value=datetime.datetime.now())
    with col2:
        status_options = ["All", "LOCKED", "UNLOCKED", "UNAUTHORIZED", "REGISTERED"]
        filter_status = st.selectbox("Filter by Status", status_options)
    with col3:
        refresh = st.button("🔄 Refresh Logs")

    logs_df = get_access_logs()
    if not logs_df.empty:
        if 'Timestamp' in logs_df.columns:
            logs_df['date'] = logs_df['Timestamp'].dt.date
            filtered_df = logs_df[logs_df['date'] == filter_date]
            if filter_status != "All":
                filtered_df = filtered_df[filtered_df['Status'] == filter_status]
            if not filtered_df.empty:
                st.write(f"Showing {len(filtered_df)} records")
                display_df = filtered_df[['UID', 'Status', 'Timestamp']].copy()
                st.dataframe(display_df, use_container_width=True)
                csv = filtered_df.to_csv(index=False)
                st.download_button(label="Download CSV", data=csv,
                                   file_name=f"access_logs_{filter_date}.csv", mime="text/csv")
            else:
                st.info("No records found matching your filters")
        else:
            st.warning("Timestamp data not available in logs")
    else:
        st.info("No access logs available")
    st.markdown("</div>", unsafe_allow_html=True)


# Component: Remote Control
def remote_control_component():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Door Control")
        lock_cols = st.columns(2)
        with lock_cols[0]:
            if st.button("🔒 Lock Door", use_container_width=True):
                command_ref = db.reference('Commands')
                command_ref.set({'action': 'lock',
                                 'timestamp': datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')})
                show_toast("Command Sent", "Lock command sent successfully", "success")
        with lock_cols[1]:
            if st.button("🔓 Unlock Door", use_container_width=True):
                command_ref = db.reference('Commands')
                command_ref.set({'action': 'unlock',
                                 'timestamp': datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')})
                show_toast("Command Sent", "Unlock command sent successfully", "success")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Restart System", use_container_width=True):
            command_ref = db.reference('Commands')
            command_ref.set({'action': 'restart',
                             'timestamp': datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')})
            show_toast("Command Sent", "Restart command sent successfully", "success")

        if st.button("📝 Enable Registration Mode", use_container_width=True):
            command_ref = db.reference('Commands')
            command_ref.set({'action': 'register_mode',
                             'timestamp': datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')})
            show_toast("Command Sent", "Registration mode activated", "success")

    with col2:
        st.subheader("System Settings")
        lock_timeout = st.slider("Auto-Lock Timeout (seconds)", min_value=1, max_value=60, value=5)
        if st.button("Save Settings", use_container_width=True):
            settings_ref = db.reference('Settings')
            settings_ref.update({'lock_timeout': lock_timeout,
                                 'updated_at': datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')})
            show_toast("Settings Saved", "System settings updated successfully", "success")

    st.markdown("</div>", unsafe_allow_html=True)


# Component: User Management
def user_management_component():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    users_df = get_users()

    # Add new user
    with st.expander("➕ Add New User", expanded=False):
        with st.form("add_user_form"):
            new_uid = st.text_input("Card UID (e.g., CF 5F 74 1F)")
            new_name = st.text_input("User Name")
            col1, col2 = st.columns(2)
            with col1:
                valid_from_date = st.date_input("Valid From Date", datetime.datetime.now())
                valid_from_time = st.time_input("Valid From Time", datetime.datetime.now().time())
            with col2:
                valid_until_date = st.date_input("Valid Until Date",
                                                 datetime.datetime.now() + timedelta(days=365))
                valid_until_time = st.time_input("Valid Until Time", datetime.time(23, 59, 59))

            submit_button = st.form_submit_button("Add User")
            if submit_button:
                if not new_uid:
                    st.error("UID is required")
                else:
                    from_datetime = datetime.datetime.combine(valid_from_date, valid_from_time)
                    until_datetime = datetime.datetime.combine(valid_until_date, valid_until_time)
                    from_str = from_datetime.strftime("%Y-%m-%d_%H-%M-%S")
                    until_str = until_datetime.strftime("%Y-%m-%d_%H-%M-%S")

                    user_data = {
                        "Name": new_name if new_name else "New User",
                        "OriginalUID": new_uid,
                        "ValidFrom": from_str,
                        "ValidUntil": until_str,
                        "AddedOn": datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                        "Authorized": True
                    }
                    if add_user(new_uid, user_data):
                        st.success(f"User {new_name} added successfully!")
                        time.sleep(1)
                        st.rerun()

    # Display and edit existing users
    if not users_df.empty:
        st.subheader("📋 Registered Users")

        for idx, user in users_df.iterrows():
            with st.expander(f"👤 {user.get('Name', 'Unknown')} - {user.get('OriginalUID', 'N/A')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.text(f"Original UID: {user.get('OriginalUID', 'N/A')}")
                    st.text(f"Hashed UID: {user.get('HashedUID', 'N/A')}")
                    st.text(f"Added On: {user.get('AddedOn', 'N/A').replace('_', ' ')}")

                    auth_status = user.get('Authorized', True)
                    if auth_status:
                        st.success("✓ Authorized")
                    else:
                        st.error("✗ Unauthorized")

                with col2:
                    if 'ValidFrom' in user and 'ValidUntil' in user:
                        st.text(f"Valid From: {user['ValidFrom'].replace('_', ' ')}")
                        st.text(f"Valid Until: {user['ValidUntil'].replace('_', ' ')}")

                # Edit form
                with st.form(f"edit_user_{user['HashedUID']}"):
                    st.subheader("Edit User")
                    edit_name = st.text_input("Name", value=user.get('Name', ''), key=f"name_{user['HashedUID']}")

                    # Parse existing dates
                    from_date, from_time = datetime.datetime.now().date(), datetime.datetime.now().time()
                    until_date, until_time = datetime.datetime.now().date(), datetime.datetime.now().time()

                    if 'ValidFrom' in user:
                        try:
                            dt_str = user['ValidFrom'].replace('_', ' ').replace('-', ':')
                            dt = datetime.datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                            from_date, from_time = dt.date(), dt.time()
                        except:
                            pass

                    if 'ValidUntil' in user:
                        try:
                            dt_str = user['ValidUntil'].replace('_', ' ').replace('-', ':')
                            dt = datetime.datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                            until_date, until_time = dt.date(), dt.time()
                        except:
                            pass

                    col1, col2 = st.columns(2)
                    with col1:
                        edit_from_date = st.date_input("Valid From Date", from_date,
                                                       key=f"from_date_{user['HashedUID']}")
                        edit_from_time = st.time_input("Valid From Time", from_time,
                                                       key=f"from_time_{user['HashedUID']}")
                    with col2:
                        edit_until_date = st.date_input("Valid Until Date", until_date,
                                                        key=f"until_date_{user['HashedUID']}")
                        edit_until_time = st.time_input("Valid Until Time", until_time,
                                                        key=f"until_time_{user['HashedUID']}")

                    is_authorized = st.checkbox("Authorized", value=user.get('Authorized', True),
                                                key=f"auth_{user['HashedUID']}")

                    col_save, col_delete = st.columns(2)
                    with col_save:
                        save_button = st.form_submit_button("💾 Save Changes", use_container_width=True)
                    with col_delete:
                        delete_button = st.form_submit_button("🗑️ Delete User", use_container_width=True)

                    if save_button:
                        edit_from_dt = datetime.datetime.combine(edit_from_date, edit_from_time)
                        edit_until_dt = datetime.datetime.combine(edit_until_date, edit_until_time)

                        user_data = {
                            "Name": edit_name,
                            "ValidFrom": edit_from_dt.strftime("%Y-%m-%d_%H-%M-%S"),
                            "ValidUntil": edit_until_dt.strftime("%Y-%m-%d_%H-%M-%S"),
                            "UpdatedOn": datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                            "Authorized": is_authorized,
                            "OriginalUID": user.get('OriginalUID', ''),
                            "AddedOn": user.get('AddedOn', '')
                        }

                        try:
                            user_ref = db.reference(f'AuthorizedUsers/{user["HashedUID"]}')
                            user_ref.update(user_data)
                            st.success(f"User {edit_name} updated successfully!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

                    if delete_button:
                        try:
                            db.reference(f'AuthorizedUsers/{user["HashedUID"]}').delete()
                            st.success(f"User deleted successfully!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
    else:
        st.info("No users registered yet")

    st.markdown("</div>", unsafe_allow_html=True)


# Component: Anomaly Detection
def anomaly_detection_component():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Access Anomalies")
    logs_df = get_access_logs()

    if not logs_df.empty and 'Timestamp' in logs_df.columns:
        if 'Status' in logs_df.columns:
            unauthorized = logs_df[logs_df['Status'] == 'UNAUTHORIZED']
            if not unauthorized.empty:
                st.warning(f"Found {len(unauthorized)} unauthorized access attempts")
                recent_unauthorized = unauthorized.head(5)
                for _, row in recent_unauthorized.iterrows():
                    st.error(f"⚠️ Unauthorized access by UID {row['UID']} at {row['Timestamp']}")
                if len(unauthorized) > 5:
                    with st.expander("Show all unauthorized attempts"):
                        st.dataframe(unauthorized[['UID', 'Timestamp']])
            else:
                st.success("No unauthorized access attempts detected")

        logs_df['hour'] = logs_df['Timestamp'].dt.hour
        off_hours = logs_df[(logs_df['hour'] < 8) | (logs_df['hour'] > 20)]
        if not off_hours.empty:
            st.warning(f"Found {len(off_hours)} access attempts outside normal hours (8 AM - 8 PM)")
            recent_off_hours = off_hours.head(5)
            for _, row in recent_off_hours.iterrows():
                st.warning(f"⏰ Off-hours access by UID {row['UID']} at {row['Timestamp']}")
        else:
            st.success("No off-hours access attempts detected")

        if len(logs_df) > 5:
            st.subheader("Access Pattern Analysis")
            logs_df['day'] = logs_df['Timestamp'].dt.day_name()
            logs_df['hour'] = logs_df['Timestamp'].dt.hour
            heatmap_data = pd.pivot_table(logs_df, values='UID', index='day',
                                          columns='hour', aggfunc='count', fill_value=0)
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            heatmap_data = heatmap_data.reindex(day_order)
            fig = px.imshow(heatmap_data,
                            labels=dict(x="Hour of Day", y="Day of Week", color="Access Count"),
                            x=heatmap_data.columns.tolist(), y=day_order,
                            color_continuous_scale="YlOrRd")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient access data for anomaly detection")

    st.markdown("</div>", unsafe_allow_html=True)


# Render selected component
if selected_nav == "Real-time Status":
    st.title("Real-time System Status")
    st.caption("Monitor your system's current state and recent activity")
    real_time_status_component()
elif selected_nav == "Live Access Logs":
    st.title("Access Logs")
    st.caption("View and filter all access attempts")
    live_access_logs_component()
elif selected_nav == "Remote Control":
    st.title("Remote System Control")
    st.caption("Control your lock system and adjust settings")
    remote_control_component()
elif selected_nav == "User Management":
    st.title("User Management")
    st.caption("Add, edit, and remove authorized users")
    user_management_component()
elif selected_nav == "Anomaly Detection":
    st.title("Security Anomalies")
    st.caption("Detect unusual access patterns and security concerns")
    anomaly_detection_component()

# Auto-refresh option
with st.expander("Dashboard Settings"):
    auto_refresh = st.checkbox("Enable auto-refresh", value=False)
    if auto_refresh:
        refresh_interval = st.slider("Refresh interval (seconds)", 5, 60, 10)
        st.write(f"Dashboard will refresh every {refresh_interval} seconds")
        time.sleep(refresh_interval)
        st.rerun()
