import os
import re
import pandas as pd
import pickle
from data_parser import CTATrainDataParser
from datetime import timedelta

data_parser = CTATrainDataParser()

# check if pickle file already exists
# Read all files inside sample_data directory
files = os.listdir('holdout_data')
days = {}
for file in files:
    print("Parsing file:", file)
    if file.endswith('.csv'):
        file_path = os.path.join('holdout_data', file)
        this_day = data_parser.parse_file(file_path)
        # Store the data for each day
        days[file] = this_day


rows = []
for day, data in days.items():
    for rec in data:
        snap_ts = rec["timestamp"].replace(tzinfo=None)
        for eta in rec["eta_entries"]:
            rows.append({
                "station_id":      eta["station_id"],
                "station_name":    eta["station_name"],
                "stop_description":eta["stop_description"],     # stpDe
                "destination_name":eta["destination_name"],     # destNm
                "is_scheduled":    eta["is_scheduled"],
                "pred_arr":        eta["arrival_time"],
                "run_number":     eta["run_number"],          # run
                "snap_ts":         snap_ts
            })
df = pd.DataFrame(rows).sort_values(["station_id", "pred_arr", "snap_ts"])


noyes_rows = []
for day, data in days.items():
    for rec in data:
        snap_ts = rec["timestamp"].replace(tzinfo=None)

        if rec["station_id"] != "40400":
            continue

        noyes_rows.append((rec["eta_entries"], snap_ts))

# sort the noyes_rows by snap_ts
noyes_rows.sort(key=lambda x: x[1])
print("Number of noyes rows:", len(noyes_rows))

# Save the DataFrame to a pickle file
#pickle_file = 'cta_train_data.pkl'
#with open(pickle_file, 'wb') as f:
#    pickle.dump(rows, f)
#print(f"Data saved to {pickle_file}")
# Save the noyes_rows to a pickle file
noyes_pickle_file = 'noyes_holdout.pkl'
with open(noyes_pickle_file, 'wb') as f:
    pickle.dump(noyes_rows, f)
print(f"Noyes data saved to {noyes_pickle_file}")