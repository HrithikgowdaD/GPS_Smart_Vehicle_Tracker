import requests
import random
import time

API_URL = "http://192.168.31.84:5000/api/hw/ping"
DEVICE_ID = "GPS_UNIT_001"

BASE_LAT = 13.0411
BASE_LNG = 77.4875

def random_location():
    return (
        BASE_LAT + random.uniform(-0.0003, 0.0003),
        BASE_LNG + random.uniform(-0.0003, 0.0003)
    )

print("🚀 Starting HW Ping Simulator (IP Mode)\n")

while True:
    lat, lng = random_location()

    payload = {
        "device_id": DEVICE_ID,
        "lat": lat,
        "lng": lng
    }

    try:
        res = requests.post(API_URL, json=payload, timeout=5)
        print(
            f"📡 Sent → {lat:.6f}, {lng:.6f} | "
            f"Status: {res.status_code} | Response: {res.text}"
        )
    except Exception as e:
        print("❌ ERROR:", e)

    time.sleep(5)
