# dashboard_app.py
# ✅ Smart Toll System Dashboard with MongoDB + Socket.IO Live Map

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
from flask_socketio import SocketIO, emit

# ---------------- CONFIG ----------------
app = Flask(__name__)
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/toll_dashboard")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change_this_secret")

# ✅ Use threading mode to fix Flask-SocketIO blocking issues
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
mongo = PyMongo(app)

# MongoDB collections
users_col = mongo.db.users
vehicles_col = mongo.db.vehicles
trips_col = mongo.db.trips
pings_col = mongo.db.live_pings


# ---------------- HELPERS ----------------
def to_str_id(doc):
    """Convert MongoDB ObjectIds to strings recursively."""
    if isinstance(doc, list):
        return [to_str_id(x) for x in doc]
    if isinstance(doc, dict):
        new_doc = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                new_doc[k] = str(v)
            elif isinstance(v, (list, dict)):
                new_doc[k] = to_str_id(v)
            else:
                new_doc[k] = v
        return new_doc
    return doc


def login_required(role=None):
    """Decorator to protect routes."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first.", "warning")
                return redirect(url_for("home"))
            try:
                user_id = ObjectId(session["user_id"])
            except Exception:
                flash("Invalid session. Please log in again.", "danger")
                return redirect(url_for("logout"))

            user = users_col.find_one({"_id": user_id})
            if not user:
                flash("User not found.", "danger")
                return redirect(url_for("logout"))

            if role and user.get("role") != role:
                flash("Unauthorized access.", "danger")
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
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")

        if users_col.find_one({"email": email}):
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        users_col.insert_one({
            "full_name": full_name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "phone": phone,
            "role": "normal",
            "created_at": datetime.utcnow()
        })
        flash("Registered successfully! Please log in.", "success")
        return redirect(url_for("home"))
    return render_template("register.html")


# ---------- Login ----------
@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    role = request.form.get("role")

    user = users_col.find_one({"email": email})
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid credentials.", "danger")
        return redirect(url_for("home"))

    if role == "developer" and user.get("role") != "developer":
        flash("Unauthorized as developer.", "danger")
        return redirect(url_for("home"))

    session["user_id"] = str(user["_id"])
    session["email"] = user["email"]
    session["role"] = user.get("role", "normal")

    flash(f"Welcome, {user.get('full_name', user['email'])}!", "success")
    return redirect(url_for("dev_dashboard" if user["role"] == "developer" else "user_dashboard"))


# ---------- Logout ----------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


# ---------- Vehicle Registration ----------
# ---------- Vehicle Registration ----------
@app.route("/vehicle/register", methods=["GET", "POST"])
@login_required()
def register_vehicle():
    user = users_col.find_one({"_id": ObjectId(session["user_id"])})

    if request.method == "POST":
        vehicles = request.form.getlist("vehicle_no[]")
        owners = request.form.getlist("owner_name[]")
        aadhars = request.form.getlist("aadhar[]")
        phone = user.get("phone")

        # ✅ Ensure phone number consistency for all vehicles of this user
        for i, vehicle_no in enumerate(vehicles):
            if not vehicle_no.strip():
                continue

            # Prevent duplicate vehicle numbers
            if vehicles_col.find_one({"vehicle_no": vehicle_no}):
                flash(f"Vehicle {vehicle_no} already exists.", "warning")
                continue

            vehicles_col.insert_one({
                "vehicle_no": vehicle_no.strip().upper(),
                "owner_name": owners[i],
                "phone": phone,  # keep same phone for all vehicles of this user
                "aadhar": aadhars[i],
                "balance": 0.0,
                "created_at": datetime.utcnow()
            })

        flash("Vehicles registered successfully!", "success")
        return redirect(url_for("user_dashboard"))

    # ✅ FIXED: pass user to the template
    return render_template("vehicle_register.html", user=user)




# ---------- User Dashboard ----------
@app.route("/user_dashboard")
@login_required(role="normal")
def user_dashboard():
    user = users_col.find_one({"_id": ObjectId(session["user_id"])})
    vehicles = list(vehicles_col.find({"phone": user.get("phone")}))
    vehicle_nos = [v["vehicle_no"] for v in vehicles]
    trips = list(trips_col.find({"vehicle_no": {"$in": vehicle_nos}}).sort("timestamp", -1))

    total_balance = sum(v.get("balance", 0.0) for v in vehicles)
    total_distance = round(sum(t.get("total_distance", 0.0) for t in trips), 2)
    total_highway = round(sum(t.get("highway_distance", 0.0) for t in trips), 2)
    total_fare = round(sum(t.get("total_fare", 0.0) for t in trips), 2)

    return render_template(
        "user_dashboard.html",
        user=user,
        vehicles=vehicles,
        trips=trips,
        total_balance=total_balance,
        total_distance=total_distance,
        total_highway=total_highway,
        total_fare=total_fare
    )


# ---------- Trip History ----------
@app.route("/user/history/<vehicle_no>")
@login_required()
def user_history(vehicle_no):
    trips_data = trips_col.find({"vehicle_no": vehicle_no}).sort("timestamp", -1)
    trips = [{
        "date": t["timestamp"].strftime("%Y-%m-%d"),
        "time": t["timestamp"].strftime("%H:%M:%S"),
        "start": t.get("start_location", "Unknown"),
        "end": t.get("end_location", "Unknown"),
        "total_distance": round(t.get("total_distance", 0), 2),
        "highway_distance": round(t.get("highway_distance", 0), 2),
        "fare": round(t.get("total_fare", 0), 2)
    } for t in trips_data]
    return render_template("user_history.html", vehicle_no=vehicle_no, trips=trips)


# ---------- Developer Dashboard ----------
@app.route("/dev_dashboard")
@login_required(role="developer")
def dev_dashboard():
    total_vehicles = vehicles_col.count_documents({})
    total_trips = trips_col.count_documents({})
    total_highway_km = trips_col.aggregate([
        {"$group": {"_id": None, "sum": {"$sum": "$highway_distance"}}}
    ])
    try:
        highway_sum = next(total_highway_km)["sum"]
    except StopIteration:
        highway_sum = 0.0

    vehicles = list(vehicles_col.find().sort("created_at", -1))
    latest_pings = {p["vehicle_no"]: to_str_id(p) for p in pings_col.find()}
    return render_template(
        "dev_dashboard.html",
        total_vehicles=total_vehicles,
        total_trips=total_trips,
        highway_sum=round(highway_sum, 2),
        vehicles=to_str_id(vehicles),
        latest_pings=latest_pings
    )
# ---------- API: Per Vehicle Stats ----------
@app.route("/api/vehicle_stats/<vehicle_no>")
def api_vehicle_stats(vehicle_no):
    vehicle = vehicles_col.find_one({"vehicle_no": vehicle_no})
    if not vehicle:
        return jsonify({"error": "Vehicle not found"}), 404

    trips = list(trips_col.find({"vehicle_no": vehicle_no}))
    total_distance = round(sum(t.get("total_distance", 0) for t in trips), 2)
    total_highway = round(sum(t.get("highway_distance", 0) for t in trips), 2)
    total_fare = round(sum(t.get("total_fare", 0) for t in trips), 2)

    return jsonify({
        "vehicle_no": vehicle_no,
        "owner_name": vehicle.get("owner_name", ""),
        "balance": round(vehicle.get("balance", 0), 2),
        "total_trips": len(trips),
        "total_distance": total_distance,
        "total_highway": total_highway,
        "total_fare": total_fare
    })



# ---------- API: Update Location ----------
@app.route("/api/update_location", methods=["POST"])
def api_update_location():
    data = request.get_json()
    vehicle_no = data.get("vehicle_no")
    lat, lng = data.get("start_lat"), data.get("start_lng")
    road_name = data.get("road_name", "")

    if not vehicle_no or lat is None or lng is None:
        return jsonify({"error": "Missing parameters"}), 400

    ping = {
        "vehicle_no": vehicle_no,
        "lat": float(lat),
        "lng": float(lng),
        "road_name": road_name,
        "timestamp": datetime.utcnow()
    }
    pings_col.update_one({"vehicle_no": vehicle_no}, {"$set": ping}, upsert=True)

    # ✅ Emit live update to all browsers
    socketio.emit("location_update", to_str_id(ping), broadcast=True)
    print(f"📡 Emitted update for {vehicle_no}: {lat},{lng}")

    return jsonify({"status": "success"}), 200


# ---------- API: Log Trip ----------
@app.route("/api/track_and_log", methods=["POST"])
def api_track_and_log():
    data = request.get_json()
    trip = {
        "vehicle_no": data.get("vehicle_no"),
        "start_location": data.get("start_location"),
        "end_location": data.get("end_location"),
        "total_distance": float(data.get("total_distance", 0)),
        "highway_distance": float(data.get("highway_distance", 0)),
        "total_fare": float(data.get("total_fare", 0)),
        "timestamp": datetime.utcnow()
    }
    trips_col.insert_one(trip)
    vehicles_col.update_one({"vehicle_no": data.get("vehicle_no")}, {"$inc": {"balance": -trip["total_fare"]}})
    return jsonify({"status": "ok", "trip": to_str_id(trip)})


# ---------- SOCKET.IO ----------
@socketio.on("connect")
def handle_connect():
    print("🟢 Client connected to Socket.IO")

@socketio.on("disconnect")
def handle_disconnect():
    print("🔴 Client disconnected")


# ---------- RUN ----------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
