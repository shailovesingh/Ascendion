import streamlit as st
import pandas as pd
import folium
import time
import os
from dotenv import load_dotenv
from streamlit_folium import folium_static
from core.data import get_combined_data, update_cab_positions, advance_sim_clock, simulation_log
from core.logistics_graph import run_logistics_for_all_trips
import numpy as np
import time
import os
from dotenv import load_dotenv
load_dotenv()

# Check for API Key
if not os.getenv("GROQ_API_KEY"):
    st.error("Please set the GROQ_API_KEY in the .env file.")
    st.stop()

from streamlit_folium import folium_static
from core.data import get_combined_data, update_cab_positions, advance_sim_clock, simulation_log
from core.logistics_graph import run_logistics_for_all_trips

# Configuration
REFRESH_INTERVAL_SECONDS = 3
DEFAULT_MAP_CENTER = [20.59, 78.96] # Center of India
DEFAULT_MAP_ZOOM = 5

# Utility Functions
def get_status_color(status):
    """Map status to a color for the dashboard."""
    if status in ['Landed', 'Dispatching']:
        return "darkred"
    elif status == 'Picked Up':
        return "green"
    elif status == 'On Trip':
        return "blue"
    else:
        return "gray"

# Streamlit UI Components

st.set_page_config(layout="wide", page_title="Executive Travel AI Dashboard")

st.title("✈️ Leadership Travel – AI Logistics Demo (12 Executives)")
st.markdown("---")
st.secrets["GROQ_API_KEY"]

# Initialize current_minute in session state if not present
if 'current_minute' not in st.session_state:
    st.session_state.current_minute = 0

# Use a placeholder to continuously update the content
placeholder = st.empty()

with placeholder.container():
    
    # 1. Run the AI Logic (LangGraph/Groq)
    new_llm_actions = run_logistics_for_all_trips()
    for action in new_llm_actions:
        st.info(f"LLM Notification: {action}")
        
    # 2. Advance Sim Clock and Cab Positions
    current_minute = advance_sim_clock()
    update_cab_positions()
    
    # 3. Get Combined Data for Display
    df_combined = get_combined_data()

    # KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Trips", len(df_combined))
    with col2:
        st.metric("Flights Landed (Awaiting Pickup)", df_combined[df_combined['status'] == 'Landed'].shape[0])
    with col3:
        st.metric("Cabs On Trip", df_combined[df_combined['cab_status'] == 'On Trip'].shape[0])
    with col4:
        st.metric("Trips Dispatched/Picked Up", df_combined[df_combined['status'].isin(['Dispatching', 'Picked Up'])].shape[0])
    with col5:
        st.metric("Sim Clock (min)", current_minute)

    st.markdown("---")

    col_map, col_table = st.columns([1, 1])

    with col_map:
        st.subheader("Live Map: Cab Tracking")
        
        # Initialize Folium Map
        m = folium.Map(location=DEFAULT_MAP_CENTER, zoom_start=DEFAULT_MAP_ZOOM)
        
        # Add markers for all tracked cabs
        for index, row in df_combined.iterrows():
            if not pd.isna(row['lat']):
                color_name = get_status_color(row['cab_status'])
                
                # Get cab icon for the color
                icon_url = f"https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-{color_name}.png"
                
                popup_html = f"""
                    <b>{row['executive']} - {row['flight_no']}</b><br>
                    Cab: {row['cab_reg_no']} ({row['driver_name']})<br>
                    Status: {row['cab_status']} @ {int(row['speed_kmh'])} km/h
                """
                folium.Marker(
                    location=[row['lat'], row['lon']],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.CustomIcon(
                        icon_image=icon_url,
                        icon_size=(25, 41),
                        icon_anchor=(12, 41),
                        popup_anchor=(1, -34)
                    ),
                ).add_to(m)
                
        # Fit map to bounds of active cabs
        active_cabs = df_combined[df_combined['cab_status'] != 'Off Duty']
        if not active_cabs.empty and active_cabs.shape[0] > 1:
             # Add small buffer to avoid map being too zoomed in if points are very close
            lat_padding = np.ptp(active_cabs['lat']) * 0.1 
            lon_padding = np.ptp(active_cabs['lon']) * 0.1
            bounds = [
                [active_cabs['lat'].min() - lat_padding, active_cabs['lon'].min() - lon_padding], 
                [active_cabs['lat'].max() + lat_padding, active_cabs['lon'].max() + lon_padding]
            ]
            m.fit_bounds(bounds)
        else:
             # If only one cab, just set the center to that cab
             if active_cabs.shape[0] == 1:
                 m.location = [active_cabs['lat'].iloc[0], active_cabs['lon'].iloc[0]]
                 m.zoom_start = 12 # Zoom in closer for a single point

        # Display the map in Streamlit
        folium_static(m, width=700, height=450)

    with col_table:
        st.subheader("Unified Status Board (Flight + Cab)")
        
        # Select and format columns for display
        df_display = df_combined[['executive', 'flight_no', 'status', 'cab_reg_no', 'cab_status', 'driver_name', 'speed_kmh']]
        df_display.columns = ['Executive', 'Flight', 'Flight Status', 'Cab Reg No', 'Cab Status', 'Driver', 'Speed (km/h)']
        
        # Sort by Flight Status to bring 'Landed'/Dispatching' trips to the top
        df_display = df_display.sort_values(by=['Flight Status', 'Cab Status'], ascending=[False, False])
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.subheader("Simulation Log")
    log_text = "\n".join(simulation_log[-10:]) # Show last 10 log entries
    st.text_area("LangGraph and Dispatch Actions", log_text, height=150)


# Real-time Loop
time.sleep(REFRESH_INTERVAL_SECONDS)
st.rerun()