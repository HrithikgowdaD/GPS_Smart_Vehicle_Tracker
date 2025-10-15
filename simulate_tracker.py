import requests
import sys
import time
import googlemaps

# 🚗 Get vehicle number from command line
if len(sys.argv) < 2:
    print("❌ Usage: python simulate_tracker.py <vehicle_no>")
    sys.exit(1)

vehicle_no = sys.argv[1]
print(f"📍 Starting tracker for vehicle: {vehicle_no}")

# ✅ Replace with your Flask server URL (ngrok or localhost)
SERVER_URL = "http://127.0.0.1:5000"

# ✅ Google Maps setup
API_KEY = "AIzaSyCBSyzLTpRbiD0qnQizzuaaqBgwqYme-6A"
gmaps = googlemaps.Client(key=API_KEY)

# ✅ Define a route for simulation (you can change)
start = "Kengeri, Bengaluru, Karnataka"
end = "Kushalnagar, Karnataka"

print(f"🛣️ Getting route from {start} → {end}...")
directions = gmaps.directions(start, end, mode="driving")

if not directions:
    print("❌ No route found.")
    sys.exit(1)

route = directions[0]['legs'][0]['steps']
total_points = sum(1 for step in route)
print(f"✅ Route loaded with {len(route)} segments.\n")

# ✅ Send each coordinate to your Flask API
for i, step in enumerate(route, start=1):
    start_lat = step['start_location']['lat']
    start_lng = step['start_location']['lng']
    end_lat = step['end_location']['lat']
    end_lng = step['end_location']['lng']
    road = step['html_instructions']

    data = {
        'vehicle_no': vehicle_no,
        'start_lat': start_lat,
        'start_lng': start_lng,
        'end_lat': end_lat,
        'end_lng': end_lng,
        'road_name': road
    }

    try:
        res = requests.post(f"{SERVER_URL}/update_location", json=data)
        if res.status_code == 200:
            print(f"✅ [{i}/{total_points}] Point sent: {road[:40]}...")
        else:
            print(f"⚠️ Server error ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Network error: {e}")

    time.sleep(1)  # simulate movement delay

print("🏁 Trip completed successfully!")
