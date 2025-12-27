# dashboard_app.py
# ✅ Smart Toll System Dashboard (FULLY WORKING)

import pkgutil, importlib.util
if not hasattr(pkgutil, "get_loader"):
    pkgutil.get_loader = importlib.util.find_spec

import os
from datetime import datetime
from functools import wraps
from bson import ObjectId
from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify, session
)
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO
import qrcode
from geopy.distance import geodesic
import razorpay




# ---------------- CONFIG ----------------
app = Flask(__name__)
app.config["MONGO_URI"] = (
    "mongodb+srv://GPS-Smart-Toll:GPSSMARTTOLL@gps-smarttoll.cowontb.mongodb.net/toll_dashboard?retryWrites=true&w=majority"
)
app.config["SECRET_KEY"] = "change_this_secret"

RAZORPAY_KEY_ID="rzp_test_R5GGG4tXm6F1KD"
RAZORPAY_KEY_SECRET="GLINKefe1fj8SuRkK2J5YMur"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
mongo = PyMongo()
mongo.init_app(app)

# ---------------- HARDWARE MAPPING ----------------
HARDWARE_VEHICLE_MAP = {
    "GPS_UNIT_001": "KA19MH8521"  # evaluator demo vehicle
}


print("Mongo DB:", mongo.db)    

# Access collections AFTER app init
users_col = mongo.db["users"]
vehicles_col = mongo.db["vehicles"]
trips_col = mongo.db["trips"]
pings_col = mongo.db["live_pings"]

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)





GOOGLE_MAPS_API_KEY = "AIzaSyDwHmT9VfKtdxVyvlO9FUCzbi87tpBWF6E"


# ---------------- HELPERS ----------------

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("home"))

            user = users_col.find_one({"_id": ObjectId(session["user_id"])})
            if not user:
                return redirect(url_for("logout"))

            if role and user.get("role") != role:
                return redirect(url_for("home"))

            return f(*args, **kwargs)
        return wrapped
    return decorator


# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("home.html")


# ---------- Register ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()

    if request.method == "POST":
        users_col.insert_one({
            "full_name": request.form["full_name"],
            "email": request.form["email"],
            "password_hash": generate_password_hash(request.form["password"]),
            "phone": request.form["phone"],
            "role": "normal",
            "created_at": datetime.utcnow()
        })
        flash("Registered successfully!", "success")
        return redirect(url_for("home"))

    return render_template("register.html")


# ---------- Login ----------
@app.route("/login", methods=["POST"])
def login():
    user = users_col.find_one({"email": request.form["email"]})
    if not user or not check_password_hash(user["password_hash"], request.form["password"]):
        flash("Invalid credentials", "danger")
        return redirect(url_for("home"))

    session["user_id"] = str(user["_id"])
    session["role"] = user["role"]
    return redirect(url_for("user_dashboard"))


# ---------- Logout ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ---------- Vehicle Registration ----------
@app.route("/vehicle/register", methods=["GET", "POST"])
@login_required()
def register_vehicle():
    user = users_col.find_one({"_id": ObjectId(session["user_id"])})

    if request.method == "POST":
        qr_dir = "static/qr"
        os.makedirs(qr_dir, exist_ok=True)

        for vno, owner, aadhaar in zip(
            request.form.getlist("vehicle_no[]"),
            request.form.getlist("owner_name[]"),
            request.form.getlist("aadhar[]")
        ):
            vno = vno.strip().upper()
            if vehicles_col.find_one({"vehicle_no": vno}):
                continue

            qr_path = f"{qr_dir}/{vno}.png"
            qrcode.make(f"http://192.168.0.103:5000/vehicle/{vno}").save(qr_path)

            vehicles_col.insert_one({
                "vehicle_no": vno,
                "owner_name": owner,
                "aadhar": aadhaar,
                "phone": user["phone"],
                "balance": 0.0,
                "qr_path": qr_path,
                "created_at": datetime.utcnow()
            })

        return redirect(url_for("user_dashboard"))

    return render_template("vehicle_register.html")


# ---------- Wallet ----------
@app.route("/wallet/add")
@login_required()
def wallet_add():
    user = users_col.find_one({"_id": ObjectId(session["user_id"])})
    vehicles = list(vehicles_col.find({"phone": user["phone"]}))
    return render_template("wallet_add.html", vehicles=vehicles)


@app.route("/wallet/submit", methods=["POST"])
@login_required()
def wallet_submit():
    vehicles_col.update_one(
        {"vehicle_no": request.form["vehicle_no"]},
        {"$inc": {"balance": float(request.form["amount"])}}
    )
    return redirect(url_for("user_dashboard"))

@app.route("/wallet/create-order", methods=["POST"])
@login_required()
def create_order():
    data = request.get_json()
    amount = int(float(data["amount"]) * 100)  # ₹ → paise
    vehicle_no = data["vehicle_no"]

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "amount": amount,
        "key": RAZORPAY_KEY_ID,
        "vehicle_no": vehicle_no
    })


@app.route("/wallet/verify", methods=["POST"])
@login_required()
def verify_payment():
    data = request.get_json()

    params_dict = {
        "razorpay_order_id": data["razorpay_order_id"],
        "razorpay_payment_id": data["razorpay_payment_id"],
        "razorpay_signature": data["razorpay_signature"]
    }

    try:
        razorpay_client.utility.verify_payment_signature(params_dict)
    except:
        return jsonify({"status": "failed"}), 400

    # ✅ Payment verified → update balance
    vehicles_col.update_one(
        {"vehicle_no": data["vehicle_no"]},
        {"$inc": {"balance": float(data["amount"])}}
    )

    return jsonify({"status": "success"})



# ---------- User Dashboard ----------
@app.route("/user_dashboard")
@login_required()
def user_dashboard():
    user = users_col.find_one({"_id": ObjectId(session["user_id"])})

    if user["role"] == "developer":
    # 🔥 Developer sees ALL vehicles
        vehicles = list(vehicles_col.find())
    else:
    # 👤 Normal user sees only their vehicles
        vehicles = list(vehicles_col.find({"phone": user["phone"]}))

    return render_template(
        "user_dashboard.html",
        user=user,
        vehicles=vehicles,
        google_api_key=GOOGLE_MAPS_API_KEY
    )


@app.route("/vehicle/delete/<vehicle_no>", methods=["POST"])
@login_required(role="developer")
def delete_vehicle(vehicle_no):
    vehicle_no = vehicle_no.upper()

    # Delete vehicle
    vehicles_col.delete_one({"vehicle_no": vehicle_no})

    # Delete related trips
    trips_col.delete_many({"vehicle_no": vehicle_no})

    # Delete live pings
    pings_col.delete_many({"vehicle_no": vehicle_no})

    flash(f"Vehicle {vehicle_no} deleted successfully.", "success")
    return redirect(url_for("user_dashboard"))


# ---------- Trip History ----------
@app.route("/user/history/<vehicle_no>")
@login_required()
def user_history(vehicle_no):
    trips = list(trips_col.find({"vehicle_no": vehicle_no}))
    return render_template("user_history.html", trips=trips, vehicle_no=vehicle_no)


# ---------- LIVE API ----------
# @app.route("/api/update_location", methods=["POST"])
# def api_update_location():
#     data = request.get_json()
#     pings_col.insert_one({
#     "vehicle_no": data["vehicle_no"],
#     "lat": data["lat"],
#     "lng": data["lng"],
#     "road_name": data.get("road_name"),
#     "timestamp": datetime.utcnow()
# })

#     socketio.emit("location_update", data)
#     return jsonify({"status": "ok"})

@app.route("/api/update_location", methods=["POST"])
def api_update_location():
    data = request.get_json()
    vehicle_no = data["vehicle_no"]

    pings_col.insert_one({
        "vehicle_no": vehicle_no,
        "lat": data["lat"],
        "lng": data["lng"],
        "timestamp": datetime.utcnow()
    })

    # 🔥 AUTO END TRIP CHECK
    if check_auto_trip_end(vehicle_no):
        process_trip(vehicle_no)

    socketio.emit("location_update", data)
    return jsonify({"status": "ok"})


@app.route("/api/hw/ping", methods=["POST"])
def hw_ping():
    data = request.get_json()

    device_id = data.get("device_id")
    lat = float(data.get("lat"))
    lng = float(data.get("lng"))

    vehicle_no = HARDWARE_VEHICLE_MAP.get(device_id)
    if not vehicle_no:
        return jsonify({"error": "Unknown device"}), 400

    ping = {
        "vehicle_no": vehicle_no,
        "lat": lat,
        "lng": lng,
        "timestamp": datetime.utcnow()
    }

    pings_col.insert_one(ping)

    # 🔥 Reuse your EXISTING auto-trip logic
    if check_auto_trip_end(vehicle_no):
        process_trip(vehicle_no)

    socketio.emit("location_update", ping)
    return jsonify({"status": "ok"})



# @app.route("/api/track_and_log", methods=["POST"])
# def track_and_log():
#     data = request.get_json()
#     trips_col.insert_one({
#         "vehicle_no": data["vehicle_no"],
#         "start_location": data["start_location"],
#         "end_location": data["end_location"],
#         "total_distance": data["total_distance"],
#         "highway_distance": data["highway_distance"],
#         "fare": data["total_fare"],
#         "route": data["route"],
#         "created_at": datetime.utcnow()
#     })
#     return jsonify({"status": "trip_saved"})
def process_trip(vehicle_no):
    pings = list(
        pings_col.find({"vehicle_no": vehicle_no}).sort("timestamp", 1)
    )

    if len(pings) < 2:
        return None

    total_distance = 0
    highway_distance = 0
    route = []

    for i in range(1, len(pings)):
        p1 = pings[i - 1]
        p2 = pings[i]

        dist = geodesic(
            (p1["lat"], p1["lng"]),
            (p2["lat"], p2["lng"])
        ).km

        total_distance += dist
        highway_distance += dist  # simplified

        route.append({
            "lat": p2["lat"],
            "lng": p2["lng"]
        })

    fare = round(highway_distance * 2.5, 2)

    trips_col.insert_one({
        "vehicle_no": vehicle_no,
        "total_distance": round(total_distance, 2),
        "highway_distance": round(highway_distance, 2),
        "fare": fare,
        "route": route,
        "created_at": datetime.utcnow()
    })

    vehicles_col.update_one(
        {"vehicle_no": vehicle_no},
        {"$inc": {"balance": -fare}}
    )

    pings_col.delete_many({"vehicle_no": vehicle_no})

    return fare


from datetime import timedelta

STOP_TIME_THRESHOLD = timedelta(minutes=5)
STOP_DISTANCE_THRESHOLD = 0.03  # km = 30 meters


def check_auto_trip_end(vehicle_no):
    pings = list(
        pings_col.find({"vehicle_no": vehicle_no})
        .sort("timestamp", -1)
        .limit(5)
    )

    if len(pings) < 2:
        return False

    # 1️⃣ Check time gap
    now = datetime.utcnow()
    last_ping_time = pings[0]["timestamp"]

    if now - last_ping_time > STOP_TIME_THRESHOLD:
        return True

    # 2️⃣ Check movement
    total_movement = 0
    for i in range(len(pings) - 1):
        p1 = pings[i]
        p2 = pings[i + 1]

        dist = geodesic(
            (p1["lat"], p1["lng"]),
            (p2["lat"], p2["lng"])
        ).km

        total_movement += dist

    if total_movement < STOP_DISTANCE_THRESHOLD:
        return True

    return False



@app.route("/api/track_and_log", methods=["POST"])
def track_and_log():
    data = request.get_json()
    vehicle_no = data["vehicle_no"]

    fare = process_trip(vehicle_no)

    if not fare:
        return jsonify({"error": "Not enough data"}), 400

    return jsonify({
        "status": "trip_completed",
        "fare": fare
    })




# ---------- QR SCAN VEHICLE PROFILE (FIXED) ----------
@app.route("/vehicle/<vehicle_no>")
def vehicle_profile(vehicle_no):
    vehicle = vehicles_col.find_one({"vehicle_no": vehicle_no.upper()})

    if not vehicle:
        return "<h3>Vehicle not found</h3>", 404

    aadhaar = vehicle.get("aadhar", "XXXX")
    masked = aadhaar[:4] + "-XXXX-XXXX"
    count = vehicles_col.count_documents({"phone": vehicle["phone"]})

    return f"""
    <html>
    <head>
      <meta name='viewport' content='width=device-width, initial-scale=1'>
      <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css' rel='stylesheet'>
    </head>
    <body class='bg-light'>
      <div class='container mt-4'>
        <div class='card p-4 shadow'>
          <h4>🚘 Vehicle Details</h4>
          <p><b>Vehicle:</b> {vehicle_no}</p>
          <p><b>Owner:</b> {vehicle["owner_name"]}</p>
          <p><b>Phone:</b> {vehicle["phone"]}</p>
          <p><b>Aadhaar:</b> {masked}</p>
          <p><b>Vehicles on this Phone:</b> {count}</p>
          <div class='alert alert-info'>Sensitive data protected</div>
        </div>
      </div>
    </body>
    </html>
    """


# ---------- SOCKET ----------
@socketio.on("connect")
def connect():
    print("Client connected")


@socketio.on("disconnect")
def disconnect():
    print("Client disconnected")


# ---------- RUN ----------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)