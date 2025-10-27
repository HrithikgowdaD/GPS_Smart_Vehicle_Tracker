# dashboard_app.py
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

socketio = SocketIO(app, cors_allowed_origins="*")
mongo = PyMongo(app)

# convenience collections
users_col = mongo.db.users            # stores both normal & dev users
vehicles_col = mongo.db.vehicles      # registered vehicles
trips_col = mongo.db.trips            # travel history
pings_col = mongo.db.live_pings       # live GPS pings (latest positions / stream)

# ------------------ HELPERS ------------------
def to_str_id(doc):
    """Convert MongoDB ObjectId fields to strings recursively."""
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
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first.", "warning")
                return redirect(url_for("home"))

            # convert back to ObjectId for queries
            try:
                user_id = ObjectId(session["user_id"])
            except Exception:
                flash("Invalid session. Please log in again.", "danger")
                return redirect(url_for("logout"))

            user = users_col.find_one({"_id": user_id})
            if not user:
                flash("User not found. Please log in again.", "danger")
                return redirect(url_for("logout"))

            if role and user.get("role") != role:
                flash("Unauthorized access.", "danger")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ------------------ ROUTES ------------------
@app.route("/")
def home():
    return render_template("home.html")


# ---------- Register new 'normal' user ----------
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


# ---------- Login ----------
@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    role = request.form.get("role")  # "normal" or "developer"

    user = users_col.find_one({"email": email})
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid credentials.", "danger")
        return redirect(url_for("home"))

    if role == "developer" and user.get("role") != "developer":
        flash("You are not authorized as a developer.", "danger")
        return redirect(url_for("home"))

    # ✅ FIX: store only string ID, not raw ObjectId
    session["user_id"] = str(user["_id"])
    session["email"] = user["email"]
    session["role"] = user.get("role", "normal")

    flash(f"Welcome, {user.get('full_name', user['email'])}!", "success")

    if session["role"] == "developer":
        return redirect(url_for("dev_dashboard"))
    else:
        return redirect(url_for("user_dashboard"))


# ---------- Logout ----------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


# ---------- Register vehicle ----------
@app.route("/vehicle/register", methods=["GET", "POST"])
@login_required()
def register_vehicle():
    if request.method == "POST":
        vehicle_no = request.form.get("vehicle_no")
        owner_name = request.form.get("owner_name")
        phone = request.form.get("phone")
        aadhar = request.form.get("aadhar")

        if vehicles_col.find_one({"vehicle_no": vehicle_no}):
            flash("Vehicle already registered.", "warning")
            return redirect(url_for("register_vehicle"))

        vehicle_doc = {
            "vehicle_no": vehicle_no,
            "owner_name": owner_name,
            "phone": phone,
            "aadhar": aadhar,
            "balance": 0.0,
            "created_at": datetime.utcnow()
        }
        vehicles_col.insert_one(vehicle_doc)
        flash("Vehicle registered successfully.", "success")
        return redirect(url_for("user_dashboard"))
    return render_template("vehicle_register.html")


# ---------- User Dashboard ----------
@app.route("/user_dashboard")
@login_required(role="normal")
def user_dashboard():
    user_id = ObjectId(session["user_id"])
    user = users_col.find_one({"_id": user_id})
    vehicles = list(vehicles_col.find({"phone": user.get("phone")}))
    trips = list(trips_col.find({"vehicle_no": {"$in": [v["vehicle_no"] for v in vehicles]}}).sort("timestamp", -1))

    return render_template(
        "user_dashboard.html",
        user=to_str_id(user),
        vehicles=to_str_id(vehicles),
        trips=to_str_id(trips)
    )


# ---------- Developer Dashboard ----------
@app.route("/dev_dashboard")
@login_required(role="developer")
def dev_dashboard():
    total_vehicles = vehicles_col.count_documents({})
    total_trips = trips_col.count_documents({})
    total_highway_km = trips_col.aggregate([
        {"$group": {"_id": None, "sum": {"$sum": "$highway_distance"}}}
    ])
    highway_sum = 0.0
    try:
        highway_sum = next(total_highway_km)["sum"] or 0.0
    except StopIteration:
        pass

    vehicles = list(vehicles_col.find().sort("created_at", -1))
    latest_pings = {p["vehicle_no"]: to_str_id(p) for p in pings_col.find()}

    return render_template(
        "dev_dashboard.html",
        total_vehicles=total_vehicles,
        total_trips=total_trips,
        highway_sum=round(highway_sum, 2),
        vehicles=to_str_id(vehicles),
        latest_pings=latest_pings,
        google_maps_key=os.environ.get("GOOGLE_MAPS_API_KEY", "")
    )


# ---------- API: Vehicles ----------
@app.route("/api/vehicles")
@login_required(role="developer")
def api_vehicles():
    vehicles = list(vehicles_col.find({}, {"_id": 0}))
    return jsonify(vehicles)


# ---------- API: Track and Log ----------
@app.route("/api/track_and_log", methods=["POST"])
@login_required()
def api_track_and_log():
    data = request.get_json()
    trip_doc = {
        "vehicle_no": data.get("vehicle_no"),
        "start_location": data.get("start_location"),
        "end_location": data.get("end_location"),
        "total_distance": float(data.get("total_distance", 0)),
        "highway_distance": float(data.get("highway_distance", 0)),
        "total_fare": float(data.get("total_fare", 0)),
        "timestamp": datetime.utcnow()
    }
    trips_col.insert_one(trip_doc)
    return jsonify({"status": "ok", "trip": to_str_id(trip_doc)})


# ---------- API: Update Location ----------
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

    socketio.emit("location_update", {
        "vehicle_no": vehicle_no,
        "lat": lat,
        "lng": lng,
        "road_name": road_name,
        "timestamp": ping["timestamp"].isoformat()
    }, broadcast=True)

    return jsonify({"status": "success"})


# ---------- Vehicle History ----------
@app.route("/history/<vehicle_no>")
@login_required()
def history(vehicle_no):
    history = list(trips_col.find({"vehicle_no": vehicle_no}).sort("timestamp", -1))
    return render_template("history.html", vehicle_no=vehicle_no, history=to_str_id(history))


# ---------- Wallet Recharge ----------
@app.route("/api/recharge", methods=["POST"])
@login_required()
def api_recharge():
    vehicle_no = request.form.get("vehicle_no")
    amount = float(request.form.get("amount", 0.0))
    vehicles_col.update_one({"vehicle_no": vehicle_no}, {"$inc": {"balance": amount}})
    flash("Recharged successfully.", "success")
    return redirect(url_for("user_dashboard"))


# ---------- Developer Creation ----------
@app.route("/create_dev", methods=["POST"])
def create_dev():
    if users_col.count_documents({"role": "developer"}) > 0:
        return "Developer already exists. Disabled.", 403

    email = request.form.get("email")
    password = request.form.get("password")
    users_col.insert_one({
        "full_name": "Dev User",
        "email": email,
        "password_hash": generate_password_hash(password),
        "phone": request.form.get("phone", ""),
        "role": "developer",
        "created_at": datetime.utcnow()
    })
    return "Developer created."


# ---------- SOCKETIO ----------
@socketio.on("connect")
def handle_connect():
    print("Socket connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("Socket disconnected")


# ---------- RUN ----------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
