<?php
// edit_customer.php


require 'database.php';
require 'log_system_action.php';
session_start(); // Start session at very top
$success = false;
$error = '';
$notification = $_SESSION['notification'] ?? '';
unset($_SESSION['notification']);


// --- Get Mikrotik Devices ---
$devices = $conn->query("SELECT device_name FROM mikrotik_devices ORDER BY device_name ASC")->fetchAll(PDO::FETCH_COLUMN);


// Fetch barangays
$barangays = [];
$barangay_query = $conn->query('SELECT id, name FROM barangays ORDER BY name ASC');
if ($barangay_query) {
    $barangays = $barangay_query->fetchAll(PDO::FETCH_ASSOC);
}




// --- Get customer ID ---
$customer_id = $_GET['id'] ?? $_POST['id'] ?? null;
if (!$customer_id) {
    die("Customer ID missing.");
}

// --- Fetch old data for logging & form population ---
$stmt = $conn->prepare("SELECT * FROM customers WHERE id = ?");
$stmt->execute([$customer_id]);
$old_data = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$old_data) {
    die("Customer not found.");
}

// --- Fetch dropdowns (statuses, plans, agents, account types) ---
try {
    $status_options = $conn->query("SELECT DISTINCT status FROM customers WHERE status IS NOT NULL AND status <> ''")->fetchAll(PDO::FETCH_COLUMN, 0);
    $plans = $conn->query("SELECT id, plan_name FROM service_plans ORDER BY plan_name ASC")->fetchAll(PDO::FETCH_ASSOC);
    $agents = $conn->query("SELECT id, name FROM agents ORDER BY name ASC")->fetchAll(PDO::FETCH_ASSOC);
    $account_types = $conn->query("SELECT type_name FROM account_type ORDER BY type_name ASC")->fetchAll(PDO::FETCH_COLUMN, 0);
} catch (PDOException $e) {
    $error = "Database error: " . $e->getMessage();
}

// --- Handle POST submission ---
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Gather and validate form data
    $username      = trim($_POST['username'] ?? '');
    $device_name   = trim($_POST['device_name'] ?? '');
    $full_name     = trim($_POST['full_name'] ?? '');
    $email         = trim($_POST['email'] ?? '');
    $phone_input   = trim($_POST['phone'] ?? '');
    $address       = trim($_POST['address'] ?? '');
    $agent         = trim($_POST['agent'] ?? '');
    $latitude      = trim($_POST['latitude'] ?? '');
    $longitude     = trim($_POST['longitude'] ?? '');
    $plan_name     = trim($_POST['plan_name'] ?? '');
    $status        = trim($_POST['status'] ?? '');
    $account_type  = trim($_POST['account_type'] ?? '');
    $mac_address   = $old_data['mac_address'] ?? '';
    $barangay_id = trim($_POST['barangay_id'] ?? '');
    $created_form_by = $old_data['created_form_by'] ?? ($_SESSION['username'] ?? 'system');


    
    // Phone logic
    $user_phone = preg_replace('/\D/', '', $phone_input);
    if (strlen($user_phone) === 10) {
        $phone = '63' . $user_phone;
    } else {
        $error = "Please enter a valid 10-digit mobile number (e.g. 9454261242)";
    }

    // Username uniqueness
    if (!$error && $username !== '') {
        $stmt = $conn->prepare("SELECT COUNT(*) FROM customers WHERE username = ? AND id != ?");
        $stmt->execute([$username, $customer_id]);
        if ($stmt->fetchColumn() > 0) {
            $error = "Username already exists, please choose another.";
        }
    }

    // Validate lat/lng
    $latitude = is_numeric($latitude) ? (float)$latitude : null;
    $longitude = is_numeric($longitude) ? (float)$longitude : null;

    $admin_username = $_SESSION['admin_username'] ?? 'admin';

    if (!$error) {

        try {
            // ✅ START TRANSACTION (important)
            $conn->beginTransaction();

            $adjusted_by_router = ($status === 'pull out') ? $admin_username : null;

            // ✅ UPDATE customers
            $stmt = $conn->prepare("
    UPDATE customers
    SET username=?, full_name=?, email=?, phone=?, address=?, agent=?, latitude=?, longitude=?, status=?, plan_name=?, adjusted_by_router=?, account_type=?, mac_address=?, created_form_by=?, device_name=?, barangay_id=?
    WHERE id=?
");



            $stmt->execute([
    $username, $full_name, $email, $phone, $address, $agent, $latitude, $longitude,
    $status, $plan_name, $adjusted_by_router, $account_type, $mac_address,
    $created_form_by, $device_name, $barangay_id, $customer_id
]);


            // ✅ UPDATE PPPoE USERS TABLE (NEW PART)
            if (!empty($username)) {
                $stmt = $conn->prepare("
                    UPDATE pppoe_users
                    SET device_name = ?
                    WHERE username = ?
                ");
                $stmt->execute([$device_name, $username]);
            }

            // ✅ Logging
            $changed_by = $_SESSION['username'] ?? 'system';
            $new_data = [
                'username' => $username,
                'device_name' => $device_name,
                'full_name' => $full_name,
                'email' => $email,
                'phone' => $phone,
                'address' => $address,
                'agent' => $agent,
                'latitude' => $latitude,
                'longitude' => $longitude,
                'status' => $status,
                'plan_name' => $plan_name,
                'adjusted_by_router' => $adjusted_by_router,
                'account_type' => $account_type,
                'mac_address' => $mac_address,
                'created_form_by' => $created_form_by
            ];

            log_system_action($conn, 'customers', $customer_id, 'update', $changed_by, $old_data, $new_data);

            // ✅ COMMIT
            $conn->commit();

            $_SESSION['notification'] = "Customer updated successfully!";
            header("Location: customers.php");
            exit();

        } catch (Exception $e) {
            $conn->rollBack();
            $error = "Update failed: " . $e->getMessage();
        }

    } else {
        // Repopulate form fields
        $old_data = [
            'username' => $username,
            'full_name' => $full_name,
            'email' => $email,
            'phone' => $phone_input,
            'address' => $address,
            'agent' => $agent,
            'latitude' => $latitude,
            'longitude' => $longitude,
            'status' => $status,
            'plan_name' => $plan_name,
            'adjusted_by_router' => ($status === 'pull out') ? $admin_username : '',
            'account_type' => $account_type,
            'mac_address' => $mac_address,
            'created_form_by' => $created_form_by
        ];
    }
}


// --- Fetch available PPPoE usernames for dropdown ---
$current_username = $old_data['username'] ?? '';
$available_usernames = [];
$stmt = $conn->prepare("
    SELECT p.username FROM pppoe_users p
    LEFT JOIN customers c ON p.username = c.username
    WHERE (c.username IS NULL OR p.username = ?)
    ORDER BY p.username ASC
");
$stmt->execute([$current_username]);
while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
    $available_usernames[] = $row['username'];
}
?>



<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Edit Customer</title>
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
    <style>
        form.card {
            background: #fff;
            border-radius: 12px;
            max-width: 500px;
            margin: 40px auto;
        }
        #map { height: 300px; border-radius: 8px; }
    </style>
</head>
<body>
<main class="container py-4">
    <h2 class="mb-4 text-center">Edit Customer</h2>
    <?php if ($notification): ?>
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            <?= htmlspecialchars($notification) ?>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    <?php endif; ?>
    <?php if ($error): ?>
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <?= htmlspecialchars($error) ?>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    <?php endif; ?>

    <form method="POST" class="card shadow p-4">
        <input type="hidden" name="id" value="<?= htmlspecialchars($customer_id) ?>">

        <div class="mb-3">
            <label for="username" class="form-label">Username (Mikrotik Pppoe Integrate)</label>
            <select id="username" name="username" class="form-select select2">
                <option value="">-- None / Blank --</option>
                <?php foreach ($available_usernames as $uname): ?>
                    <option value="<?= htmlspecialchars($uname) ?>" <?= (($uname ?? '') == ($old_data['username'] ?? '')) ? 'selected' : '' ?>>
                        <?= htmlspecialchars($uname) ?>
                    </option>
                <?php endforeach; ?>
            </select>
        </div>

        <script>
        $(document).ready(function() {
            $('#username').select2({
                placeholder: "-- None / Blank --",
                allowClear: true,
                width: '100%'
            });
        });
        </script>











<div class="mb-3">
    <label for="device_name" class="form-label">Mikrotik Device</label>
    <select id="device_name" name="device_name" class="form-select" required>
        <option value="">-- Select Device --</option>
        <?php foreach ($devices as $dev): ?>
            <option value="<?= htmlspecialchars($dev) ?>"
                <?= (isset($old_data['device_name']) && $old_data['device_name'] == $dev) ? 'selected' : '' ?>>
                <?= htmlspecialchars($dev) ?>
            </option>
        <?php endforeach; ?>
    </select>
</div>











        <div class="mb-3">
            <label for="full_name" class="form-label">Full Name</label>
            <input type="text" id="full_name" name="full_name" class="form-control" value="<?= htmlspecialchars($old_data['full_name'] ?? '') ?>" required>
        </div>

        <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input type="email" id="email" name="email" class="form-control" value="<?= htmlspecialchars($old_data['email'] ?? '') ?>" required>
        </div>

        <div class="mb-3">
            <label for="phone" class="form-label">Phone</label>
            <div class="input-group">
                <span class="input-group-text">63</span>
                <input type="text" id="phone" name="phone" maxlength="10" pattern="\d{10}" class="form-control"
                    value="<?= isset($old_data['phone']) ? htmlspecialchars(substr($old_data['phone'], 2)) : '' ?>">
            </div>
            <small class="text-muted">Enter the 10-digit mobile number (e.g. 9454261242)</small>
        </div>

        <div class="mb-3">
            <label for="address" class="form-label">Address</label>
            <textarea id="address" name="address" class="form-control" rows="2"><?= htmlspecialchars($old_data['address'] ?? '') ?></textarea>
        </div>






<div class="mb-3">
    <label for="barangay_id" class="form-label">Barangay</label>
    <select id="barangay_id" name="barangay_id" class="form-select" required>
        <option value="">-- Select Barangay --</option>
        <?php foreach ($barangays as $brgy): ?>
            <option value="<?= htmlspecialchars($brgy['id']) ?>"
                <?= (isset($old_data['barangay_id']) && $old_data['barangay_id'] == $brgy['id']) ? 'selected' : '' ?>>
                <?= htmlspecialchars($brgy['name']) ?>
            </option>
        <?php endforeach; ?>
    </select>
</div>







        <!-- AGENT DROPDOWN -->
        <div class="mb-3">
            <label for="agent" class="form-label">Agent</label>
            <select id="agent" name="agent" class="form-select" required>
                <option value="">-- Select Agent --</option>
                <?php foreach ($agents as $ag): ?>
                    <option value="<?= htmlspecialchars($ag['name']) ?>"
                        <?= ($old_data['agent'] ?? '') == $ag['name'] ? 'selected' : '' ?>>
                        <?= htmlspecialchars($ag['name']) ?>
                    </option>
                <?php endforeach; ?>
            </select>
        </div>

        <div class="mb-3">
            <label for="latitude" class="form-label">Latitude</label>
            <input type="text" id="latitude" name="latitude" class="form-control"
                   value="<?= htmlspecialchars($old_data['latitude'] ?? '') ?>" required>
        </div>
        <div class="mb-3">
            <label for="longitude" class="form-label">Longitude</label>
            <input type="text" id="longitude" name="longitude" class="form-control"
                   value="<?= htmlspecialchars($old_data['longitude'] ?? '') ?>" required>
        </div>
        <div class="mb-3">
            <label class="form-label d-block">Locate on Map</label>
            <div id="map" style="height: 300px;"></div>
            
            <small class="form-text text-muted">Click or drag the marker to update latitude and longitude.</small>
        </div>

        <div class="mb-3">
            <label for="plan_name" class="form-label">Service Plan</label>
            <select id="plan_name" name="plan_name" class="form-select" required>
                <option value="">-- Select Plan --</option>
                <?php foreach ($plans as $plan): ?>
                    <option value="<?= htmlspecialchars($plan['plan_name']) ?>" <?= (isset($old_data['plan_name']) && $old_data['plan_name'] == $plan['plan_name']) ? 'selected' : '' ?>>
                        <?= htmlspecialchars($plan['plan_name']) ?>
                    </option>
                <?php endforeach; ?>
            </select>
        </div>

        <!-- ACCOUNT TYPE DROPDOWN -->
        <div class="mb-3">
            <label for="account_type" class="form-label">Account Type</label>
            <select id="account_type" name="account_type" class="form-select" required>
                <option value="">-- Select Account Type --</option>
                <?php foreach ($account_types as $type): ?>
                    <option value="<?= htmlspecialchars($type) ?>" <?= (isset($old_data['account_type']) && $old_data['account_type'] == $type) ? 'selected' : '' ?>>
                        <?= htmlspecialchars($type) ?>
                    </option>
                <?php endforeach; ?>
            </select>
        </div>

        <div class="mb-3">
            <label for="status" class="form-label">Status</label>
            <select id="status" name="status" class="form-select">
                <option value="active" <?= (isset($old_data['status']) && $old_data['status'] == 'active') ? 'selected' : '' ?>>Active</option>
                <option value="pull out" <?= (isset($old_data['status']) && $old_data['status'] == 'pull out') ? 'selected' : '' ?>>Pull Out (router)</option>
                <?php foreach ($status_options as $opt):
                if ($opt !== 'active' && $opt !== 'pull out') : ?>
                    <option value="<?= htmlspecialchars($opt) ?>" <?= (isset($old_data['status']) && $old_data['status'] == $opt) ? 'selected' : '' ?>>
                        <?= htmlspecialchars($opt) ?>
                    </option>
                <?php endif; endforeach; ?>
            </select>
        </div>

        <div class="mb-3" id="adjusted_by_div" style="display: <?= (isset($old_data['status']) && $old_data['status'] == 'pull out') ? 'block' : 'none' ?>;">
           
        </div>

        <div class="d-flex justify-content-between">
            <a href="customers.php" class="btn btn-secondary">Back</a>
            <button type="submit" class="btn btn-primary">Update</button>
        </div>
    </form>
</main>

<?php include 'footer.php'; ?>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    // Map logic
    var latInput = document.getElementById('latitude');
    var lngInput = document.getElementById('longitude');
    var defaultLat = parseFloat(latInput.value) || 8.484442513139395;
    var defaultLng = parseFloat(lngInput.value) || 124.62420771108842;
    var map = L.map('map').setView([defaultLat, defaultLng], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
    var marker = L.marker([defaultLat, defaultLng], {draggable: true}).addTo(map);
    marker.on('dragend', function(e) {
        var position = marker.getLatLng();
        latInput.value = position.lat.toFixed(6);
        lngInput.value = position.lng.toFixed(6);
    });
    latInput.addEventListener('change', function() {
        var lat = parseFloat(latInput.value);
        var lng = parseFloat(lngInput.value);
        if (!isNaN(lat) && !isNaN(lng)) {
            marker.setLatLng([lat, lng]);
            map.setView([lat, lng]);
        }
    });
    lngInput.addEventListener('change', function() {
        var lat = parseFloat(latInput.value);
        var lng = parseFloat(lngInput.value);
        if (!isNaN(lat) && !isNaN(lng)) {
            marker.setLatLng([lat, lng]);
            map.setView([lat, lng]);
        }
    });
    map.on('click', function(e) {
        marker.setLatLng(e.latlng);
        latInput.value = e.latlng.lat.toFixed(6);
        lngInput.value = e.latlng.lng.toFixed(6);
    });
    document.getElementById('use-current-location').addEventListener('click', function() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function(position) {
                var lat = position.coords.latitude;
                var lng = position.coords.longitude;
                latInput.value = lat.toFixed(6);
                lngInput.value = lng.toFixed(6);
                marker.setLatLng([lat, lng]);
                map.setView([lat, lng], 16);
            }, function(error) {
                alert('Unable to get your location.');
            });
        } else {
            alert('Geolocation is not supported by your browser.');
        }
    });

    // Show/hide Adjusted By field
    var statusSelect = document.getElementById('status');
    var adjustedDiv = document.getElementById('adjusted_by_div');
    statusSelect.addEventListener('change', function() {
        if (this.value === 'pull out') {
            adjustedDiv.style.display = 'block';
            <?php if (isset($_SESSION['admin_username'])): ?>
            var adjustedByInput = adjustedDiv.querySelector('input');
            if (!adjustedByInput.value) {
                adjustedByInput.value = "<?= htmlspecialchars($_SESSION['admin_username']) ?>";
            }
            <?php endif; ?>
        } else {
            adjustedDiv.style.display = 'none';
            var adjustedByInput = adjustedDiv.querySelector('input');
            adjustedByInput.value = '';
        }
    });
});
</script>
</body>
</html>
