<?php
include 'header.php';

// Load MikroTikManager + data ($napboxesJson, $customersJson, $devicesError, $errors)
require __DIR__ . '/MikrotikManager/MikrotikManager_geo_user_map.php';
?>

<style>
    #map-search-wrapper {
        margin-bottom: 1rem;
    }
    .leaflet-popup-content a.btn-view-mt {
        display: inline-block;
        width: 100%;
        text-align: center;
        font-weight: bold;
        color: #000;
        background-color: #ffc107;
        border: 2px solid #ff9800;
        border-radius: .25rem;
        box-shadow: 0 0 6px rgba(0,0,0,.3);
    }
    .leaflet-popup-content a.btn-view-mt:hover {
        background-color: #ffb300;
        border-color: #fb8c00;
        text-decoration: none;
        color: #000;
    }
    .leaflet-popup-content small.coord-info {
        display: block;
        margin-top: .35rem;
        font-size: .75rem;
        color: #555;
    }
    .save-status {
        font-size: 0.85rem;
    }
</style>

<main class="container py-4">
    <div class="col-12">
        <div class="card shadow-sm border-0">
            <h2 class="mb-0 fw-bold text-primary">
                <i class="fa-regular fa-address-book"></i> Geo Nap & Customer Map
            </h2>
            <br>
            <div class="card-body">
                <h5 class="card-title mb-3">NAP Boxes and Customer Locations</h5>
                <p class="card-text">
                    The map below shows:<br>
                    - <strong>Blue pins</strong>: Customers (username is active in MikroTik)<br>
                    - <strong>Black pins</strong>: Customers (username not active in MikroTik)<br>
                    - <strong>Violet pins</strong>: Gametech Relay Server<br>
                    - <strong>Green pins</strong>: LCP Splitter<br>
                    - <strong>Red pins</strong>: Mother LCP Nap<br>
                    Drag a pin to move it, then click <strong>Save Changes</strong> to store the new coordinates.
                    <br>
                    <a href="add_nap.php" class="btn btn-outline-secondary me-2" title="Add NAP"><i class="fa-regular fa-map"></i></a>
                    <a href="table_nap.php" class="btn btn-outline-secondary me-2" title="Table NAP"><i class="fa-solid fa-house"></i></a>
                </p>

                <?php if (!empty($devicesError)): ?>
                    <div class="alert alert-warning py-2">
                        <?= htmlspecialchars($devicesError, ENT_QUOTES, 'UTF-8') ?>
                    </div>
                <?php endif; ?>
                <?php if (!empty($errors)): ?>
                    <div class="alert alert-warning py-2">
                        <strong>MikroTik errors:</strong><br>
                        <?php foreach ($errors as $er): ?>
                            <?= htmlspecialchars($er, ENT_QUOTES, 'UTF-8') ?><br>
                        <?php endforeach; ?>
                    </div>
                <?php endif; ?>

                <div class="row align-items-center mb-3" id="map-search-wrapper">
                    <div class="col-md-9">
                        <div class="row g-2 align-items-center">
                            <div class="col-6 col-lg-7">
                                <input
                                    type="text"
                                    id="map-search-input"
                                    class="form-control"
                                    placeholder="Search by NAP, customer name, or username..."
                                >
                            </div>
                            <div class="col-3 col-lg-2 d-flex">
                                <button id="map-search-btn" class="btn btn-primary w-100">
                                    Search
                                </button>
                            </div>
                            <div class="col-3 col-lg-3 d-flex">
                                <button id="save-changes-btn" class="btn btn-success w-100">
                                    Save Changes
                                </button>
                            </div>
                            <div class="col-12 mt-1">
                                <small id="map-search-msg" class="text-muted"></small>
                                <span id="save-status" class="ms-2 save-status text-muted"></span>
                            </div>
                        </div>
                    </div>
                </div>

                <div id="map"
                     style="width: 100%; height: 500px; border-radius: .25rem; border: 1px solid #ddd;">
                </div>
            </div>
        </div>
    </div>
</main>

<link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
/>
<script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
></script>

<script>
const napboxes  = <?= $napboxesJson  ? $napboxesJson  : '[]' ?>;
const customers = <?= $customersJson ? $customersJson : '[]' ?>;

function computeCenterFromBoth(napArr, custArr) {
    const all = [];
    napArr.forEach(n => {
        if (n.nap_latitude && n.nap_longitude) {
            all.push({lat: parseFloat(n.nap_latitude), lng: parseFloat(n.nap_longitude)});
        }
    });
    custArr.forEach(c => {
        if (c.latitude && c.longitude) {
            all.push({lat: parseFloat(c.latitude), lng: parseFloat(c.longitude)});
        }
    });
    if (!all.length) return {lat: 0, lng: 0};
    let sumLat = 0, sumLng = 0;
    all.forEach(p => {
        sumLat += p.lat;
        sumLng += p.lng;
    });
    return {lat: sumLat / all.length, lng: sumLng / all.length};
}

document.addEventListener('DOMContentLoaded', function () {
    const center = computeCenterFromBoth(napboxes, customers);
    const hasAny = napboxes.length || customers.length;

    const map = L.map('map').setView([center.lat, center.lng], hasAny ? 10 : 2);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
    }).addTo(map);

    if (!hasAny) return;

    const allowedColors = ['red', 'blue', 'green', 'orange', 'yellow', 'violet', 'grey', 'black'];
    const napIconsByColor = {};

    function getNapIconByColor(color) {
        let c = (color || '').toLowerCase().trim();
        if (!allowedColors.includes(c)) {
            c = 'red';
        }
        if (!napIconsByColor[c]) {
            napIconsByColor[c] = new L.Icon({
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-' + c + '.png',
                shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
                iconSize:     [25, 41],
                iconAnchor:   [12, 41],
                popupAnchor:  [1, -34],
                shadowSize:   [41, 41]
            });
        }
        return napIconsByColor[c];
    }

    // Customer marker icons
    const blueIcon = new L.Icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
        iconSize:     [25, 41],
        iconAnchor:   [12, 41],
        popupAnchor:  [1, -34],
        shadowSize:   [41, 41]
    });
    const blackIcon = new L.Icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-black.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
        iconSize:     [25, 41],
        iconAnchor:   [12, 41],
        popupAnchor:  [1, -34],
        shadowSize:   [41, 41]
    });

    const bounds  = [];
    const markers = [];
    const dirty   = {};

    function makeDirtyKey(type, id) {
        return type + ':' + id;
    }

    // --- NAP BOX MARKERS (DRAGGABLE) ---
    napboxes.forEach(n => {
        const lat = parseFloat(n.nap_latitude);
        const lng = parseFloat(n.nap_longitude);
        if (isNaN(lat) || isNaN(lng)) return;

        const icon = getNapIconByColor(n.marker_color);
        const marker = L.marker([lat, lng], {
            icon,
            draggable: true
        }).addTo(map);

        const popupHtml = (latNow, lngNow) =>
            '<strong>NAP: ' + (n.napbox_no || '-') + '</strong><br>' +
            'Lat: ' + latNow.toFixed(6) + '<br>' +
            'Lng: ' + lngNow.toFixed(6) + '<br>' +
            'Color: ' + (n.marker_color || 'default (red)') +
            '<small class="coord-info">(Drag pin to change position, then click "Save Changes")</small>';

        marker.bindPopup(popupHtml(lat, lng));

        marker.on('dragend', function (e) {
            const newPos = e.target.getLatLng();
            const newLat = newPos.lat;
            const newLng = newPos.lng;

            dirty[makeDirtyKey('nap', n.id)] = {
                type: 'nap',
                id: n.id,
                lat: newLat,
                lng: newLng
            };

            marker.setPopupContent(popupHtml(newLat, newLng));

            document.getElementById('save-status').textContent =
                'You have unsaved changes.';
        });

        markers.push({
            type: 'nap',
            marker,
            data: n,
            lat,
            lng
        });

        bounds.push([lat, lng]);
    });

    // --- CUSTOMER MARKERS (DRAGGABLE, color by Mikrotik active username match) ---
    customers.forEach(c => {
        const lat = parseFloat(c.latitude);
        const lng = parseFloat(c.longitude);
        if (isNaN(lat) || isNaN(lng)) return;

        // is_connected sent from PHP (1 if username is in Mikrotik active list)
        const isConnected = (String(c.is_connected) === '1');

        const icon = isConnected ? blueIcon : blackIcon;

        const marker = L.marker([lat, lng], {
            icon,
            draggable: true
        }).addTo(map);

        const detailUrl = 'user_view.php?id=' + encodeURIComponent(c.id);

        const popupHtml = (latNow, lngNow) =>
            '<strong>' + (c.full_name || 'Unknown') + '</strong><br>' +
            'Username: ' + (c.username || '-') + '<br>' +
            'Lat: ' + latNow.toFixed(6) + '<br>' +
            'Lng: ' + lngNow.toFixed(6) + '<br>' +
            '<span>Status: <b>' + (isConnected ? 'Connected (active in MikroTik)' : 'Not Active in MikroTik') + '</b></span><br>' +
            '<a href="' + detailUrl + '" class="btn-view-mt mt-2">➡ View Mikrotik Details</a>' +
            '<small class="coord-info">(Drag pin to change position, then click "Save Changes")</small>';

        marker.bindPopup(popupHtml(lat, lng));

        marker.on('dblclick', function () {
            window.location.href = detailUrl;
        });

        marker.on('dragend', function (e) {
            const newPos = e.target.getLatLng();
            const newLat = newPos.lat;
            const newLng = newPos.lng;

            dirty[makeDirtyKey('customer', c.id)] = {
                type: 'customer',
                id: c.id,
                lat: newLat,
                lng: newLng
            };

            marker.setPopupContent(popupHtml(newLat, newLng));

            document.getElementById('save-status').textContent =
                'You have unsaved changes.';
        });

        markers.push({
            type: 'customer',
            marker,
            data: c,
            lat,
            lng
        });

        bounds.push([lat, lng]);
    });

    if (bounds.length > 1) {
        map.fitBounds(bounds, {padding: [30, 30]});
    }

    // --- SEARCH LOGIC ---
    const searchInput = document.getElementById('map-search-input');
    const searchBtn   = document.getElementById('map-search-btn');
    const searchMsg   = document.getElementById('map-search-msg');

    function runSearch() {
        const q = (searchInput.value || '').trim().toLowerCase();
        searchMsg.textContent = '';

        if (!q) {
            searchMsg.textContent =
                'Type NAP, customer name, or username to search.';
            return;
        }

        let match = markers.find(m => {
            if (m.type !== 'customer') return false;
            const name = (m.data.full_name || '').toLowerCase();
            const user = (m.data.username || '').toLowerCase();
            return name.includes(q) || user.includes(q);
        });

        if (!match) {
            match = markers.find(m => {
                if (m.type !== 'nap') return false;
                const nb = (m.data.napbox_no || '').toLowerCase();
                return nb.includes(q);
            });
        }

        if (!match) {
            searchMsg.textContent = 'No matching record found.';
            return;
        }

        map.setView([match.lat, match.lng], 15);
        match.marker.openPopup();

        if (match.type === 'customer') {
            searchMsg.textContent = 'Showing customer: ' +
                (match.data.full_name || match.data.username || 'Unknown');
        } else {
            searchMsg.textContent = 'Showing NAP: ' +
                (match.data.napbox_no || '-');
        }
    }

    searchBtn.addEventListener('click', runSearch);
    searchInput.addEventListener('keyup', function (e) {
        if (e.key === 'Enter') runSearch();
    });

    // --- SAVE CHANGES (AJAX) ---
    const saveBtn    = document.getElementById('save-changes-btn');
    const saveStatus = document.getElementById('save-status');

    saveBtn.addEventListener('click', function () {
        const changes = Object.values(dirty);
        if (!changes.length) {
            saveStatus.textContent = 'No changes to save.';
            return;
        }

        if (!confirm('Are you sure you want to save the changes?')) {
            return;
        }

        saveStatus.textContent = 'Saving...';

        fetch('save_marker_positions.php', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(changes)
        })
        .then(res => res.json())
        .then(data => {
            if (data && data.success) {
                for (const k in dirty) {
                    if (Object.hasOwn(dirty, k)) delete dirty[k];
                }
                saveStatus.textContent = 'Changes saved successfully.';
            } else {
                saveStatus.textContent = data && data.message
                    ? 'Error: ' + data.message
                    : 'Error saving changes.';
            }
        })
        .catch(err => {
            console.error(err);
            saveStatus.textContent = 'Error saving changes (network/server).';
        });
    });
});
</script>

<?php include 'footer.php'; ?>
