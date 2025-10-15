from flask import Flask, render_template, request, jsonify
import googlemaps
from geopy.distance import distance
import time

app = Flask(__name__)

# 🔑 Use your valid Google API key with billing enabled
gmaps = googlemaps.Client(key="AIzaSyCBSyzLTpRbiD0qnQizzuaaqBgwqYme-6A")

# Global variables
path_points = []          # Raw GPS points
snapped_path = []         # Points snapped to road
total_distance = 0.0
total_fare = 0.0
last_timestamp = None
rate_per_km = 1.2         # ₹1.2 per km (example)

@app.route('/')
def index():
    return render_template('map.html')


@app.route('/update', methods=['POST'])
def update_location():
    global total_distance, total_fare, last_timestamp, snapped_path

    # New global tracker for highway-only distance
    global total_highway_distance
    try:
        total_highway_distance
    except NameError:
        total_highway_distance = 0.0

    data = request.get_json()
    if not data or 'lat' not in data or 'lng' not in data:
        return jsonify({'error': 'Invalid JSON. Expected {"lat": <float>, "lng": <float>}'})

    lat = float(data['lat'])
    lng = float(data['lng'])
    path_points.append((lat, lng))

    try:
        # Snap only the latest segment for efficiency
        if len(path_points) >= 2:
            snapped = gmaps.snap_to_roads(path_points[-2:], interpolate=True)
            new_snapped = [
                {'lat': p['location']['latitude'], 'lng': p['location']['longitude']}
                for p in snapped
            ]
            for point in new_snapped:
                if not snapped_path or point != snapped_path[-1]:
                    snapped_path.append(point)
        else:
            snapped_path.append({'lat': lat, 'lng': lng})

        # Reverse geocode latest coordinate
        reverse = gmaps.reverse_geocode((lat, lng))
        road_name = "Unknown Road"
        is_highway = False

        if reverse:
            addr = reverse[0].get('formatted_address', '')
            road_name = addr.split(',')[0]
            # Detect highways generically (any type)
            if any(k in addr.upper() for k in ['HIGHWAY', 'EXPRESSWAY', 'NH', 'SH']):
                is_highway = True

        # Calculate incremental segment distance
        if len(snapped_path) >= 2:
            segment_distance = distance(
                (snapped_path[-2]['lat'], snapped_path[-2]['lng']),
                (snapped_path[-1]['lat'], snapped_path[-1]['lng'])
            ).km
        else:
            segment_distance = 0.0

        # Add to totals
        total_distance += segment_distance
        if is_highway:
            total_highway_distance += segment_distance
            total_fare += segment_distance * rate_per_km

        last_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        return jsonify({
            'status': 'success',
            'road_name': road_name,
            'is_highway': is_highway,
            'segment_distance_km': round(segment_distance, 3),
            'total_distance_km': round(total_distance, 3),
            'total_highway_distance_km': round(total_highway_distance, 3),
            'total_fare_rs': round(total_fare, 2),
            'timestamp': last_timestamp
        })

    except Exception as e:
        return jsonify({'error': f'Google API error: {e}'})




@app.route('/path')
def get_path():
    return jsonify(snapped_path)


if __name__ == '__main__':
    app.run(debug=True)
