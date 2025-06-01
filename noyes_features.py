import pickle
import pandas as pd
from datetime import datetime
from collections import deque
from datetime import timedelta

# Load noyes data from pickle file
noyes_pickle_file = 'pickled_data/cta_train_noyes_actual.pkl'
with open(noyes_pickle_file, 'rb') as f:
    noyes_data = pickle.load(f)
print("Loaded noyes data from pickle file.")

print(len(noyes_data), "snapshots loaded from pickle file.")

seen_live = set()   # (pred_arr, direction) to avoid rematching same live ETA
seen_sched = set()  # (sched_arr, direction) to avoid rematching same scheduled ETA
sched_queue = {
    "Howard": deque(),
    "Linden": deque()
}
matches = []
missed_scheduled = []
MAX_RELEVANT_MIN = 10.0  # or maybe 20.0 depending on tolerance
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
                
                # Accept this match
                minutes = eta.get("minutes_until_arrival", 0)
                actual_arr = snap_ts + timedelta(minutes=minutes)

                matches.append({
                    "direction": direction,
                    "scheduled_arr": sched["scheduled_arr"],
                    "actual_arr": actual_arr,
                    "first_seen": sched["first_seen"],
                    "delay_min": delay_min,
                    "run_number": eta["run_number"],
                })

                # Remove from queue
                del sched_queue[direction][i]
                break


df_match = pd.DataFrame(matches)
df_match["error_min"] = (df_match["actual_arr"] - df_match["scheduled_arr"]).dt.total_seconds() / 60.0
print(df_match[["direction", "run_number", "scheduled_arr", "actual_arr", "error_min"]].head())
# save the DataFrame to a csv file
output_file = 'matches/noyes_actual_matches_arrival_new.csv'
df_match.to_csv(output_file, index=False)
