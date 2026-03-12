import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from shapely import wkt
from shapely.errors import WKTReadingError
import plotly.express as px

# UI libraries
from streamlit_option_menu import option_menu
from streamlit_extras.metric_cards import style_metric_cards

# ==========================
# PAGE CONFIGURATION
# ==========================
st.set_page_config(
    page_title="KLIMATA Risk Dashboard",
    page_icon="🗺️",
    layout="wide"
)

# ==========================
# DATA LOADING FUNCTIONS
# ==========================
@st.cache_data
def load_data(csv_path, encoding='utf-8'):
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

@st.cache_data
def load_amenity_data(path):
    return pd.read_csv(path, encoding='latin1')

# ==========================
# DASHBOARD BUILDER
# ==========================
def build_dashboard(gdf, df2):
    # --- Standardize Barangay Names for gdf ---
    if 'brgy_names-ILOILO.location.adm4_en' in gdf.columns:
        gdf['barangay_name'] = gdf['brgy_names-ILOILO.location.adm4_en']
    elif 'location1.adm4_en' in gdf.columns:
        gdf['barangay_name'] = gdf['location1.adm4_en']
    else:
        gdf['barangay_name'] = None

    # --- Standardize Barangay Names for df2 ---
    if 'location1.adm4_en' in df2.columns:
        df2['barangay_name'] = df2['location1.adm4_en']
    else:
        df2['barangay_name'] = None

    dark_mode = st.sidebar.toggle("🌗 Dark Mode", value=True)

    # Apply theme
    if dark_mode:
        st.markdown("""
        <style>
        .stApp {background-color: #121212; color: #E0E0E0;}
        [data-testid="stHeader"] {background-color: #111318;}
        div[data-testid="stMetricValue"] {color: #00ADB5 !important; text-shadow: 0px 0px 6px rgba(0,173,181,0.7);}
        section[data-testid="stSidebar"] {background-color: #111318; color: #EEE;}
        </style>
        """, unsafe_allow_html=True)
        metric_style = dict(background_color="#1E1E1E", border_left_color="#00ADB5", border_color="#2C2C2C")
    else:
        st.markdown("""
        <style>
        .stApp {background-color: #F5F6FA; color: #000000;}
        [data-testid="stHeader"] {background-color: #E0E0E0;}
        div[data-testid="stMetricValue"] {color: #000000 !important;}
        section[data-testid="stSidebar"] {background-color: #FFFFFF; color: #000000;}
        </style>
        """, unsafe_allow_html=True)
        metric_style = dict(background_color="#FFFFFF", border_left_color="#00ADB5", border_color="#DDDDDD")

    # Sidebar Navigation
    with st.sidebar:
        selected = option_menu(
            menu_title=None,
            options=["City Overview", "Barangay Deep Dive"],
            icons=["house", "map"],
            menu_icon="globe",
            default_index=0,
            styles={
                "container": {"padding": "5px", "background-color": "transparent"},
                "icon": {"color": "#00ADB5", "font-size": "18px"},
                "nav-link": {"color": "#EEEEEE" if dark_mode else "#111", "font-size": "15px", "text-align": "left"},
                "nav-link-selected": {"background-color": "#00ADB5", "color": "white"},
            },
        )

    # =====================
    # City Overview
    # =====================
    if selected == "City Overview":
        background_image_url = "https://www.detourista.com/wp/wp-content/uploads/Tax-Place/Philippines/Iloilo/Iloilo/Featured/001-Calle-Real-in-Iloilo-City-150105-063819.jpg"

        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: linear-gradient(rgba(18, 18, 18, 0.85), rgba(18, 18, 18, 0.85)),
                              url("{background_image_url}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
        }}
        </style>
        """, unsafe_allow_html=True)

        st.title("Iloilo City: Climate Vulnerability Index")

        selected_layer = st.sidebar.radio(
            "🗺️ Select Map Layer",
            ["Urban Risk", "Population", "Amenity", "Climate Exposure"]
        )

        layer_config = {
            "Urban Risk": {"col": "urban_risk_index", "color": "YlOrRd", "legend": "Urban Risk Index"},
            "Population": {"col": "pop_total", "color": "Blues", "legend": "Population Total"},
            "Amenity": {"col": "infra_index", "color": "Reds", "legend": "Amenity Index"},
            "Climate Exposure": {"col": "climate_exposure_score", "color": "Greens", "legend": "Climate Exposure Score"},
        }

        col_config = layer_config[selected_layer]
        metric_col = col_config["col"]
        color_scale = col_config["color"]
        legend_name = col_config["legend"]

        avg_risk = gdf['urban_risk_index'].mean()
        avg_infra = gdf['infra_index'].mean()
        avg_wealth = gdf['rwi_mean'].mean()

        col1, col2, col3 = st.columns(3)
        col1.metric("Average Urban Risk", f"{avg_risk:.2f}")
        col2.metric("Average Infrastructure", f"{avg_infra:.2f}")
        col3.metric("Average Relative Wealth", f"{avg_wealth:.2f}")
        style_metric_cards(**metric_style, box_shadow=True)

        iloilo_center = [10.7202, 122.5621]
        m = folium.Map(location=iloilo_center, zoom_start=13)

        folium.Choropleth(
            geo_data=gdf,
            data=gdf,
            columns=['adm4_pcode', metric_col],
            key_on='feature.properties.adm4_pcode',
            fill_color=color_scale,
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name=legend_name
        ).add_to(m)

        if selected_layer == "Urban Risk":
            tooltip_fields = [
                'barangay_name', 'urban_risk_index', 'risk_level',
                'infra_risk', 'climate_exposure_score', 'coast_risk',
                'ndvi_risk', 'pop_risk', 'rwi_risk'
            ]
            tooltip_aliases = [
                'Barangay:', 'Urban Risk Index:', 'Risk Level:',
                'Climate Vulnerability Index:', 'Climate Exposure Score:',
                'Coastal Distance Risk Score:', 'NDVI Risk Score:',
                'Population Risk Score:', 'Relative Wealth Index (RWI) Risk Score:'
            ]
        else:
            tooltip_fields = ['barangay_name', metric_col]
            tooltip_aliases = ['Barangay:', legend_name + ":"]

        folium.GeoJson(
            gdf,
            tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases, localize=True)
        ).add_to(m)

        st_folium(m, width='100%', height=600)

        tab1, tab2 = st.tabs(["Top 5 Barangays", "Value Distribution"])
        with tab1:
            top_5 = gdf.nlargest(5, metric_col)
            top_5_df = top_5[['barangay_name', metric_col]].copy()
            top_5_df.rename(columns={'barangay_name': 'Barangay', metric_col: legend_name}, inplace=True)
            fig = px.bar(top_5_df, x='Barangay', y=legend_name, title=f"Top 5 Barangays by {legend_name}",
                         color=legend_name, color_continuous_scale=color_scale, text=legend_name)
            fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            color_map = {"YlOrRd": "#F4A261", "Blues": "#1E90FF", "Reds": "#E63946", "Greens": "#2A9D8F"}
            hist_color = color_map.get(color_scale, "#00ADB5")
            fig = px.histogram(gdf, x=metric_col, nbins=20, title=f"Distribution of {legend_name}")
            fig.update_traces(marker_color=hist_color, opacity=0.8)
            st.plotly_chart(fig, use_container_width=True)

    # =====================
    # Barangay Deep Dive
    # =====================
    elif selected == "Barangay Deep Dive":
        background_image_url = "https://www.detourista.com/wp/wp-content/uploads/Tax-Place/Philippines/Iloilo/Iloilo/Featured/001-Calle-Real-in-Iloilo-City-150105-063819.jpg"

        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: linear-gradient(rgba(18, 18, 18, 0.85), rgba(18, 18, 18, 0.85)),
                              url("{background_image_url}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
        }}
        </style>
        """, unsafe_allow_html=True)

        st.title("Barangay Deep Dive")
        brgy_list = sorted(gdf['barangay_name'].dropna().unique())

        search_query = st.sidebar.text_input("🔍 Search Barangay")
        filtered_brgy_list = [b for b in brgy_list if search_query.lower() in b.lower()] if search_query else brgy_list

        if len(filtered_brgy_list) == 0:
            st.sidebar.warning("No barangay found. Try a different search.")
            st.stop()

        selected_brgy = st.sidebar.selectbox("Select a Barangay", filtered_brgy_list)
        brgy_data_rows = gdf[gdf['barangay_name'] == selected_brgy]

        if brgy_data_rows.empty:
            st.error("Data not available for this barangay.")
            st.stop()

        brgy_data = brgy_data_rows.iloc[0]
        st.header(f"📍 Dashboard for: {selected_brgy}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Urban Risk Score", f"{brgy_data['urban_risk_index']:.2f}")
        col2.metric("Risk Level", brgy_data['risk_label'])
        col3.metric("Relative Wealth Index", f"{brgy_data['rwi_mean']:.2f}")
        style_metric_cards(**metric_style, box_shadow=True)

        brgy_gdf = gpd.GeoDataFrame([brgy_data], geometry='geometry', crs=gdf.crs)
        centroid = brgy_gdf.geometry.centroid.iloc[0]
        m = folium.Map(location=[centroid.y, centroid.x], zoom_start=15)
        folium.GeoJson(
            brgy_gdf,
            style_function=lambda x: {'fillColor': 'blue', 'color': 'blue', 'fillOpacity': 0.5},
            tooltip=folium.GeoJsonTooltip(
                fields=['barangay_name', 'urban_risk_index', 'risk_label'],
                aliases=['Barangay:', 'Urban Risk Index:', 'Risk Level:'],
                localize=True
            )
        ).add_to(m)
        st_folium(m, width='100%', height=500)

        st.subheader("🏫 Nearest Amenities Overview")
        brgy_amenities = df2[df2['barangay_name'] == selected_brgy]

        if not brgy_amenities.empty:
            amenity_cols = ['college_nearest', 'community_centre_nearest', 'school_nearest',
                            'shelter_nearest', 'town_hall_nearest', 'university_nearest']
            amenity_data = brgy_amenities[amenity_cols].melt(var_name='Amenity Type', value_name='Distance (meters)')
            amenity_data['Amenity Type'] = amenity_data['Amenity Type'].str.replace('_nearest', '').str.replace('_', ' ').str.title()

            fig = px.bar(
                amenity_data,
                x='Amenity Type',
                y='Distance (meters)',
                title=f"Nearest Facilities from {selected_brgy}",
                color='Distance (meters)',
                color_continuous_scale='tealgrn'
            )
            fig.update_traces(texttemplate='%{y:.1f}', textposition='outside')
            fig.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(amenity_data)
        else:
            st.info("No amenity data available for this barangay.")


# ==========================
# MAIN APP
# ==========================
gdf = load_data('URBAN_RISK_data.csv', encoding='latin1')
df2 = load_amenity_data('AMENITY_FINAL.csv')
build_dashboard(gdf, df2)
