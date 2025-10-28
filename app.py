import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from shapely import wkt
from shapely.errors import WKTReadingError
import plotly.express as px
import sqlite3  # --- NEW: For our Python-only database
import hashlib  # --- NEW: For hashing passwords securely

# --- Page Configuration ---
st.set_page_config(
    page_title="KLIMATA Risk Dashboard",
    page_icon="🗺️",
    layout="wide"
)

# --- NEW: DATABASE FUNCTIONS (The "C.R.U.D." Backend) ---

def hash_password(password):
    """Securely hash the password using SHA-256."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    """Initialize the SQLite database and create the users table if it doesn't exist."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_user(username, password):
    """CREATE: Add a new user to the database."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    finally:
        conn.close()

def check_user_password(username, password):
    """READ: Check if a username exists and the password is correct."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    data = c.fetchone()
    conn.close()
    if data:
        return data[0] == hash_password(password)
    return False

def update_user_password(username, new_password):
    """UPDATE: Update an existing user's password."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(new_password), username))
    conn.commit()
    conn.close()
    return True

def delete_user(username):
    """DELETE: Delete a user from the database."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return True

# --- Data Loading Function (Your original code, unchanged) ---
@st.cache_data
def load_data(csv_path, encoding='utf-8'):
    """Loads, cleans, and prepares the data, returning a GeoDataFrame."""

    def parse_wkt(wkt_string):
        if not isinstance(wkt_string, str):
            return None
        try:
            return wkt.loads(wkt_string)
        except (WKTReadingError, TypeError):
            return None

    df = pd.read_csv(csv_path, encoding=encoding)
    df['geometry'] = df['brgy_names-ILOILO.geometry'].apply(parse_wkt)
    df.dropna(subset=['geometry', 'urban_risk_index'], inplace=True)

    gdf = gpd.GeoDataFrame(df, geometry='geometry')
    gdf.set_crs(epsg=4326, inplace=True)
    return gdf

# --- Dashboard Builder (Modified to add new sidebar buttons) ---
def build_dashboard(gdf):
    # --- Sidebar ---
    st.sidebar.title(f"Welcome, {st.session_state['username']}!") # NEW: Show logged-in user
    st.sidebar.header("Navigation")
    mode = st.sidebar.radio("Select View", ["City Overview", "Barangay Deep Dive"])

    # --- NEW: Sidebar buttons for account management ---
    if st.sidebar.button("Manage Account"):
        st.session_state.page = "Manage Account"
        st.rerun()

    if st.sidebar.button("Log Out"):
        st.session_state.logged_in = False
        del st.session_state.username
        st.session_state.page = "Login"
        st.rerun()

    # =======================
    # CITY OVERVIEW SECTION
    # =======================
    if mode == "City Overview":
        st.title("Iloilo City: Urban Risk Dashboard")
        
        # --- (Your original KPI, Map, and Chart code... unchanged) ---
        avg_risk = gdf['urban_risk_index'].mean()
        avg_infra = gdf['infra_index'].mean()
        avg_wealth = gdf['rwi_mean'].mean()

        col1, col2, col3 = st.columns(3)
        col1.metric("Average Urban Risk", f"{avg_risk:.2f}")
        col2.metric("Average Infrastructure", f"{avg_infra:.2f}")
        col3.metric("Average Relative Wealth", f"{avg_wealth:.2f}")

        iloilo_center = [10.7202, 122.5621]
        m = folium.Map(location=iloilo_center, zoom_start=13)
        folium.Choropleth(
            geo_data=gdf,
            name='Urban Risk Index',
            data=gdf,
            columns=['adm4_pcode', 'urban_risk_index'],
            key_on='feature.properties.adm4_pcode',
            fill_color='YlOrRd',
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name='Urban Risk Index'
        ).add_to(m)
        folium.GeoJson(
            gdf,
            tooltip=folium.GeoJsonTooltip(
                fields=['brgy_names-ILOILO.location.adm4_en', 'urban_risk_index', 'risk_label'],
                aliases=['Barangay:', 'Risk Index:', 'Risk Level:'],
                localize=True
            )
        ).add_to(m)
        st_folium(m, width='100%', height=600)

        tab1, tab2 = st.tabs(["Top 5 At-Risk Barangays", "Risk Level Distribution"])
        with tab1:
            top_5 = gdf.nlargest(5, 'urban_risk_index')
            top_5_df = top_5[['brgy_names-ILOILO.location.adm4_en', 'urban_risk_index']].copy()
            top_5_df.rename(
                columns={
                    'brgy_names-ILOILO.location.adm4_en': 'Barangay',
                    'urban_risk_index': 'Urban Risk Index'
                },
                inplace=True
            )
            fig = px.bar(
                top_5_df,
                x='Barangay',
                y='Urban Risk Index',
                title='Top 5 At-Risk Barangays',
                color='Urban Risk Index',
                color_continuous_scale='YlOrRd',
                text='Urban Risk Index',
                labels={'Urban Risk Index': 'Risk Index Value'}
            )
            fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig.update_layout(
                xaxis_tickangle=-45,
                yaxis_title='Urban Risk Index',
                xaxis_title='Barangay',
                title_x=0.3
            )
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("Risk Level Distribution")
            risk_counts = gdf['risk_label'].value_counts()
            risk_df = pd.DataFrame({'Risk Level': risk_counts.index, 'Count': risk_counts.values})
            color_map = {'High Risk': 'red', 'Medium Risk': 'orange', 'Low Risk': 'yellow'}
            fig = px.pie(
                risk_df,
                values='Count',
                names='Risk Level',
                color='Risk Level',
                color_discrete_map=color_map,
                title='Risk Level Distribution'
            )
            st.plotly_chart(fig, use_container_width=True)

    # ============================
    # BARANGAY DEEP DIVE SECTION
    # ============================
    else:
        # --- (Your original Barangay Deep Dive code... unchanged) ---
        brgy_list = gdf['brgy_names-ILOILO.location.adm4_en'].dropna().unique()
        selected_brgy = st.sidebar.selectbox("Select a Barangay", brgy_list)
        
        # Handle case where selected_brgy might not be in the filtered gdf
        brgy_data_rows = gdf[gdf['brgy_names-ILOILO.location.adm4_en'] == selected_brgy]
        
        if brgy_data_rows.empty:
            st.error("Data not available for this barangay.")
            return
            
        brgy_data = brgy_data_rows.iloc[0]

        st.title(f"Dashboard for: {selected_brgy}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Urban Risk Score", f"{brgy_data['urban_risk_index']:.2f}")
        col2.metric("Risk Level", brgy_data['risk_label'])
        col3.metric("Relative Wealth Index", f"{brgy_data['rwi_mean']:.2f}")

        brgy_gdf = gpd.GeoDataFrame([brgy_data], geometry='geometry', crs=gdf.crs)

        m = folium.Map(
            location=[
                brgy_gdf.geometry.centroid.y.iloc[0],
                brgy_gdf.geometry.centroid.x.iloc[0]
            ],
            zoom_start=15
        )
        folium.GeoJson(
            brgy_gdf,
            style_function=lambda x: {'fillColor': 'blue', 'color': 'blue'},
            tooltip=folium.GeoJsonTooltip(
                fields=['brgy_names-ILOILO.location.adm4_en', 'urban_risk_index', 'risk_label'],
                aliases=['Barangay:', 'Risk Index:', 'Risk Level:'],
                localize=True
            )
        ).add_to(m)
        st_folium(m, width='100%', height=500)

        st.subheader("Barangay vs. City Average")
        avg_scores = {
            'Climate Exposure': gdf['climate_exposure_score'].mean(),
            'Infrastructure Index': gdf['infra_index'].mean(),
            'Relative Wealth': gdf['rwi_mean'].mean()
        }
        brgy_scores = {
            'Climate Exposure': brgy_data['climate_exposure_score'],
            'Infrastructure Index': brgy_data['infra_index'],
            'Relative Wealth': brgy_data['rwi_mean']
        }
        chart_data = pd.DataFrame({'City Average': avg_scores, selected_brgy: brgy_scores})
        st.bar_chart(chart_data)

# --- NEW: PAGE FUNCTIONS FOR LOGIN, SIGNUP, MANAGE ACCOUNT ---

def show_login_page():
    """Display the login page."""
    st.title("KLIMATA: Urban Risk Assessment Portal")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In")

        if submitted:
            if check_user_password(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.page = "Dashboard"
                st.rerun()
            else:
                st.error("😕 User not known or password incorrect")
    
    if st.button("Need an account? Sign Up"):
        st.session_state.page = "Sign Up"
        st.rerun()

def show_signup_page():
    """Display the account creation page."""
    st.title("Create a New Account")
    
    with st.form("signup_form"):
        username = st.text_input("New Username")
        password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account")

        if submitted:
            if not username or not password or not confirm_password:
                st.error("Please fill in all fields.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            else:
                if create_user(username, password):
                    st.success("Account created successfully! Please log in.")
                    st.session_state.page = "Login"
                    st.rerun()
                else:
                    st.error("Username already exists. Please choose another.")
    
    if st.button("Back to Login"):
        st.session_state.page = "Login"
        st.rerun()

def show_manage_account_page():
    """Display the page for updating or deleting the account."""
    st.title(f"Manage Account: {st.session_state['username']}")
    st.sidebar.title(f"Welcome, {st.session_state['username']}!")
    if st.sidebar.button("Back to Dashboard"):
        st.session_state.page = "Dashboard"
        st.rerun()
        
    st.sidebar.button("Log Out", on_click=lambda: (
        st.session_state.update(logged_in=False, page="Login"),
        st.session_state.pop('username', None),
        st.rerun()
    ))
    
    # --- UPDATE (U) ---
    st.subheader("Change Your Password")
    with st.form("update_password_form"):
        new_password = st.text_input("New Password", type="password")
        confirm_new_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Update Password")

        if submitted:
            if not new_password or not confirm_new_password:
                st.error("Please fill in both fields.")
            elif new_password != confirm_new_password:
                st.error("New passwords do not match.")
            else:
                update_user_password(st.session_state['username'], new_password)
                st.success("Password updated successfully!")

    # --- DELETE (D) ---
    st.subheader("Delete Your Account")
    st.warning("This action is permanent and cannot be undone.")
    if st.button("DELETE MY ACCOUNT", type="primary"):
        delete_user(st.session_state['username'])
        st.session_state.logged_in = False
        del st.session_state.username
        st.session_state.page = "Login"
        st.success("Account deleted successfully.")
        st.rerun()

# --- MAIN APP ROUTER ---
init_db()  # Initialize the database file

# Initialize session state variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "Login"

# Page routing logic
if st.session_state.logged_in:
    if st.session_state.page == "Dashboard":
        gdf = load_data('URBAN_RISK_data.csv', encoding='latin1')
        build_dashboard(gdf)
    elif st.session_state.page == "Manage Account":
        show_manage_account_page()
else:
    if st.session_state.page == "Login":
        show_login_page()
    elif st.session_state.page == "Sign Up":
        show_signup_page()
