# simulate_tracker.py
"""
Simulate a vehicle sending GPS pings to the Flask dashboard.
Usage:
    python simulate_tracker.py <vehicle_no> <start_location> <end_location>

Example:
    python simulate_tracker.py KA01AA0001 "Kengeri, Bengaluru" "Mysuru, Karnataka"
"""

import requests
import sys
import time
import googlemaps
import polyline

# ---------------- CONFIG ----------------
SERVER_URL = "http://127.0.0.1:5000"  # your Flask app
API_KEY = "AIzaSyCBSyzLTpRbiD0qnQizzuaaqBgwqYme-6A"  # replace or export as env var

if len(sys.argv) < 4:
    print("Usage: python simulate_tracker.py <vehicle_no> <start_location> <end_location>")
    sys.exit(1)

vehicle_no = sys.argv[1]
start = sys.argv[2]
end = sys.argv[3]

gmaps = googlemaps.Client(key=API_KEY)

print(f"🚗 Getting route from '{start}' → '{end}' ...")
directions = gmaps.directions(start, end, mode="driving")

if not directions:
    print("❌ No route found! Check your API key or locations.")
    sys.exit(1)

overview_polyline = directions[0]["overview_polyline"]["points"]
path_points = polyline.decode(overview_polyline)
print(f"✅ Route has {len(path_points)} points.")

# ---------------- SEND PINGS ----------------
for i, (lat, lng) in enumerate(path_points, start=1):
    payload = {
        "vehicle_no": vehicle_no,
        "start_lat": lat,
        "start_lng": lng,
        "road_name": f"Segment {i}"
    }

    try:
        r = requests.post(f"{SERVER_URL}/api/update_location", json=payload, timeout=10)
        if r.status_code == 200:
            print(f"📍 [{i}/{len(path_points)}] Sent ({lat:.5f}, {lng:.5f}) OK")
        else:
            print(f"⚠️ [{i}] Server error: {r.status_code}")
    except Exception as e:
        print(f"❌ Error sending ping: {e}")

    time.sleep(1.2)  # simulate ~1 second between pings

print("🏁 Simulation complete.")
