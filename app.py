from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import qrcode
import os
import googlemaps
from geopy.distance import distance
from datetime import datetime
import time


app = Flask(__name__)

# ------------ CONFIG ------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vehicles.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
gmaps = googlemaps.Client(key="AIzaSyCBSyzLTpRbiD0qnQizzuaaqBgwqYme-6A")

# ------------ DATABASE MODELS ------------
class RegisteredVehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_no = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    aadhar_number = db.Column(db.String(20), nullable=False)
    qr_code_path = db.Column(db.String(200), nullable=False)
    travels = db.relationship('TravelHistory', backref='vehicle', lazy=True)


class TravelHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('registered_vehicle.id'), nullable=False)
    start_location = db.Column(db.String(200))
    end_location = db.Column(db.String(200))
    total_distance = db.Column(db.Float)
    highway_distance = db.Column(db.Float)
    total_fare = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ------------ REGISTRATION ROUTE ------------
@app.route('/register', methods=['GET', 'POST'])
def register_vehicle():
    if request.method == 'POST':
        vehicle_no = request.form['vehicle_no']
        full_name = request.form['full_name']
        phone_number = request.form['phone_number']
        aadhar_number = request.form['aadhar_number']

        # Check duplicate
        existing = RegisteredVehicle.query.filter_by(vehicle_no=vehicle_no).first()
        if existing:
            return "⚠️ Vehicle already registered!"

        qr_folder = 'static/qr_codes'
        os.makedirs(qr_folder, exist_ok=True)
        qr_filename = f"{vehicle_no}.png"
        qr_path = os.path.join(qr_folder, qr_filename)

        qr = qrcode.make(f"Vehicle: {vehicle_no}")
        qr.save(qr_path)

        new_vehicle = RegisteredVehicle(
            vehicle_no=vehicle_no,
            full_name=full_name,
            phone_number=phone_number,
            aadhar_number=aadhar_number,
            qr_code_path=qr_path
        )
        db.session.add(new_vehicle)
        db.session.commit()
        return render_template('register_success.html', vehicle=new_vehicle)
    return render_template('register.html')

# ------------ TRACK VEHICLE (Simulated GPS Path) ------------
@app.route('/track/<vehicle_no>')
def track_vehicle(vehicle_no):
    vehicle = RegisteredVehicle.query.filter_by(vehicle_no=vehicle_no).first()
    if not vehicle:
        return "Vehicle not found!"

    start = "Kengeri, Bengaluru, Karnataka"
    end = "Kushalnagar, Karnataka"

    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={start}&destination={end}&mode=driving&key=YOUR_VALID_API_KEY"
    data = gmaps.directions(start, end, mode="driving")

    if not data:
        return jsonify({"error": "No route found."})

    route = data[0]['legs'][0]
    total_distance = route['distance']['value'] / 1000
    highway_distance = 0
    total_fare = 0

    # Simulate checking each step for "highway" in its name
    for step in route['steps']:
        road_name = step.get('html_instructions', '')
        step_distance = step['distance']['value'] / 1000
        if any(x in road_name.lower() for x in ["highway", "expressway", "nh", "sh"]):
            highway_distance += step_distance

    total_fare = round(highway_distance * 1.2, 2)

    # Log trip into DB
    trip = TravelHistory(
        vehicle_id=vehicle.id,
        start_location=start,
        end_location=end,
        total_distance=round(total_distance, 2),
        highway_distance=round(highway_distance, 2),
        total_fare=total_fare
    )
    db.session.add(trip)
    db.session.commit()

    return render_template('dashboard.html', vehicle=vehicle, trip=trip)

# ------------ VIEW HISTORY ------------
@app.route('/history/<vehicle_no>')
def vehicle_history(vehicle_no):
    vehicle = RegisteredVehicle.query.filter_by(vehicle_no=vehicle_no).first()
    if not vehicle:
        return "Vehicle not found!"
    history = TravelHistory.query.filter_by(vehicle_id=vehicle.id).all()
    return render_template('history.html', vehicle=vehicle, history=history)


@app.route('/track_select', methods=['POST'])
def track_select():
    vehicle_no = request.form['vehicle_no']
    return redirect(url_for('track_vehicle', vehicle_no=vehicle_no))


@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.get_json()
    vehicle_no = data.get('vehicle_no')
    start_lat = data.get('start_lat')
    start_lng = data.get('start_lng')
    end_lat = data.get('end_lat')
    end_lng = data.get('end_lng')
    road_name = data.get('road_name', 'Unknown')

    # ✅ Log update for debug
    print(f"📡 {vehicle_no} → {road_name} ({start_lat}, {start_lng})")

    # Here you could:
    # - Store current position in DB
    # - Update dashboard live using SocketIO (optional)
    # - Update highway/fare stats dynamically

    return jsonify({"status": "success", "vehicle": vehicle_no})



@app.route('/')
def home():
    vehicles = RegisteredVehicle.query.all()
    return render_template('home.html', vehicles=vehicles, datetime=datetime)


if __name__ == '__main__':
    app.run(debug=True)
