# simulate_tracker.py
<<<<<<< HEAD
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
=======
import os, time, requests, math, sys
from random import uniform
from pymongo import MongoClient
from datetime import datetime

# =============== CONFIGURATION ===============
SERVER_URL = "http://127.0.0.1:5000"
FARE_PER_KM = 2.5  # ₹ per km
DB_NAME = "gps_tracker"

# MongoDB connection
try:
    client = MongoClient("mongodb://localhost:27017/")
    db = client[DB_NAME]
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    exit(1)

# =============== UTILITY FUNCTIONS ===============
def haversine(lat1, lon1, lat2, lon2):
    """Compute distance between two GPS points in km"""
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
>>>>>>> SIDHU/dashboard-upgrade

def is_highway(lat, lon):
    """Check if a given coordinate is on a highway"""
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&zoom=14&format=json"
    headers = {'User-Agent': 'SmartTollSystem/1.0'}
    try:
<<<<<<< HEAD
        r = requests.post(f"{SERVER_URL}/api/update_location", json=payload, timeout=10)
        if r.status_code == 200:
            print(f"📍 [{i}/{len(path_points)}] Sent ({lat:.5f}, {lng:.5f}) OK")
        else:
            print(f"⚠️ [{i}] Server error: {r.status_code}")
    except Exception as e:
        print(f"❌ Error sending ping: {e}")

    time.sleep(1.2)  # simulate ~1 second between pings

print("🏁 Simulation complete.")
=======
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        road_name = data.get('address', {}).get('road', '') or ''
        return any(word in road_name.lower() for word in ["highway", "expressway", "bypass", "nh", "ah"])
    except Exception:
        return False

def get_location_name(lat, lon):
    """Get readable address from lat/lon"""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        r = requests.get(url, headers={"User-Agent": "vehicle-simulator"})
        data = r.json()
        return data.get("display_name", f"{lat}, {lon}")
    except:
        return f"{lat}, {lon}"

# =============== MAIN SIMULATION ===============
def simulate_trip(vehicle_no):
    start = (12.9200, 77.5000)  # Kengeri, Bengaluru
    end = (12.4569, 75.9626)    # Kushalnagar
    steps = 20
    lat_step = (end[0] - start[0]) / steps
    lon_step = (end[1] - start[1]) / steps

    total_distance = 0
    highway_distance = 0
    prev = start

    print(f"🚗 Simulating {vehicle_no} from {start} → {end} ...")

    for i in range(steps + 1):
        lat = start[0] + i * lat_step + uniform(-0.002, 0.002)
        lon = start[1] + i * lon_step + uniform(-0.002, 0.002)
        dist = haversine(prev[0], prev[1], lat, lon)
        total_distance += dist

        # Detect if vehicle is on highway
        on_highway = is_highway(lat, lon)
        if on_highway:
            highway_distance += dist
            print(f"✅ On highway ({highway_distance:.2f} km total)")
        else:
            print(f"🛣️ Local road ({total_distance:.2f} km total)")

        # Send live update to dashboard backend
        try:
            requests.post(f"{SERVER_URL}/api/update_location", json={
                "vehicle_no": vehicle_no,
                "lat": lat,
                "lng": lon,
                "road_name": "highway" if on_highway else "local"
            })
        except Exception as e:
            print(f"⚠️ Ping failed: {e}")

        prev = (lat, lon)
        time.sleep(1)

    # ======= After trip ends =======
    total_fare = round(highway_distance * FARE_PER_KM, 2)

    # Get readable location names
    start_location = get_location_name(start[0], start[1])
    end_location = get_location_name(end[0], end[1])

    # ======= Log trip in MongoDB =======
    trip_record = {
        "vehicle_no": vehicle_no,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "start_location": start_location,
        "end_location": end_location,
        "total_distance": round(total_distance, 2),
        "highway_distance": round(highway_distance, 2),
        "total_fare": total_fare
    }
    db.trips.insert_one(trip_record)
    print(f"✅ Trip logged to MongoDB: {trip_record}")

    # ======= Also send to Flask backend (optional) =======
    try:
        requests.post(f"{SERVER_URL}/api/track_and_log", json=trip_record)
        print(f"💰 Trip ended: {highway_distance:.2f} km on highway → ₹{total_fare}")
    except Exception as e:
        print(f"❌ Failed to log trip via API: {e}")


# =============== MAIN ENTRY ===============
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python simulate_tracker.py <vehicle_no>")
        exit(1)
    simulate_trip(sys.argv[1])
>>>>>>> SIDHU/dashboard-upgrade
