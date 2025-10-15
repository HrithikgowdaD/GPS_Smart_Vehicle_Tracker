import requests, time, polyline

API_KEY = "AIzaSyCBSyzLTpRbiD0qnQizzuaaqBgwqYme-6A"
start = "Svce college, Bengaluru, Karnataka"
end = "Vinjamur,Andra Pradesh"

print(f"📍 Getting route from {start} → {end}...")

# Use new Routes API endpoint
url = f"https://maps.googleapis.com/maps/api/directions/json?origin={start}&destination={end}&mode=driving&key={API_KEY}"

response = requests.get(url)
data = response.json()

if "routes" not in data or not data["routes"]:
    print("❌ No route found or Directions API not enabled.")
    print("Response:", data)
    exit()

# Decode polyline to get points
points = polyline.decode(data["routes"][0]["overview_polyline"]["points"])
print(f"✅ Got {len(points)} points along the route.")

# Send to Flask server
for i, (lat, lng) in enumerate(points):
    print(f"🚗 Sending point {i+1}/{len(points)}: ({lat}, {lng})...")
    try:
        res = requests.post(
            "http://127.0.0.1:5000/update",
            json={"lat": lat, "lng": lng},
            timeout=10
        )
        print("✅ Response:", res.json())
    except Exception as e:
        print("❌ Error:", e)
    
    time.sleep(1)
