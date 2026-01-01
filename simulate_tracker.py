
import time
import requests
import googlemaps
from geopy.distance import geodesic

# ---------------- CONFIG ----------------
API_KEY = "AIzaSyDwHmT9VfKtdxVyvlO9FUCzbi87tpBWF6E"
gmaps = googlemaps.Client(key=API_KEY)

API_URL = "http://127.0.0.1:5000/api/update_location"
LOG_URL = "http://127.0.0.1:5000/api/track_and_log"

START = (12.9716, 77.5946)   # Bengaluru
END   = (11.1271, 78.6569)   # Mysuru

# ---------------- HELPERS ----------------
def get_route_points(start, end):
    """
    Fetch real road route from Google Directions API
    and return list of {lat, lng}
    """
    directions = gmaps.directions(
        start,
        end,
        mode="driving",
        alternatives=False
    )

    steps = directions[0]["legs"][0]["steps"]
    route = []

    for step in steps:
        route.append({
            "lat": step["start_location"]["lat"],
            "lng": step["start_location"]["lng"]
        })
        route.append({
            "lat": step["end_location"]["lat"],
            "lng": step["end_location"]["lng"]
        })

    return route


# ---------------- SIMULATOR ----------------
def simulate_vehicle(vehicle_no, delay=2):
    print(f"🚗 Simulating {vehicle_no} on REAL ROADS")

    # 🔥 IMPORTANT: fresh route for every run
    route_points = get_route_points(START, END)

    total_distance = 0.0
    highway_distance = 0.0
    last_point = None

    for point in route_points:
        current = (point["lat"], point["lng"])

        if last_point:
            dist = geodesic(last_point, current).km
            total_distance += dist

            # Basic highway heuristic (OK for now)
            road_type = "National Highway" if dist > 0.5 else "Local Road"
            if road_type == "National Highway":
                highway_distance += dist
        else:
            road_type = "Local Road"

        payload = {
            "vehicle_no": vehicle_no,
            "lat": point["lat"],
            "lng": point["lng"],
            "road_name": road_type
        }

        requests.post(API_URL, json=payload)
        print(f"📍 {road_type} @ {current}")

        last_point = current
        time.sleep(delay)

    # ✅ FINAL TRIP LOG (USED BY HISTORY)
    summary = {
        "vehicle_no": vehicle_no,
        "start_location": START,
        "end_location": END,
        "total_distance": total_distance,
        "highway_distance": highway_distance,
        "total_fare": highway_distance * 2.5,
        "route": route_points   # 🔥 CORRECT FORMAT
    }

    requests.post(LOG_URL, json=summary)
    print("✅ Trip logged successfully")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python simulate_tracker.py <VEHICLE_NO>")
    else:
        simulate_vehicle(sys.argv[1])



# import time
# import requests
# import googlemaps
# from geopy.distance import geodesic

# # ---------------- CONFIG ----------------
# API_KEY = "AIzaSyDwHmT9VfKtdxVyvlO9FUCzbi87tpBWF6E"  # same key you use in frontend
# gmaps = googlemaps.Client(key=API_KEY)

# API_URL = "http://127.0.0.1:5000/api/update_location"
# LOG_URL = "http://127.0.0.1:5000/api/track_and_log"

# START = (12.9716, 77.5946)   # Bengaluru
# END   = (22.2604, 84.8536)   # Odisha example


# route_points = []

# # ---------------- HELPERS ----------------
# def get_route_points(start, end):
#     """Fetch real road route from Google Directions API"""
#     directions = gmaps.directions(
#         start,
#         end,
#         mode="driving",
#         alternatives=False
#     )

#     steps = directions[0]["legs"][0]["steps"]

   
#     for step in steps:
#         start_loc = step["start_location"]
#         end_loc = step["end_location"]
#         route_points.append((start_loc["lat"], start_loc["lng"]))
#         route_points.append((end_loc["lat"], end_loc["lng"]))

#     return route_points


# # ---------------- SIMULATOR ----------------
# def simulate_vehicle(vehicle_no, delay=2):
#     print(f"🚗 Simulating {vehicle_no} on REAL ROADS")

#     route = get_route_points(START, END)

#     total_distance = 0.0
#     highway_distance = 0.0

#     last_point = None

#     for point in route:
#         if last_point:
#             dist = geodesic(last_point, point).km
#             total_distance += dist

#             # crude highway detection (can improve later)
#             road_type = "National Highway" if dist > 0.5 else "Local Road"
#             if road_type == "National Highway":
#                 highway_distance += dist
#         else:
#             road_type = "Local Road"

#         payload = {
#             "vehicle_no": vehicle_no,
#             "lat": point[0],
#             "lng": point[1],
#             "road_name": road_type
#         }

#         requests.post(API_URL, json=payload)
#         print(f"📍 {road_type} @ {point}")

#         last_point = point
#         time.sleep(delay)

#     # Trip summary
#     summary = {
#         "vehicle_no": vehicle_no,
#         "start_location": str(START),
#         "end_location": str(END),
#         "total_distance": total_distance,
#         "highway_distance": highway_distance,
#         "total_fare": highway_distance * 2.5,
#         "route": route_points
#     }

#     requests.post(LOG_URL, json=summary)
#     print("✅ Trip logged successfully")


# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) != 2:
#         print("Usage: python simulate_tracker.py <VEHICLE_NO>")
#     else:
#         simulate_vehicle(sys.argv[1])



# # # simulate_tracker.py
# # import time
# # import requests
# # from geopy.distance import geodesic

# # # MongoDB coordinates: Bengaluru → Mangalore (for testing)
# # START = (12.9716, 77.5946)
# # END = (22.2604, 84.8536)

# # route_points = []


# # API_URL = "http://127.0.0.1:5000/api/update_location"   # Flask endpoint
# # LOG_URL = "http://127.0.0.1:5000/api/track_and_log"     # Final trip log endpoint


# # def interpolate_coords(start, end, steps):
# #     """Generate intermediate coordinates from start → end."""
# #     lat1, lon1 = start
# #     lat2, lon2 = end
# #     return [
# #         (
# #             lat1 + (lat2 - lat1) * i / steps,
# #             lon1 + (lon2 - lon1) * i / steps
# #         )
# #         for i in range(steps + 1)
# #     ]


# # def simulate_vehicle(vehicle_no, total_steps=20, delay=2):
# #     """Simulate movement and send updates to Flask backend."""
# #     print(f"✅ Connected to MongoDB")
# #     print(f"🚗 Simulating {vehicle_no} from {START} → {END} ...")

# #     coords = interpolate_coords(START, END, total_steps)
# #     total_distance = 0.0
# #     highway_distance = 0.0
# #     total_fare = 0.0

# #     for i in range(1, len(coords)):
# #         start = coords[i - 1]
# #         end = coords[i]
# #         segment_km = geodesic(start, end).km
# #         total_distance += segment_km

# #         # Simple logic: if step index divisible by 3 → Highway
# #         if i % 3 == 0:
# #             road_name = "National Highway"
# #             highway_distance += segment_km
# #             total_fare += segment_km * 2.5  # ₹2.5/km
# #         else:
# #             road_name = "Local Road"
# #             total_fare += segment_km * 1.2  # ₹1.2/km

# #         print(f"🛣️ {road_name} ({total_distance:.2f} km total)")

# #         # 🔹 Send live update to Flask API
# #         payload = {
# #             "vehicle_no": vehicle_no,
# #             "lat": end[0],
# #             "lng": end[1],
# #             "road_name": road_name
# #         }

# #         try:
# #             requests.post(API_URL, json=payload, timeout=5)
# #         except Exception as e:
# #             print("❌ Failed to send:", e)

# #         time.sleep(delay)

# #     # ✅ Log the completed trip at the end
# #     trip_summary = {
# #         "vehicle_no": vehicle_no,
# #         "start_location": f"{START}",
# #         "end_location": f"{END}",
# #         "total_distance": total_distance,
# #         "highway_distance": highway_distance,
# #         "total_fare": total_fare,
# #     }
# #     requests.post(LOG_URL, json=trip_summary)
# #     print("✅ Trip logged successfully!")


# # if __name__ == "__main__":
# #     import sys
# #     if len(sys.argv) != 2:
# #         print("Usage: python simulate_tracker.py <VEHICLE_NO>")
# #     else:
# #         simulate_vehicle(sys.argv[1])
