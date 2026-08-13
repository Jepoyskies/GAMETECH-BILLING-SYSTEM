<?php
// edit_nap.php
include 'header.php';
require 'database.php'; // must create a PDO instance in $conn

$message = '';
$error   = '';
$napbox_no = $nap_latitude = $nap_longitude = $marker_color = '';

// Check if an ID is provided to edit an existing entry
$id = isset($_GET['id']) ? (int)$_GET['id'] : null;

if ($id) {
    // Fetch existing data
    try {
        $stmt = $conn->prepare("SELECT * FROM napbox_mapping WHERE id = :id");
        $stmt->execute([':id' => $id]);
        $napbox = $stmt->fetch();

        if ($napbox) {
            $napbox_no     = $napbox['napbox_no'];
            $nap_latitude  = $napbox['nap_latitude'];
            $nap_longitude = $napbox['nap_longitude'];
            $marker_color  = $napbox['marker_color'];
        } else {
            $error = 'NAP Box not found.';
        }
    } catch (PDOException $e) {
        $error = 'Error fetching data: ' . $e->getMessage();
    }
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $napbox_no     = trim($_POST['napbox_no'] ?? '');
    $nap_latitude  = trim($_POST['nap_latitude'] ?? '');
    $nap_longitude = trim($_POST['nap_longitude'] ?? '');
    $marker_color  = trim($_POST['marker_color'] ?? 'red');

    if ($napbox_no === '' || $nap_latitude === '' || $nap_longitude === '') {
        $error = 'All fields are required.';
    } else {
        try {
            if ($id) {
                // Update existing record
                $stmt = $conn->prepare(
                    "UPDATE napbox_mapping 
                     SET napbox_no = :napbox_no, nap_latitude = :nap_latitude, nap_longitude = :nap_longitude, marker_color = :marker_color
                     WHERE id = :id"
                );

                $stmt->execute([
                    ':napbox_no'     => $napbox_no,
                    ':nap_latitude'  => $nap_latitude,
                    ':nap_longitude' => $nap_longitude,
                    ':marker_color'  => $marker_color,
                    ':id'            => $id,
                ]);

                $message = 'NAP Box mapping updated successfully.';
            }
        } catch (PDOException $e) {
            $error = 'Database error: ' . $e->getMessage();
        }
    }
}
?>

<!-- Page-specific content starts here -->
<main class="container py-4">
    <div class="row justify-content-center">
        <div class="col-12 col-lg-8 mb-4">
            <div class="card shadow-sm border-0">
                <div class="card-body">
                    <h5 class="card-title mb-3 text-center">Edit NAP Box Mapping</h5>

                    <?php if ($message): ?>
                        <div class="alert alert-success py-2">
                            <?php echo htmlspecialchars($message); ?>
                        </div>
                    <?php endif; ?>

                    <?php if ($error): ?>
                        <div class="alert alert-danger py-2">
                            <?php echo htmlspecialchars($error); ?>
                        </div>
                    <?php endif; ?>

                    <div class="mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <label class="form-label mb-0">Location</label>
                            <button type="button" class="btn btn-sm btn-outline-primary" id="btnLocate">
                                Use My Location
                            </button>
                        </div>
                        <div id="map" style="width: 100%; height: 350px; border-radius: 0.35rem; border: 1px solid #dee2e6;"></div>
                        <small class="text-muted">
                            Click on the map to place/move the pin, or use "Use My Location" to auto-detect.
                        </small>
                    </div>

                    <form method="post" action="">
                        <div class="mb-3">
                            <label for="napbox_no" class="form-label">NAP Box No</label>
                            <input
                                type="text"
                                class="form-control"
                                id="napbox_no"
                                name="napbox_no"
                                value="<?php echo htmlspecialchars($napbox_no); ?>"
                                required
                            >
                        </div>

                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="nap_latitude" class="form-label">NAP Latitude</label>
                                <input
                                    type="text"
                                    class="form-control"
                                    id="nap_latitude"
                                    name="nap_latitude"
                                    placeholder="e.g. -6.200000"
                                    value="<?php echo htmlspecialchars($nap_latitude); ?>"
                                    required
                                >
                            </div>

                            <div class="col-md-6 mb-3">
                                <label for="nap_longitude" class="form-label">NAP Longitude</label>
                                <input
                                    type="text"
                                    class="form-control"
                                    id="nap_longitude"
                                    name="nap_longitude"
                                    placeholder="e.g. 106.816666"
                                    value="<?php echo htmlspecialchars($nap_longitude); ?>"
                                    required
                                >
                            </div>
                        </div>

                        <!-- NEW: Color dropdown -->
                        <div class="mb-3">
                            <label for="marker_color" class="form-label">Marker Color</label>
                            <select
                                class="form-select"
                                id="marker_color"
                                name="marker_color"
                                required
                            >
                                <?php
                                $selectedColor = $marker_color ?? 'red';
                                ?>
                                <option value="red"   <?php echo $selectedColor === 'red'   ? 'selected' : ''; ?>>Red</option>
                                <option value="green" <?php echo $selectedColor === 'green' ? 'selected' : ''; ?>>Green</option>
                                <option value="violet" <?php echo $selectedColor === 'violet' ? 'selected' : ''; ?>>Violet</option>
                            </select>
                            <small class="text-muted">This color will be used for this NAP Box pin on the map.</small>
                        </div>

                        <button type="submit" class="btn btn-primary w-100">
                            Update NAP Box
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div><!-- /.row -->
</main>
<!-- Page-specific content ends -->

<?php include 'footer.php'; ?>

<!-- Leaflet CSS & JS -->
<link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
/>
<script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
></script>

<script>
document.addEventListener('DOMContentLoaded', function () {
    var defaultLat = <?php echo $nap_latitude ?: 8.483800; ?>;
    var defaultLng = <?php echo $nap_longitude ?: 124.626868; ?>;
    var defaultZoom = 13;

    var map = L.map('map').setView([defaultLat, defaultLng], defaultZoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    var marker = L.marker([defaultLat, defaultLng], {draggable: true}).addTo(map);
    marker.on('dragend', function (e) {
        var pos = e.target.getLatLng();
        updateInputs(pos.lat, pos.lng);
    });

    function updateInputs(lat, lng) {
        document.getElementById('nap_latitude').value  = lat.toFixed(6);
        document.getElementById('nap_longitude').value = lng.toFixed(6);
    }

    map.on('click', function (e) {
        marker.setLatLng([e.latlng.lat, e.latlng.lng]);
        updateInputs(e.latlng.lat, e.latlng.lng);
    });

    document.getElementById('btnLocate').addEventListener('click', function () {
        if (!navigator.geolocation) {
            alert('Geolocation is not supported by your browser.');
            return;
        }

        navigator.geolocation.getCurrentPosition(
            function (pos) {
                var lat = pos.coords.latitude;
                var lng = pos.coords.longitude;
                map.setView([lat, lng], 17);
                marker.setLatLng([lat, lng]);
                updateInputs(lat, lng);
            },
            function (err) {
                alert('Cannot get your location: ' + err.message);
            }
        );
    });
});
</script>
