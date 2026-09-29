<?php

require_once __DIR__ . '/MikrotikManager/MikrotikManager_add_customer_pppoe.php';
require __DIR__ . '/database.php';
require __DIR__ . '/log_system_action.php';
include 'header.php';

// LOGIN CHECK BEFORE ANY OUTPUT
if (!isset($_SESSION['username'])) {
    header('Location: login.php');
    exit;
}
$currentUser = $_SESSION['username'];

date_default_timezone_set('Asia/Manila');

// Fetch plans
$plans = [];
$plan_query = $pdo->query('SELECT plan_name FROM service_plans ORDER BY plan_name ASC');
if ($plan_query) {
    $plans = $plan_query->fetchAll(PDO::FETCH_COLUMN);
}

// Fetch MikroTik devices
$devices = [];
$device_query = $pdo->query(
    'SELECT id, device_name, ip_address, api_username, api_password, api_port
     FROM mikrotik_devices
     ORDER BY device_name ASC'
);
if ($device_query) {
    $devices = $device_query->fetchAll(PDO::FETCH_ASSOC);
}

// Fetch agents
$agents = [];
$agent_query = $pdo->query('SELECT name FROM agents ORDER BY name ASC');
if ($agent_query) {
    $agents = $agent_query->fetchAll(PDO::FETCH_COLUMN);
}


// Fetch barangays
$barangays = [];
$brgy_query = $pdo->query('SELECT id, name FROM barangays ORDER BY name ASC');
if ($brgy_query) {
    $barangays = $brgy_query->fetchAll(PDO::FETCH_ASSOC);
}



// Fetch account types
$accountTypes = [];
$acct_query = $pdo->query('SELECT type_name FROM account_type ORDER BY type_name ASC');
if ($acct_query) {
    $accountTypes = $acct_query->fetchAll(PDO::FETCH_COLUMN);
}

$success                = false;
$error                  = '';
$pppoe_message          = '';
$currentPHTimeForInput  = date('Y-m-d\TH:i');
$createdAtValueFromForm = $_POST['created_at'] ?? $currentPHTimeForInput;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Grab and sanitize form data
    $plan_name    = trim($_POST['plan_name'] ?? '');
    $full_name    = trim($_POST['full_name'] ?? '');
    $account_type = trim($_POST['account_type'] ?? '');
    $email        = trim($_POST['email'] ?? '');
    $phone        = trim($_POST['phone'] ?? '');
    $address      = trim($_POST['address'] ?? '');
    $barangay_id = trim($_POST['barangay_id'] ?? '');
    $status       = trim($_POST['status'] ?? '');
    $latitude     = trim($_POST['latitude'] ?? '');
    $longitude    = trim($_POST['longitude'] ?? '');
    $created_at   = trim($_POST['created_at'] ?? $currentPHTimeForInput);
    $agent        = trim($_POST['agent'] ?? '');
    $created_form_by = $currentUser;

    $pppoe_username = trim($_POST['pppoe_username'] ?? '');
    $pppoe_password = trim($_POST['pppoe_password'] ?? '');
    $pppoe_profile  = trim($_POST['pppoe_profile'] ?? 'expired');
    $selected_devices = $_POST['mikrotik_devices'] ?? [];
    $device_names     = [];

    if (!empty($selected_devices)) {
        $in = str_repeat('?,', count($selected_devices) - 1) . '?';
        $dev_stmt = $pdo->prepare("SELECT device_name FROM mikrotik_devices WHERE id IN ($in)");
        $dev_stmt->execute($selected_devices);
        $device_names = $dev_stmt->fetchAll(PDO::FETCH_COLUMN);
    }
    $device_names_str = implode(',', $device_names);

    // Validation
    if (
    !$plan_name || !$full_name || !$account_type || !$email || !$phone ||
    !$status || !$latitude || !$longitude || !$created_at ||
    !$pppoe_username || !$pppoe_password || !$pppoe_profile || !$agent ||
    !$barangay_id
)

 {
        $error = 'All fields including Account Type, Agent, PPPoE username, password, and profile are required.';
    } elseif (empty($selected_devices)) {
        $error = 'Please select at least one MikroTik device.';
    } else {
        // Normalize phone
        $user_phone = preg_replace('/\D/', '', $phone);
        if (strlen($user_phone) === 10) {
            $full_phone = '63' . $user_phone;
        } else {
            $error = 'Please enter a valid 10-digit mobile number (e.g. 9454261242)';
        }

        // Validate lat/lon as numbers
        $latitude  = is_numeric($latitude) ? (float)$latitude : null;
        $longitude = is_numeric($longitude) ? (float)$longitude : null;

        // PPPoE username duplication
        if (!$error) {
            $check_stmt = $pdo->prepare('SELECT COUNT(*) FROM pppoe_users WHERE username = ?');
            $check_stmt->execute([$pppoe_username]);
            if ($check_stmt->fetchColumn() > 0) {
                $error = '⚠️ PPPoE username already exists. Please choose a different username.';
            }
        }

        // Email duplication
        if (!$error) {
            $check_stmt = $pdo->prepare('SELECT COUNT(*) FROM customers WHERE email = ?');
            $check_stmt->execute([$email]);
            if ($check_stmt->fetchColumn() > 0) {
                $error = '⚠️ Email address already exists. Please use a different email.';
            }
        }

        if (!$error) {
            if ($latitude === null || $longitude === null) {
                $error = 'Latitude and Longitude are required and must be numbers.';
            } else {
                $pdo->beginTransaction();
                try {
                    // 1. Insert customer
                    $customer_stmt = $pdo->prepare(
    'INSERT INTO customers
    (plan_name, full_name, account_type, email, phone, address, barangay_id, status, created_at,
     latitude, longitude, username, device_name, agent, created_form_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
);

$customer_stmt->execute([
    $plan_name,
    $full_name,
    $account_type,
    $email,
    $full_phone,
    $address,
    $barangay_id, // ✅ FIXED
    $status,
    $created_at,
    $latitude,
    $longitude,
    $pppoe_username,
    $device_names_str,
    $agent,
    $created_form_by,
]);

                    $customer_id = $pdo->lastInsertId();

                    // 2. Insert PPPoE user in DB
                    $pppoe_stmt = $pdo->prepare(
                        'INSERT INTO pppoe_users (username, password, profile, device_name)
                         VALUES (?, ?, ?, ?)'
                    );
                    $pppoe_stmt->execute([
                        $pppoe_username,
                        $pppoe_password,
                        $pppoe_profile,
                        $device_names_str,
                    ]);

                    // 3. Add PPPoE user to selected MikroTik devices
                    foreach ($selected_devices as $device_id) {
                        $dev_stmt = $pdo->prepare('SELECT * FROM mikrotik_devices WHERE id = ?');
                        $dev_stmt->execute([$device_id]);
                        $device = $dev_stmt->fetch(PDO::FETCH_ASSOC);

                        if ($device) {
                            try {
                                $mt = new MikroTikManager(
                                    $device['ip_address'],
                                    $device['api_username'],
                                    $device['api_password'],
                                    $device['api_port'] ?: 22
                                );
                                $mt->addPppoeUser($pppoe_username, $pppoe_password, $pppoe_profile);
                                $mt->disconnect();
                            } catch (Exception $e) {
                                throw new Exception(
                                    "Failed to add PPPoE user to device '{$device['device_name']}' " .
                                    "({$device['ip_address']}): " . $e->getMessage()
                                );
                            }
                        } else {
                            throw new Exception("Device ID $device_id not found.");
                        }
                    }

                    // 4. Log system action
                    $new_data = [
                        'plan_name'    => $plan_name,
                        'full_name'    => $full_name,
                        'account_type' => $account_type,
                        'email'        => $email,
                        'phone'        => $full_phone,
                        'address'      => $address,
                        'status'       => $status,
                        'created_at'   => $created_at,
                        'latitude'     => $latitude,
                        'longitude'    => $longitude,
                        'username'     => $pppoe_username,
                        'device_name'  => $device_names_str,
                        'agent'        => $agent,
                        'created_form_by' => $created_form_by,
                    ];
                    log_system_action($pdo, 'customers', $customer_id, 'add', $currentUser, null, $new_data);

                    // Commit
                    $pdo->commit();
                    $pppoe_message = '<div class="alert alert-success">✅ PPPoE user added on all selected MikroTik devices.</div>';
                    $success = true;
                } catch (Exception $e) {
                    $pdo->rollBack();
                    $error = '❌ ' . $e->getMessage();
                }
            }
        }
    }
}
?>



<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>Add Customer & PPPoE User</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
    <style>
        #map { height: 250px; border: 1px solid #eee; }
        .created-by-info {
            font-size: 1rem;
            color: #6c757d;
        }
        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #3a3a3a;
            margin-top: 2rem;
            margin-bottom: .5rem;
        }
        .card {
            border-radius: 12px;
            border: 1px solid #eee;
        }
    </style>
</head>
<body>
<main class="container py-4">
    <div class="row justify-content-center">
        <div class="col-12 col-md-10 col-lg-8">
            <?php if ($success): ?>
                <div class="alert alert-success">Customer added successfully!</div>
            <?php elseif ($error): ?>
                <div class="alert alert-danger"><?php echo htmlspecialchars($error); ?></div>
            <?php endif; ?>
            <?php echo $pppoe_message; ?>

            <div class="card p-3 shadow-sm border-0">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <div>
                        <h5 class="mb-0">Add Customer & PPPoE User</h5>
                    </div>
                    <div class="created-by-info">
                        <i class="fa fa-user"></i>
                        Created Form By: <span><?php echo htmlspecialchars($currentUser); ?></span>
                    </div>
                </div>
                <hr>
                <form action="" method="POST" id="customerForm">
                    <input type="hidden" name="created_form_by" value="<?php echo htmlspecialchars($currentUser); ?>">
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label for="plan_name" class="form-label">Plan Name</label>
                            <select name="plan_name" id="plan_name" class="form-select" required>
                                <option value="">Select Plan</option>
                                <?php foreach ($plans as $plan): ?>
                                    <option value="<?php echo htmlspecialchars($plan); ?>"
                                            <?php if (($_POST['plan_name'] ?? '') === $plan) echo 'selected'; ?>>
                                        <?php echo htmlspecialchars($plan); ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label for="agent" class="form-label">Agent</label>
                            <select name="agent" id="agent" class="form-select" required>
                                <option value="">Select Agent</option>
                                <?php foreach ($agents as $agentOpt): ?>
                                    <option value="<?php echo htmlspecialchars($agentOpt); ?>"
                                            <?php if (($_POST['agent'] ?? '') === $agentOpt) echo 'selected'; ?>>
                                        <?php echo htmlspecialchars($agentOpt); ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label for="full_name" class="form-label">Full Name</label>
                            <input type="text" name="full_name" id="full_name" class="form-control" required
                                   value="<?php echo htmlspecialchars($_POST['full_name'] ?? ''); ?>">
                        </div>
                        <div class="col-md-6">
                            <label for="account_type" class="form-label">Account Type</label>
                            <select name="account_type" id="account_type" class="form-select" required>
                                <option value="">Select Account Type</option>
                                <?php foreach ($accountTypes as $acct): ?>
                                    <option value="<?php echo htmlspecialchars($acct); ?>"
                                            <?php if (($_POST['account_type'] ?? '') === $acct) echo 'selected'; ?>>
                                        <?php echo htmlspecialchars($acct); ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" name="email" id="email" class="form-control" required
                                   value="<?php echo htmlspecialchars($_POST['email'] ?? ''); ?>">
                        </div>
                        <div class="col-md-6">
                            <label for="phone" class="form-label">Phone</label>
                            <div class="input-group">
                                <span class="input-group-text">63</span>
                                <input type="text" name="phone" id="phone" maxlength="10" pattern="\d{10}" inputmode="numeric"
                                       class="form-control" placeholder="e.g. 9454261242"
                                       value="<?php echo htmlspecialchars($_POST['phone'] ?? ''); ?>">
                            </div>
                            <small class="text-muted">10-digit mobile number (e.g. 9454261242)</small>
                        </div>
                        <div class="col-12">
                            <label for="address" class="form-label">Address</label>
                            <input type="text" name="address" id="address" class="form-control"
                                   value="<?php echo htmlspecialchars($_POST['address'] ?? ''); ?>">
                        </div>


<div class="col-md-6">
    <label for="barangay_id" class="form-label">Barangay</label>
    <select name="barangay_id" id="barangay_id" class="form-select" required>
        <option value="">Select Barangay</option>
        <?php foreach ($barangays as $b): ?>
            <option value="<?php echo (int)$b['id']; ?>"
                <?php if (($_POST['barangay_id'] ?? '') == $b['id']) echo 'selected'; ?>>
                <?php echo htmlspecialchars($b['name']); ?>
            </option>
        <?php endforeach; ?>
    </select>
</div>






                        <div class="col-md-6">
                            <label for="status" class="form-label">Status</label>
                            <select name="status" id="status" class="form-select" required>
                                <option value="active" <?php if (($_POST['status'] ?? '') === 'active') echo 'selected'; ?>>Active</option>
                                <option value="inactive" <?php if (($_POST['status'] ?? '') === 'inactive') echo 'selected'; ?>>Inactive</option>
                                <option value="suspended" <?php if (($_POST['status'] ?? '') === 'suspended') echo 'selected'; ?>>Suspended</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label for="created_at" class="form-label">Created At</label>
                            <input type="datetime-local" name="created_at" id="created_at"
                                   class="form-control"
                                   value="<?php echo htmlspecialchars($createdAtValueFromForm); ?>"
                                   required>
                            <small class="form-text text-muted">PH time: Asia/Manila</small>
                        </div>
                    </div>
                    <div class="section-title">Location</div>
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label for="latitude" class="form-label">Latitude</label>
                            <input type="number" step="any" name="latitude" id="latitude" class="form-control" required
                                   value="<?php echo htmlspecialchars($_POST['latitude'] ?? ''); ?>">
                        </div>
                        <div class="col-md-6">
                            <label for="longitude" class="form-label">Longitude</label>
                            <input type="number" step="any" name="longitude" id="longitude" class="form-control" required
                                   value="<?php echo htmlspecialchars($_POST['longitude'] ?? ''); ?>">
                        </div>
                        <div class="col-12">
                            <div id="map" class="mb-2"></div>
                            <div class="d-flex justify-content-between">
                                <small class="text-muted">
                                    Click or drag marker on map, or type coordinates.
                                </small>
                                <button type="button" class="btn btn-sm btn-outline-info" id="useLocationBtn">
                                    <i class="fas fa-location-crosshairs"></i> Use Current Location
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="section-title">MikroTik Device(s) & PPPoE</div>
                    <div class="row g-3">
                        <div class="col-12">
                            <label for="mikrotik_devices" class="form-label">Select MikroTik Device(s) <span class="text-danger">*</span></label>
                            <select name="mikrotik_devices[]" id="mikrotik_devices" class="form-select" multiple required>
                                <?php foreach ($devices as $device): ?>
                                    <option value="<?php echo (int)$device['id']; ?>"
                                            <?php if (isset($_POST['mikrotik_devices']) && in_array($device['id'], (array)$_POST['mikrotik_devices'], false)) echo 'selected'; ?>>

                                        <?php echo htmlspecialchars($device['device_name'] . ' (' . $device['ip_address'] . ')'); ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                            <small class="form-text text-muted">Hold Ctrl (Windows) or Command (Mac) for multiple selection.</small>
                        </div>
                        <div class="col-md-4">
                            <label for="pppoe_username" class="form-label">PPPoE Username <span class="text-danger">*</span></label>
                            <input type="text" name="pppoe_username" id="pppoe_username" class="form-control" required
                                   value="<?php echo htmlspecialchars($_POST['pppoe_username'] ?? ''); ?>">
                        </div>
                        <div class="col-md-4">
                            <label for="pppoe_password" class="form-label">PPPoE Password <span class="text-danger">*</span></label>
                            <div class="input-group">
                                <input type="password" name="pppoe_password" id="pppoe_password"
                                       class="form-control" required value="<?php echo htmlspecialchars($_POST['pppoe_password'] ?? ''); ?>">
                                <button type="button" class="btn btn-outline-secondary" id="togglePppoePassword" tabindex="-1">
                                    <i class="fa fa-eye" id="togglePppoePasswordIcon"></i>
                                </button>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <label for="pppoe_profile" class="form-label">PPPoE Profile <span class="text-danger">*</span></label>
                            <select name="pppoe_profile" id="pppoe_profile" class="form-select" required>
                                <option value="expired" <?php if (($_POST['pppoe_profile'] ?? '') === 'expired') echo 'selected'; ?>>expired</option>
                            </select>
                        </div>
                    </div>
                    <div class="d-flex gap-2 justify-content-end mt-4">
                        <button type="button" class="btn btn-outline-secondary" onclick="window.location.href='customers.php';">
                            <i class="fas fa-arrow-left"></i> Back
                        </button>
                        <button type="button" class="btn btn-outline-info" onclick="location.reload();">
                            <i class="fas fa-sync-alt"></i> Refresh
                        </button>
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-plus me-1"></i> Add Customer
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</main>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function () {
    const DEFAULT_LAT = 8.484274;
    const DEFAULT_LNG = 124.623878;

    const latInput = document.getElementById('latitude');
    const lngInput = document.getElementById('longitude');
    const useLocationBtn = document.getElementById('useLocationBtn');

    // Use defaults if fields are empty
    let lat = parseFloat(latInput.value) || DEFAULT_LAT;
    let lng = parseFloat(lngInput.value) || DEFAULT_LNG;

    const map = L.map('map').setView([lat, lng], 16);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: 'Map data © <a href="https://openstreetmap.org">OpenStreetMap</a>',
    }).addTo(map);

    let marker = null;
    function addOrMoveMarker(lat, lng, center = true) {
        if (marker) map.removeLayer(marker);
        marker = L.marker([lat, lng], { draggable: true }).addTo(map);
        marker.on('dragend', function (e) {
            const pos = e.target.getLatLng();
            latInput.value = pos.lat.toFixed(6);
            lngInput.value = pos.lng.toFixed(6);
            if (center) map.setView([pos.lat, pos.lng], map.getZoom());
        });
        if (center) map.setView([lat, lng], Math.max(map.getZoom(), 16));
    }
    if (!isNaN(lat) && !isNaN(lng)) addOrMoveMarker(lat, lng, false);

    map.on('click', function (e) {
        const { lat, lng } = e.latlng;
        latInput.value = lat.toFixed(6);
        lngInput.value = lng.toFixed(6);
        addOrMoveMarker(lat, lng);
    });

    function syncMapFromInputs() {
        const lat = parseFloat(latInput.value);
        const lng = parseFloat(lngInput.value);
        if (!isNaN(lat) && !isNaN(lng)) addOrMoveMarker(lat, lng);
    }
    latInput.addEventListener('change', syncMapFromInputs);
    lngInput.addEventListener('change', syncMapFromInputs);

    useLocationBtn.addEventListener('click', function () {
        latInput.value = DEFAULT_LAT.toFixed(6);
        lngInput.value = DEFAULT_LNG.toFixed(6);
        addOrMoveMarker(DEFAULT_LAT, DEFAULT_LNG);
        map.setView([DEFAULT_LAT, DEFAULT_LNG], 16);
    });
});
</script>


<!-- Live AJAX validation for PPPoE username and email -->
<script>
document.addEventListener('DOMContentLoaded', function () {
    // Username check
    const usernameInput = document.getElementById('pppoe_username');
    const usernameFeedback = document.createElement('div');
    usernameFeedback.className = 'form-text text-danger';
    usernameInput.parentNode.appendChild(usernameFeedback);
    let lastUsername = '';
    usernameInput.addEventListener('input', function () {
        const val = usernameInput.value.trim();
        if (val === '' || val === lastUsername) {
            usernameFeedback.textContent = '';
            usernameInput.setCustomValidity('');
            return;
        }
        lastUsername = val;
        fetch('check_pppoe_username.php?username=' + encodeURIComponent(val))
            .then(r => r.json())
            .then(data => {
                if (data.exists) {
                    usernameFeedback.textContent = 'PPPoE username already exists!';
                    usernameInput.setCustomValidity('Username already exists');
                } else {
                    usernameFeedback.textContent = '';
                    usernameInput.setCustomValidity('');
                }
            })
            .catch(() => {
                usernameFeedback.textContent = '';
                usernameInput.setCustomValidity('');
            });
    });

    // Email check
    const emailInput = document.getElementById('email');
    const emailFeedback = document.createElement('div');
    emailFeedback.className = 'form-text text-danger';
    emailInput.parentNode.appendChild(emailFeedback);
    let lastEmail = '';
    emailInput.addEventListener('input', function () {
        const val = emailInput.value.trim();
        if (val === '' || val === lastEmail) {
            emailFeedback.textContent = '';
            emailInput.setCustomValidity('');
            return;
        }
        lastEmail = val;
        fetch('check_email.php?email=' + encodeURIComponent(val))
            .then(r => r.json())
            .then(data => {
                if (data.exists) {
                    emailFeedback.textContent = 'Email address already exists!';
                    emailInput.setCustomValidity('Email already exists');
                } else {
                    emailFeedback.textContent = '';
                    emailInput.setCustomValidity('');
                }
            })
            .catch(() => {
                emailFeedback.textContent = '';
                emailInput.setCustomValidity('');
            });
    });

    // PPPoE password show/hide
    const pwdInput = document.getElementById('pppoe_password');
    const toggleBtn = document.getElementById('togglePppoePassword');
    const icon = document.getElementById('togglePppoePasswordIcon');
    if (pwdInput && toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            const isHidden = pwdInput.type === 'password';
            pwdInput.type = isHidden ? 'text' : 'password';
            if (icon) {
                icon.classList.toggle('fa-eye', !isHidden);
                icon.classList.toggle('fa-eye-slash', isHidden);
            }
        });
    }
});
</script>




<?php include 'footer.php'; ?>
</body>
</html>
<?php
ob_end_flush();
?>
