// static/js/dev_dashboard.js
document.addEventListener("DOMContentLoaded", function() {
  const socket = io();

  // simple hashmap of markers
  let map;
  const markers = {};

  function initMap() {
    if (!window.google || !google.maps) {
      // try to load maps script if key available
      if (GOOGLE_MAPS_API_KEY) {
        const s = document.createElement('script');
        s.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}`;
        s.onload = () => {
          map = new google.maps.Map(document.getElementById('map'), {
            center: { lat: 12.9716, lng: 77.5946 },
            zoom: 7
          });
        };
        document.head.appendChild(s);
      } else {
        // fallback: create blank map area
        document.getElementById('map').innerHTML = "<div class='p-3'>No Google Maps API key set. Set GOOGLE_MAPS_API_KEY in env.</div>";
      }
    } else {
      map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 12.9716, lng: 77.5946 },
        zoom: 7
      });
    }
  }

  initMap();

  socket.on("location_update", (data) => {
    console.log("ping", data);
    const v = data.vehicle_no;
    const lat = parseFloat(data.lat), lng = parseFloat(data.lng);

    if (!map) return;

    const pos = { lat, lng };
    if (markers[v]) {
      markers[v].setPosition(pos);
    } else {
      markers[v] = new google.maps.Marker({
        position: pos,
        map: map,
        label: v.slice(0, 3)
      });
    }
    // center map on latest ping (optional)
    // map.panTo(pos);
  });
});
