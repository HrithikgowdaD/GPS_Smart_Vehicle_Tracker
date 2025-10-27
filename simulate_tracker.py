# simulate_tracker.py  — upgraded version (auto logs trip summary)

import requests
import sys
import time
import googlemaps
import os

# ===================== CONFIG ===================== #
SERVER_URL = os.environ.get("SERVER_URL", "http://127.0.0.1:5000")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# ================================================== #
if len(sys.argv) < 2:
    print("Usage: python simulate_tracker.py <vehicle_no>")
    sys.exit(1)

vehicle_no = sys.argv[1]

if not GOOGLE_MAPS_API_KEY:
    print("❌ Missing Google Maps API key! Set it via environment variable:")
    print("   $env:GOOGLE_MAPS_API_KEY='YOUR_KEY'   (Windows PowerShell)")
    sys.exit(1)

gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Define your route (you can change start and end points)
start = "Kengeri, Bengaluru, Karnataka"
end = "Kushalnagar, Karnataka"

print(f"Getting route from {start} → {end} ...")
directions = gmaps.directions(start, end, mode="driving")

if not directions:
    print("No route found. Check your API key or billing settings.")
    sys.exit(1)

steps = directions[0]['legs'][0]['steps']
total_distance = directions[0]['legs'][0]['distance']['value'] / 1000  # in km
start_location = directions[0]['legs'][0]['start_address']
end_location = directions[0]['legs'][0]['end_address']

print(f"Total distance: {total_distance:.2f} km")
print("Sending live GPS updates to server...")

for i, step in enumerate(steps, start=1):
    payload = {
        "vehicle_no": vehicle_no,
        "start_lat": step['start_location']['lat'],
        "start_lng": step['start_location']['lng'],
        "end_lat": step['end_location']['lat'],
        "end_lng": step['end_location']['lng'],
        "road_name": step.get('html_instructions', 'unknown')
    }

    try:
        resp = requests.post(f"{SERVER_URL}/api/update_location", json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"[{i}/{len(steps)}] Ping sent.")
        else:
            print(f"Server responded with {resp.status_code}: {resp.text}")
    except Exception as e:
        print("Network error:", e)

    time.sleep(1)  # delay between pings

# ======= After simulation, auto-log a trip summary ======= #
print("\nSimulation complete. Logging trip to server...")

# Estimate highway distance (rough 80% of total for demo)
highway_distance = total_distance * 0.8
total_fare = round(highway_distance * 1.5, 2)  # e.g. ₹1.5 per km

trip_summary = {
    "vehicle_no": vehicle_no,
    "start_location": start_location,
    "end_location": end_location,
    "total_distance": round(total_distance, 2),
    "highway_distance": round(highway_distance, 2),
    "total_fare": total_fare
}

try:
    r = requests.post(f"{SERVER_URL}/api/track_and_log", json=trip_summary, timeout=10)
    if r.status_code == 200:
        print(f"✅ Trip logged successfully! ({start_location} → {end_location})")
        print(f"   Distance: {total_distance:.2f} km | Fare: ₹{total_fare}")
    else:
        print(f"❌ Failed to log trip. Server response: {r.status_code} {r.text}")
except Exception as e:
    print("❌ Error logging trip:", e)
