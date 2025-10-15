from flask import Flask, render_template, request, jsonify
import googlemaps
from geopy.distance import distance
import time
import csv
import os

app = Flask(__name__)

# 🔑 Replace with your valid API key
gmaps = googlemaps.Client(key="AIzaSyCBSyzLTpRbiD0qnQizzuaaqBgwqYme-6A")

# Global trackers
path_points = []
snapped_path = []
total_distance = 0.0
total_highway_distance = 0.0
total_fare = 0.0
last_timestamp = None
rate_per_km = 1.2
LOG_FILE = "trip_log.csv"


@app.route('/')
def index():
    return render_template('map.html')


@app.route('/update', methods=['POST'])
def update_location():
    global total_distance, total_highway_distance, total_fare, last_timestamp, snapped_path

    data = request.get_json()
    if not data or 'lat' not in data or 'lng' not in data:
        return jsonify({'error': 'Invalid JSON. Expected {"lat": <float>, "lng": <float>}'})

    lat, lng = float(data['lat']), float(data['lng'])
    path_points.append((lat, lng))

    try:
        # Snap latest segment to road
        if len(path_points) >= 2:
            snapped = gmaps.snap_to_roads(path_points[-2:], interpolate=True)
            new_snapped = [{'lat': p['location']['latitude'], 'lng': p['location']['longitude']} for p in snapped]
            for point in new_snapped:
                if not snapped_path or point != snapped_path[-1]:
                    snapped_path.append(point)
        else:
            snapped_path.append({'lat': lat, 'lng': lng})

        # Reverse geocode to detect highway
        reverse = gmaps.reverse_geocode((lat, lng))
        road_name = "Unknown Road"
        is_highway = False
        if reverse:
            addr = reverse[0].get('formatted_address', '')
            road_name = addr.split(',')[0]
            if any(k in addr.upper() for k in ['HIGHWAY', 'EXPRESSWAY', 'NH', 'SH']):
                is_highway = True

        # Distance calculation
        if len(snapped_path) >= 2:
            segment_distance = distance(
                (snapped_path[-2]['lat'], snapped_path[-2]['lng']),
                (snapped_path[-1]['lat'], snapped_path[-1]['lng'])
            ).km
        else:
            segment_distance = 0.0

        total_distance += segment_distance
        if is_highway:
            total_highway_distance += segment_distance
            total_fare += segment_distance * rate_per_km

        last_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # 📁 Log data to CSV
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "lat", "lng", "road_name", "is_highway", "segment_km", "total_km", "total_highway_km", "fare_rs"])

        with open(LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                last_timestamp, lat, lng, road_name, is_highway,
                round(segment_distance, 3), round(total_distance, 3),
                round(total_highway_distance, 3), round(total_fare, 2)
            ])

        return jsonify({
            'status': 'success',
            'lat': lat,
            'lng': lng,
            'road_name': road_name,
            'is_highway': is_highway,
            'segment_distance_km': round(segment_distance, 3),
            'total_distance_km': round(total_distance, 3),
            'total_highway_distance_km': round(total_highway_distance, 3),
            'total_fare_rs': round(total_fare, 2),
            'timestamp': last_timestamp
        })

    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/path')
def get_path():
    return jsonify(snapped_path)

@app.route('/stats')
def get_stats():
    """Return current distance, fare, and highway stats."""
    global total_distance, total_highway_distance, total_fare, last_timestamp
    return jsonify({
        'total_distance_km': round(total_distance, 3),
        'total_highway_distance_km': round(total_highway_distance, 3),
        'total_fare_rs': round(total_fare, 2),
        'timestamp': last_timestamp
    })



@app.route('/replay')
def replay_route():
    """Load previously logged route for replay."""
    if not os.path.exists(LOG_FILE):
        return jsonify({'error': 'No logged trip data found'})
    with open(LOG_FILE, 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    return jsonify(data)


if __name__ == '__main__':
    app.run(debug=True)
