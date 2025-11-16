from langgraph.graph import StateGraph, END, START
from typing import TypedDict, Annotated, List, Tuple
from core.flight_tools import get_flight_status_sim, dispatch_cab_and_notify
from core.data import get_current_state, update_sim_data, add_to_log

# 1. Define the State
class TripState(TypedDict):
    """The state of the executive travel system for a single trip."""
    trip_id: int
    executive: str
    flight_no: str
    current_flight_status: str
    cab_reg_no: str
    llm_notification: str

# 2. Define the Nodes
def check_flight_status(state: TripState) -> TripState:
    """Node: Checks the flight status using the simulated API tool."""
    trip_id = state["trip_id"]
    flight_no = state["flight_no"]
    
    # Use the LangChain tool
    flight_update = get_flight_status_sim.invoke({"trip_id": trip_id, "flight_no": flight_no})
    
    # Update the state with the latest flight status
    state["current_flight_status"] = flight_update.current_status
    return state

def dispatch_cab(state: TripState) -> TripState:
    """Node: Dispatches the cab and generates the notification."""
    trip_id = state["trip_id"]
    cab_reg_no = state["cab_reg_no"]
    
    # Use the LangChain tool which also updates the cab status in the 'database'
    notification = dispatch_cab_and_notify.invoke({"trip_id": trip_id, "cab_reg_no": cab_reg_no})
    
    # Save the LLM-generated message to the state
    state["llm_notification"] = notification
    
    # The status in the DB is set to 'Dispatching' in the tool. We transition the graph to END.
    return state

# 3. Define the Edges/Conditions
def should_dispatch(state: TripState) -> str:
    """Conditional Edge: Decides whether to proceed to dispatch."""
    trips_df = get_current_state()
    # Only dispatch if the flight is 'Landed' AND the trip status is still 'En Route' (not already dispatched)
    if state["current_flight_status"] == 'Landed' and trips_df.loc[state['trip_id'], 'status'] == 'En Route':
        return "dispatch"
    return "monitor"


# 4. Build the Graph
def build_logistics_graph(trip_id: int):
    """Builds and compiles the graph for a single trip."""
    
    workflow = StateGraph(TripState)
    
    # Add Nodes
    workflow.add_node("monitor", check_flight_status)
    workflow.add_node("dispatch", dispatch_cab)
    
    # Add Edges
    workflow.add_edge(START, "monitor")
    workflow.add_edge("dispatch", END) # Task complete after dispatch/notification
    
    # Conditional Edge from Monitor
    workflow.add_conditional_edges(
        "monitor",
        should_dispatch,
        {
            "dispatch": "dispatch",
            "monitor": END, # If no dispatch is needed, the current graph run ends
        }
    )
    
    return workflow.compile()

# --- Graph Runner ---
def run_logistics_for_all_trips():
    """Iterates through all active trips and runs the logic for them."""
    trips_df = get_current_state()
    logs = []
    
    for trip_id, trip in trips_df.iterrows():
        # Only run the graph for trips that haven't been processed past dispatching
        if trip['status'] in ['En Route', 'Landed']:
            
            # Initial State for the graph
            initial_state = TripState(
                trip_id=trip_id,
                executive=trip['executive'],
                flight_no=trip['flight_no'],
                current_flight_status=trip['status'],
                cab_reg_no=trip['cab_reg_no'],
                llm_notification=""
            )
            
            # Run the graph
            graph = build_logistics_graph(trip_id)
            # The invoke result is an iterable that yields the final state
            
            # 1. Get the final dictionary from the stream
            final_result = list(graph.stream(initial_state))[-1] 
            
            # 2. CHECK THE KEY SAFELY before trying to access the notification
            if 'dispatch' in final_result:
                final_state = final_result['dispatch']
                
                if final_state and final_state.get("llm_notification"):
                    logs.append(f"AI Action: {final_state['llm_notification']}")
                
    return logs