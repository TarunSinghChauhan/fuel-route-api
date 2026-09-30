import json

TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fuel route</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<style>html,body,#map{height:100%;margin:0}
.box{position:absolute;z-index:1000;top:10px;right:10px;background:#fff;padding:10px 14px;
border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font:14px/1.4 system-ui,sans-serif;max-width:260px}</style>
</head><body><div id="map"></div><div class="box" id="box"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script>
const data = __DATA__;
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom: 18, attribution: '&copy; OpenStreetMap contributors'}).addTo(map);
const line = L.geoJSON(data.route.geometry, {style: {color: '#2563eb', weight: 5}}).addTo(map);
map.fitBounds(line.getBounds(), {padding: [30, 30]});
const pin = (ll, color, html) => L.circleMarker(ll, {radius: 9, color: '#fff', weight: 2,
  fillColor: color, fillOpacity: 1}).bindPopup(html).addTo(map);
pin([data.start.lat, data.start.lng], '#16a34a', '<b>Start</b><br>' + data.start.label);
pin([data.finish.lat, data.finish.lng], '#dc2626', '<b>Finish</b><br>' + data.finish.label);
data.fuel_stops.forEach(s => pin([s.lat, s.lng], '#f59e0b',
  `<b>#${s.order} ${s.name}</b><br>${s.city}, ${s.state}<br>mile ${s.mile_marker}<br>` +
  `${s.gallons} gal @ $${s.price_per_gallon}/gal = <b>$${s.cost}</b>`));
document.getElementById('box').innerHTML =
  `<b>${data.route.distance_miles} mi</b> &middot; ${data.route.duration_hours} h<br>` +
  `Fuel stops: ${data.fuel_stops.length}<br>Total fuel cost: <b>$${data.summary.total_fuel_cost}</b>`;
</script></body></html>"""


def render_map(payload):
    blob = json.dumps(payload).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", blob)
