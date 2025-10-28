# app.py
import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify, session
)
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit

# ---------- CONFIG ----------
app = Flask(__name__)
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/toll_dashboard")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change_this_secret")
socketio = SocketIO(app, cors_allowed_origins="*")
mongo = PyMongo(app)

# Collections
users_col = mongo.db.users
vehicles_col = mongo.db.vehicles
trips_col = mongo.db.trips
pings_col = mongo.db.live_pings

# ---------- HELPERS ----------
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first.", "warning")
                return redirect(url_for("home"))
            if role:
                user = users_col.find_one({"_id": session["user_id"]})
                if not user or user.get("role") != role:
                    flash("Unauthorized access.", "danger")
                    return redirect(url_for("home"))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ---------- ROUTES ----------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")
        role = "normal"

        if users_col.find_one({"email": email}):
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        user_doc = {
            "_id": email,  # using email as _id for simplicity
            "full_name": full_name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "phone": phone,
            "role": role,
            "created_at": datetime.utcnow()
        }
        users_col.insert_one(user_doc)
        flash("Registered successfully. Please sign in.", "success")
        return redirect(url_for("home"))
    return render_template("register.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    role_choice = request.form.get("role")  # "normal" or "developer"
    user = users_col.find_one({"_id": email})
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid credentials.", "danger")
        return redirect(url_for("home"))

    if role_choice == "developer" and user.get("role") != "developer":
        flash("You are not a developer user.", "danger")
        return redirect(url_for("home"))

    session["user_id"] = user["_id"]
    session["email"] = user["email"]
    session["role"] = user.get("role", "normal")
    flash(f"Welcome, {user.get('full_name')}!", "success")

    if session["role"] == "developer":
        return redirect(url_for("dev_dashboard"))
    else:
        return redirect(url_for("user_dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("home"))

# Vehicle registration (normal user)
@app.route("/vehicle/register", methods=["GET", "POST"])
@login_required()
def register_vehicle():
    if request.method == "POST":
        vehicle_no = request.form.get("vehicle_no")
        owner_name = request.form.get("owner_name")
        aadhar = request.form.get("aadhar")

        # Automatically use the logged-in user's phone
        user = users_col.find_one({"_id": session["user_id"]})
        phone = user.get("phone")

        # Check for duplicates
        if vehicles_col.find_one({"vehicle_no": vehicle_no}):
            flash("Vehicle already registered.", "warning")
            return redirect(url_for("register_vehicle"))

        # Create vehicle record
        vehicle_doc = {
            "vehicle_no": vehicle_no,
            "owner_name": owner_name,
            "phone": phone,  # auto-link user phone
            "aadhar": aadhar,
            "balance": 0.0,
            "created_at": datetime.utcnow()
        }
        vehicles_col.insert_one(vehicle_doc)
        flash("Vehicle registered successfully.", "success")
        return redirect(url_for("user_dashboard"))
    return render_template("vehicle_register.html")


# Normal user dashboard
@app.route("/user_dashboard")
@login_required(role="normal")
def user_dashboard():
    user = users_col.find_one({"_id": session["user_id"]})
    vehicles = list(vehicles_col.find({"phone": user.get("phone")})) or []
    vehicle_nos = [v["vehicle_no"] for v in vehicles]
    trips = list(trips_col.find({"vehicle_no": {"$in": vehicle_nos}}).sort("timestamp", -1))
    return render_template("user_dashboard.html", user=user, vehicles=vehicles, trips=trips)

# Developer dashboard
@app.route("/dev_dashboard")
@login_required(role="developer")
def dev_dashboard():
    total_vehicles = vehicles_col.count_documents({})
    total_trips = trips_col.count_documents({})
    highway_agg = trips_col.aggregate([{"$group": {"_id": None, "sum": {"$sum": "$highway_distance"}}}])
    highway_sum = 0.0
    try:
        highway_sum = next(highway_agg)["sum"] or 0.0
    except StopIteration:
        highway_sum = 0.0

    vehicles = list(vehicles_col.find().sort("created_at", -1))
    latest_pings = {}
    for p in pings_col.find():
        latest_pings[p["vehicle_no"]] = p

    return render_template("dev_dashboard.html",
                           total_vehicles=total_vehicles,
                           total_trips=total_trips,
                           highway_sum=round(highway_sum, 2),
                           vehicles=vehicles,
                           latest_pings=latest_pings,
                           google_maps_key=os.environ.get("AIzaSyCBSyzLTpRbiD0qnQizzuaaqBgwqYme-6A", ""))

# API: list vehicles (developer)
@app.route("/api/vehicles")
@login_required(role="developer")
def api_vehicles():
    vehicles = list(vehicles_col.find({}, {"_id": 0}))
    return jsonify(vehicles)

# API: accept trip logging (from simulate script)
@app.route("/api/track_and_log", methods=["POST"])
@login_required()
def api_track_and_log():
    data = request.get_json()
    vehicle_no = data.get("vehicle_no")
    trip_doc = {
        "vehicle_no": vehicle_no,
        "start_location": data.get("start_location"),
        "end_location": data.get("end_location"),
        "total_distance": float(data.get("total_distance", 0)),
        "highway_distance": float(data.get("highway_distance", 0)),
        "total_fare": float(data.get("total_fare", 0)),
        "timestamp": datetime.utcnow()
    }
    trips_col.insert_one(trip_doc)
    return jsonify({"status": "ok", "trip": trip_doc})

# API: receive live pings (open, used by simulate_tracker)
@app.route("/api/update_location", methods=["POST"])
def api_update_location():
    data = request.get_json()
    vehicle_no = data.get("vehicle_no")
    lat = float(data.get("start_lat"))
    lng = float(data.get("start_lng"))
    road_name = data.get("road_name", "")
    ping = {
        "vehicle_no": vehicle_no,
        "lat": lat,
        "lng": lng,
        "road_name": road_name,
        "timestamp": datetime.utcnow()
    }
    pings_col.update_one({"vehicle_no": vehicle_no}, {"$set": ping}, upsert=True)
    mongo.db.pings_log.insert_one(ping)
    # Broadcast to dashboard clients
    socketio.emit("location_update", {
        "vehicle_no": vehicle_no,
        "lat": lat,
        "lng": lng,
        "road_name": road_name,
        "timestamp": ping["timestamp"].isoformat()
    }, broadcast=True)
    return jsonify({"status": "success"})

# History page
@app.route("/history/<vehicle_no>")
@login_required()
def history(vehicle_no):
    history = list(trips_col.find({"vehicle_no": vehicle_no}).sort("timestamp", -1))
    return render_template("history.html", vehicle_no=vehicle_no, history=history)

# Wallet recharge
@app.route("/api/recharge", methods=["POST"])
@login_required()
def api_recharge():
    vehicle_no = request.form.get("vehicle_no")
    amount = float(request.form.get("amount", 0.0))
    vehicles_col.update_one({"vehicle_no": vehicle_no}, {"$inc": {"balance": amount}})
    flash("Recharged successfully.", "success")
    if session.get("role") == "developer":
        return redirect(url_for("dev_dashboard"))
    return redirect(url_for("user_dashboard"))

# Convenience: create developer user (only if none exists)
@app.route("/create_dev", methods=["POST"])
def create_dev():
    if users_col.count_documents({"role": "developer"}) > 0:
        return "Developer already exists. Disabled.", 403
    email = request.form.get("email")
    password = request.form.get("password")
    users_col.insert_one({
        "_id": email,
        "full_name": "Dev User",
        "email": email,
        "password_hash": generate_password_hash(password),
        "phone": request.form.get("phone", ""),
        "role": "developer",
        "created_at": datetime.utcnow()
    })
    return "Developer created."

# SocketIO events (optional logging)
@socketio.on("connect")
def handle_connect():
    print("Socket connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("Socket disconnected")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
