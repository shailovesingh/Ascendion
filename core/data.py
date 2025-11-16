import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import streamlit as st

# TRIP MASTER DATA (12 Executives)
executives = ['CEO', 'CFO'] + [f'Board Member {i}' for i in range(1, 11)]
flight_numbers = [f'AI{random.randint(100, 999)}' for _ in range(12)]
cab_reg_numbers = [f'KA{i:02}AB{random.randint(1000, 9999)}' for i in range(1, 13)]
cities = ['Bengaluru', 'Mumbai', 'Delhi', 'Hyderabad', 'Chennai', 'Pune', 'Kolkata', 'Ahmedabad', 'Jaipur', 'Lucknow', 'Goa', 'Chandigarh']

trips_data = {
    'trip_id': list(range(1, 13)),
    'executive': executives,
    'flight_no': flight_numbers,
    'status': ['En Route'] * 12, # Status can be 'En Route', 'Landed', 'Dispatching', 'Picked Up'
    'cab_reg_no': cab_reg_numbers,
    'destination_city': random.sample(cities, 12),
    'latest_update': [datetime.now()] * 12
}
trips_df = pd.DataFrame(trips_data)
trips_df.set_index('trip_id', inplace=True)

# CAB MASTER DATA (12 Drivers)
drivers = [f'Driver {i}' for i in range(1, 13)]
phones = [f'+91 98765 {i:04}' for i in range(1, 13)]

cabs_data = {
    'cab_reg_no': cab_reg_numbers,
    'driver_name': drivers,
    'driver_phone': phones,
    # Initial scattered simulated GPS positions (within a reasonable range for India)
    'lat': np.random.uniform(10.0, 30.0, 12), 
    'lon': np.random.uniform(70.0, 85.0, 12),
    'speed_kmh': [0] * 12,
    'cab_status': ['Idle'] * 8 + ['Off Duty'] * 4 # Mix of statuses
}
cabs_df = pd.DataFrame(cabs_data)
cabs_df.set_index('cab_reg_no', inplace=True)

# SIMULATION STATE
simulation_log = []
landed_times = {} # To track when a flight lands to avoid immediate re-triggering

def update_sim_data(new_trip_status=None, new_cab_loc=None):
    """Function to update the data frames (simulating database writes)."""
    global trips_df, cabs_df
    
    if new_trip_status:
        for trip_id, status in new_trip_status.items():
            if trip_id in trips_df.index:
                if trips_df.loc[trip_id, 'status'] != status:
                    trips_df.loc[trip_id, 'status'] = status
                    trips_df.loc[trip_id, 'latest_update'] = datetime.now()

    if new_cab_loc:
        for reg_no, update in new_cab_loc.items():
            if reg_no in cabs_df.index:
                cabs_df.loc[reg_no, 'lat'] = update.get('lat', cabs_df.loc[reg_no, 'lat'])
                cabs_df.loc[reg_no, 'lon'] = update.get('lon', cabs_df.loc[reg_no, 'lon'])
                cabs_df.loc[reg_no, 'speed_kmh'] = update.get('speed_kmh', cabs_df.loc[reg_no, 'speed_kmh'])
                cabs_df.loc[reg_no, 'cab_status'] = update.get('cab_status', cabs_df.loc[reg_no, 'cab_status'])


def get_combined_data():
    """Combines trip and cab data for the dashboard."""
    return trips_df.join(cabs_df, on='cab_reg_no', how='left')

def update_cab_positions():
    """Simulates real-time GPS movement for the dashboard."""
    global cabs_df
    for index, cab in cabs_df.iterrows():
        if cab['cab_status'] == 'On Trip':
            # Jitter movement for 'On Trip' (faster movement)
            lat_delta = np.random.uniform(-0.005, 0.005)
            lon_delta = np.random.uniform(-0.005, 0.005)
            cabs_df.loc[index, 'lat'] += lat_delta
            cabs_df.loc[index, 'lon'] += lon_delta
            cabs_df.loc[index, 'speed_kmh'] = np.random.randint(20, 60)
        elif cab['cab_status'] == 'Idle':
            # Slight jitter for 'Idle' (waiting at airport)
            lat_delta = np.random.uniform(-0.0002, 0.0002)
            lon_delta = np.random.uniform(-0.0002, 0.0002)
            cabs_df.loc[index, 'lat'] += lat_delta
            cabs_df.loc[index, 'lon'] += lon_delta
            cabs_df.loc[index, 'speed_kmh'] = np.random.randint(0, 5)
        else: # Off Duty
            cabs_df.loc[index, 'speed_kmh'] = 0
            
def advance_sim_clock():
    """Advances the clock using Streamlit session state for persistence."""
    # The 'st' object is now defined here
    if 'current_minute' not in st.session_state:
        st.session_state.current_minute = 0
    st.session_state.current_minute += 1
    return st.session_state.current_minute

def get_current_state():
    return trips_df.copy()

def add_to_log(message):
    simulation_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")