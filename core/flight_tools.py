import os
import random
from pydantic import BaseModel, Field
from typing import Literal
from langchain.tools import tool
from core.data import get_current_state, update_sim_data, add_to_log
from groq import Groq
import streamlit as st # Used to access session_state for simulation clock

from dotenv import load_dotenv
load_dotenv()
# Initialize Groq Client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# Pydantic Schemas
class FlightStatus(BaseModel):
    """Structured response for flight status."""
    flight_no: str = Field(description="The unique flight number being tracked.")
    current_status: Literal['En Route', 'Landed', 'Delayed', 'Cancelled'] = Field(description="The current flight status.")
    eta_mins: int = Field(description="Estimated minutes until landing. 0 if landed.")
    gate_or_baggage: str = Field(description="The assigned gate or baggage claim number.")

class FlightCheckInput(BaseModel):
    """Input for checking flight status."""
    trip_id: int = Field(description="The unique ID of the executive trip.")
    flight_no: str = Field(description="The flight number to check.")

class DispatchCabInput(BaseModel):
    """Input for dispatching a cab."""
    trip_id: int = Field(description="The unique ID of the executive trip.")
    cab_reg_no: str = Field(description="The registration number of the cab to dispatch.")

# LangChain Tools

@tool("get_flight_status_sim", args_schema=FlightCheckInput)
def get_flight_status_sim(trip_id: int, flight_no: str) -> FlightStatus:
    """
    Simulates checking a flight status. The status changes based on a
    randomly generated minute count in the simulation for variety.
    """
    state_df = get_current_state()
    current_status = state_df.loc[trip_id, 'status']
    
    # Get the global simulation minute count
    current_minute = st.session_state.get('current_minute', 0)
    
    # Use a dynamic, trip-specific landing trigger based on the trip_id
    landing_minute_trigger = (trip_id * 2) % 15 # Landing occurs every 15 iterations, adjusted by trip_id
    
    # SIMULATION LOGIC 
    new_status = current_status
    if current_status == 'En Route':
        if current_minute > 0 and current_minute % 15 == landing_minute_trigger:
            new_status = 'Landed'
        
    # Update the status in the simulated database
    update_sim_data(new_trip_status={trip_id: new_status})
    add_to_log(f"SIM: Flight {flight_no} status checked for Trip {trip_id}. Current: {new_status}")

    # Return structured Pydantic data
    if new_status == 'Landed' or new_status == 'Dispatching':
        return FlightStatus(
            flight_no=flight_no, 
            current_status='Landed', 
            eta_mins=0, 
            gate_or_baggage=f"Baggage Claim {random.randint(1, 10)}"
        )
    else:
        return FlightStatus(
            flight_no=flight_no, 
            current_status='En Route', 
            eta_mins=random.randint(10, 45), 
            gate_or_baggage="TBD"
        )


@tool("dispatch_cab_and_notify", args_schema=DispatchCabInput)
def dispatch_cab_and_notify(trip_id: int, cab_reg_no: str) -> str:
    """
    Updates the cab's status to 'On Trip' (Dispatched) and generates a real-time notification
    using Groq's LLM capabilities.
    """
    state_df = get_current_state()
    executive = state_df.loc[trip_id, 'executive']
    flight_no = state_df.loc[trip_id, 'flight_no']
    city = state_df.loc[trip_id, 'destination_city']
    
    # 1. Update cab and trip status
    update_sim_data(
        new_trip_status={trip_id: 'Dispatching'},
        new_cab_loc={cab_reg_no: {'cab_status': 'On Trip'}}
    )
    
    # 2. Generate a notification using Groq
    prompt = f"""
    You are an Executive Travel AI Dispatcher. Write a professional, concise, and proactive
    message for the driver of cab {cab_reg_no} AND the executive ({executive}) for trip {trip_id}.
    The executive's flight, {flight_no}, has just landed in {city}.

    Generate the combined notification text.
    """
    
    try:
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",  # Fast and capable model
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        notification_message = response.choices[0].message.content
    except Exception as e:
        notification_message = f"ERROR: Could not generate LLM notification: {e}. CAB {cab_reg_no} DISPATCHED."

    add_to_log(f"DISPATCH: Cab {cab_reg_no} set to 'On Trip'. Trip {trip_id} status updated to 'Dispatching'.")
    return notification_message