# simulate_tracker.py
# ✅ FINAL – Realistic GPS tracker simulation
# ❌ No Google Directions API
# ✅ Designed to work PERFECTLY with frontend Directions-based road animation

import time
import requests
import math
from geopy.distance import geodesic

BASE_URL = "http://192.168.0.103:5000"
UPDATE_URL = f"{BASE_URL}/api/update_location"
LOG_URL = f"{BASE_URL}/api/track_and_log"

# Start & End
START = (12.9716, 77.5946)   # Bengaluru
END   = (22.2604, 84.8536)   # Destination

HIGHWAY_RATE = 2.5
CITY_RATE = 1.2


def generate_realistic_gps_route(start, end, points=900):
    lat1, lng1 = start
    lat2, lng2 = end
    route = []

    for i in range(points + 1):
        t = i / points
        lat = lat1 + (lat2 - lat1) * t
        lng = lng1 + (lng2 - lng1) * t

        # Micro GPS drift
        lat += 0.002 * math.sin(t * math.pi * 2)
        lng += 0.002 * math.cos(t * math.pi * 2)

        route.append((round(lat, 6), round(lng, 6)))

    return route


def simulate_vehicle(vehicle_no, delay=0.8):
    print("🚗 Starting realistic GPS tracker simulation")

    route = generate_realistic_gps_route(START, END)

    total_distance = 0.0
    highway_distance = 0.0
    total_fare = 0.0

    # ✅ STORE FULL ROUTE FOR HISTORY
    route_points = []

    for i in range(1, len(route)):
        prev = route[i - 1]
        curr = route[i]

        segment = geodesic(prev, curr).km
        total_distance += segment

        if i % 7 == 0:
            road = "National Highway"
            highway_distance += segment
            total_fare += segment * HIGHWAY_RATE
        else:
            road = "City Road"
            total_fare += segment * CITY_RATE

        payload = {
            "vehicle_no": vehicle_no,
            "lat": curr[0],
            "lng": curr[1],
            "road_name": road
        }

        # ✅ SAVE ROUTE POINT
        route_points.append({
            "lat": curr[0],
            "lng": curr[1]
        })

        try:
            requests.post(UPDATE_URL, json=payload, timeout=2)
        except Exception as e:
            print("⚠️ Network error:", e)

        print(f"📍 {road}: {curr[0]}, {curr[1]}")
        time.sleep(delay)

    # ✅ FINAL TRIP LOG (WITH ROUTE)
    try:
        requests.post(LOG_URL, json={
            "vehicle_no": vehicle_no,
            "start_location": str(START),
            "end_location": str(END),
            "total_distance": round(total_distance, 2),
            "highway_distance": round(highway_distance, 2),
            "total_fare": round(total_fare, 2),
            "route": route_points
        })
    except:
        pass

    print("✅ Trip completed successfully")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python simulate_tracker.py <VEHICLE_NO>")
    else:
        simulate_vehicle(sys.argv[1])