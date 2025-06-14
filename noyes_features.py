import pickle
import pandas as pd
from datetime import datetime
from collections import deque
from datetime import timedelta

# Load noyes data from pickle file
noyes_pickle_file = 'noyes_holdout.pkl'
with open(noyes_pickle_file, 'rb') as f:
    noyes_data = pickle.load(f)
print("Loaded noyes data from pickle file.")

print(len(noyes_data), "snapshots loaded from pickle file.")

snapshot_lookup = {}
for etas, snap_ts in noyes_data:
    snapshot_lookup[snap_ts] = etas  # we’ll use this later to get opposite direction live trains


seen_live = set()   # (pred_arr, direction) to avoid rematching same live ETA
seen_sched = set()  # (sched_arr, direction) to avoid rematching same scheduled ETA
sched_queue = {
    "Howard": deque(),
    "Linden": deque()
}
matches = []
missed_scheduled = []
MAX_RELEVANT_MIN = 10.0  # or maybe 20.0 depending on tolerance
MIN_RELEVANT_MIN = 1.0  # minimum delay to consider a match
current_day = None  # to track the current day of snapshots

for etas, snap_ts in noyes_data:
    snap_day = snap_ts.date()
    
    if current_day is None:
        current_day = snap_day
    
    elif snap_day != current_day:
        current_day = snap_day
        sched_queue = {"Howard": deque(), "Linden": deque()}
        seen_sched.clear()
        seen_live.clear()  # optional — depends if trains are truly unique per day
    
    
    for eta in etas:
        
        direction = "Howard" if "Howard" in eta["stop_description"] else (
                    "Linden" if "Linden" in eta["stop_description"] else None)
        if direction is None:
            print(f"Skipping ETA with unknown direction: {eta['stop_description']}")
            continue

        arrival_time = eta["arrival_time"]
        if not arrival_time:
            print(f"Skipping ETA with no arrival time: {eta}")
            continue

        # (A) scheduled rows go into stack
        if eta["is_scheduled"]:
            # make sure not to add the same scheduled ETA multiple times
            key = (direction, eta["run_number"])
            if key in seen_sched:
                continue
            
            seen_sched.add(key)
            sched_queue[direction].append({
                "scheduled_arr": arrival_time,
                "first_seen": snap_ts,
                "direction": direction,
                "run_number": eta["run_number"],
            })

        # (B) live ETAs try to pair with stack top (if not seen before)
        elif not eta["is_scheduled"]:
            key = (arrival_time, direction)
            if key in seen_live:
                continue
            seen_live.add(key)
            
            for i, sched in enumerate(sched_queue[direction]):
                if sched["run_number"] != eta["run_number"]:
                    continue  # wrong train, skip

                delay_min = (snap_ts - sched["scheduled_arr"]).total_seconds() / 60.0
                error_min = (arrival_time - sched["scheduled_arr"]).total_seconds() / 60.0

                if delay_min < 0:
                    continue  # live train is before this scheduled ETA → skip
                
                if error_min > MAX_RELEVANT_MIN:
                    continue  # scheduled ETA too old for this live arrival
                
                if error_min < MIN_RELEVANT_MIN:
                    continue
                # Accept this match
                minutes = eta.get("minutes_until_arrival", 0)
                actual_arr = snap_ts + timedelta(minutes=minutes)
                
                # Find opposite direction live trains at first_seen
                opposite = "Linden" if sched["direction"] == "Howard" else "Howard"
                opp_etas = snapshot_lookup.get(sched["first_seen"], [])
                opp_live_arrivals = []
                for opp_eta in opp_etas:
                    if (not opp_eta.get("is_scheduled")) and (opposite in opp_eta.get("stop_description", "")):
                        if opp_eta.get("arrival_time"):
                            mins = (opp_eta["arrival_time"] - sched["first_seen"]).total_seconds() / 60.0
                            opp_live_arrivals.append(round(mins, 2))

                matches.append({
                    "direction": direction,
                    "scheduled_arr": sched["scheduled_arr"],
                    "actual_arr": actual_arr,
                    "first_seen": sched["first_seen"],
                    "delay_min": delay_min,
                    "run_number": eta["run_number"],
                    "opp_dir_live_arrivals": opp_live_arrivals,
                })

                # Remove from queue
                del sched_queue[direction][i]
                break


df_match = pd.DataFrame(matches)
df_match["error_min"] = (df_match["actual_arr"] - df_match["scheduled_arr"]).dt.total_seconds() / 60.0
print(df_match[["direction", "run_number", "scheduled_arr", "actual_arr", "error_min"]].head())
# save the DataFrame to a csv file
output_file = 'matches/noyes_holdout.csv'
df_match.to_csv(output_file, index=False)
