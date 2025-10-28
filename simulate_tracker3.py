import time, requests, json

# Your Flask server URL
SERVER_URL = "http://127.0.0.1:5000"

# Vehicle to simulate
VEHICLE_NO = "KA50MC1234"

# Start and end coordinates
start = (12.9155, 77.4840)  # Kengeri, Bengaluru
end = (12.4570, 75.9580)    # Kushalnagar

print(f"🚗 Getting highway route for {VEHICLE_NO}...")

# 1️⃣ Get road route from OSRM
url = f"https://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"
res = requests.get(url)
data = res.json()

if "routes" not in data or not data["routes"]:
    print("❌ Could not fetch route.")
    exit()

route_coords = data["routes"][0]["geometry"]["coordinates"]
print(f"✅ Route received with {len(route_coords)} points.")

# 2️⃣ Send simulated live updates
for i, (lon, lat) in enumerate(route_coords):
    ping_data = {
        "vehicle_no": VEHICLE_NO,
        "start_lat": lat,
        "start_lng": lon,
        "road_name": "Highway",
    }
    try:
        requests.post(f"{SERVER_URL}/api/update_location", json=ping_data, timeout=5)
    except Exception as e:
        print("⚠️ Connection failed:", e)

    print(f"📍 {i+1}/{len(route_coords)} Sent location ({lat:.5f}, {lon:.5f})")
    time.sleep(0.7)  # Smooth movement speed

print("✅ Trip completed successfully.")
