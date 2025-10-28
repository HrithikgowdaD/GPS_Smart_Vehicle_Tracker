# simulate_tracker.py
import requests
import sys
import time
import googlemaps
import os

# usage: python simulate_tracker.py <vehicle_no>
if len(sys.argv) < 2:
    print("Usage: python simulate_tracker.py <vehicle_no>")
    sys.exit(1)

vehicle_no = sys.argv[1]
SERVER_URL = os.environ.get("SERVER_URL", "http://127.0.0.1:5000")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

start = "Kengeri, Bengaluru, Karnataka"
end = "Kushalnagar, Karnataka"

print(f"Getting route from {start} to {end}...")
directions = gmaps.directions(start, end, mode="driving")

if not directions:
    print("No route found")
    sys.exit(1)

steps = directions[0]['legs'][0]['steps']
print("Sending pings...")
for i, step in enumerate(steps, start=1):
    start_lat = step['start_location']['lat']
    start_lng = step['start_location']['lng']
    road = step.get('html_instructions', 'unknown')

    payload = {
        "vehicle_no": vehicle_no,
        "start_lat": start_lat,
        "start_lng": start_lng,
        "end_lat": step['end_location']['lat'],
        "end_lng": step['end_location']['lng'],
        "road_name": road
    }
    try:
        resp = requests.post(f"{SERVER_URL}/api/update_location", json=payload)
        if resp.status_code == 200:
            print(f"[{i}/{len(steps)}] ping sent.")
        else:
            print("Server error:", resp.status_code, resp.text)
    except Exception as e:
        print("Network error:", e)
    time.sleep(1)

print("Simulation complete.")
