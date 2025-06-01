from flask import Flask, render_template, request
import pickle
from datetime import datetime

app = Flask(__name__)

with open("data/noyes_data.pkl", "rb") as f:
    snapshots = pickle.load(f)



def convert_snapshot(eta_list, snap_ts):
    snapshot = {
        "snap_ts": snap_ts.strftime("%Y-%m-%d %H:%M:%S"),
        "snap_date": snap_ts.strftime("%Y-%m-%d"),
        "snap_time": snap_ts.strftime("%H:%M"),
        "Howard": [],
        "Linden": [],
    }

    for eta in eta_list:
        direction = None
        if "Howard" in eta["stop_description"]:
            direction = "Howard"
        elif "Linden" in eta["stop_description"]:
            direction = "Linden"

        if direction and eta.get("arrival_time"):
            mins = (eta["arrival_time"] - snap_ts).total_seconds() / 60.0
            snapshot[direction].append({
                "minutes": round(mins),
                "type": "Live" if not eta["is_scheduled"] else "Scheduled",
                "run_number": eta["run_number"],
            })

    return snapshot

snapshots = [convert_snapshot(etas, snap_ts) for etas, snap_ts in snapshots]

def get_index_by_ts(target_ts):
    """Return index of snapshot closest to given timestamp string (from datetime-local input)."""
    try:
        target = datetime.strptime(target_ts, "%Y-%m-%dT%H:%M")
        times = [datetime.strptime(s["snap_ts"], "%Y-%m-%d %H:%M:%S") for s in snapshots]
        closest_idx = min(range(len(times)), key=lambda i: abs(times[i] - target))
        return closest_idx
    except Exception as e:
        print("Error parsing timestamp:", e)
        return 0


@app.route("/")
def index():
    if "ts" in request.args:
        i = get_index_by_ts(request.args["ts"])
    else:
        i = int(request.args.get("i", 0))
    i = max(0, min(i, len(snapshots) - 1))  # bounds check
    snapshot = snapshots[i]
    return render_template("index.html", snapshot=snapshot, index=i, total=len(snapshots))

if __name__ == "__main__":
    app.run(debug=True)
