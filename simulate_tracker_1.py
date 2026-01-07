import requests, time

# Coordinates (example: Bangalore central area)
coords = [
    (12.9716, 77.5946),
    (12.9730, 77.5970),
    (12.9755, 77.6005),
    (12.9780, 77.6040),
    (12.9810, 77.6080),
    (12.9850, 77.6125),
]

for i, (lat, lng) in enumerate(coords, start=1):
    print(f"📍 Sending point {i}: ({lat}, {lng})...")
    try:
        res = requests.post(
            "https://gps.hrithikgd.in/update",
            json={"lat": lat, "lng": lng},
            timeout=5
        )
        print("✅ Response:", res.json())
    except Exception as e:
        print("❌ Error:", e)
    
    # Wait 20 seconds between points (simulate real-time vehicle ping)
    time.sleep(20)
