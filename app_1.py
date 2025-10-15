from flask import Flask, render_template, request, jsonify
import googlemaps
from geopy.distance import distance
import time
import json

app = Flask(__name__)

# 🔑 Replace with your Google API key (make sure Roads API is enabled)
gmaps = googlemaps.Client(key="AIzaSyCBSyzLTpRbiD0qnQizzuaaqBgwqYme-6A")

path_points = []
snapped_path = []
total_distance = 0.0
total_fare = 0.0
last_timestamp = None
rate_per_km = 1.2  # ₹1.2 per km for highways


@app.route('/')
def index():
    return render_template('map.html')


@app.route('/update', methods=['POST'])
def update_location():
    global total_distance, total_fare, last_timestamp, snapped_path

    data = request.get_json()
    if not data or 'lat' not in data or 'lng' not in data:
        return jsonify({'error': 'Invalid JSON. Expected {"lat": <float>, "lng": <float>}'})

    lat = float(data['lat'])
    lng = float(data['lng'])
    path_points.append((lat, lng))

    try:
        # Snap multiple points to road to get full road shape
        if len(path_points) >= 2:
            snapped = gmaps.snap_to_roads(path_points, interpolate=True)
            snapped_path = [
                {'lat': p['location']['latitude'], 'lng': p['location']['longitude']}
                for p in snapped
            ]
        else:
            snapped_path = [{'lat': lat, 'lng': lng}]

        # Reverse geocode last point
        reverse = gmaps.reverse_geocode((lat, lng))
        road_name = "Unknown Road"
        is_highway = False
        if reverse:
            addr = reverse[0].get('formatted_address', '')
            road_name = addr.split(',')[0]
            if any(k in addr.upper() for k in ['HIGHWAY', 'NH', 'EXPRESSWAY']):
                is_highway = True

        # Distance calculation using snapped path
        total_distance = 0.0
        for i in range(1, len(snapped_path)):
            total_distance += distance(
                (snapped_path[i - 1]['lat'], snapped_path[i - 1]['lng']),
                (snapped_path[i]['lat'], snapped_path[i]['lng'])
            ).km

        total_fare = total_distance * rate_per_km if is_highway else 0
        last_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        return jsonify({
            'status': 'success',
            'snapped_path': snapped_path,
            'road_name': road_name,
            'is_highway': is_highway,
            'total_distance_km': round(total_distance, 3),
            'total_fare_rs': round(total_fare, 2),
            'timestamp': last_timestamp
        })

    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/path')
def get_path():
    return jsonify(snapped_path)


if __name__ == '__main__':
    app.run(debug=True)
