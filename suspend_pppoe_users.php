<?php
require_once 'routeros_api.class.php';
require_once 'MikrotikManager_suspend.php';
require 'database.php';

// --- LOGGING FUNCTION ---
function log_event($message) {
    $logfile = __DIR__ . '/suspend_users.log';
    $date = date('Y-m-d H:i:s');
    error_log("[$date] $message\n", 3, $logfile);
}

// Enable mysqli exceptions for better debugging (disable in production)
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

// --- DB CONNECTION FUNCTION ---
function db_connect($host, $user, $pass, $db) {
    $conn = new mysqli($host, $user, $pass, $db);
    $conn->set_charset('utf8mb4');
    return $conn;
}

// --- FETCH PAST-DUE CUSTOMERS ---
function get_past_due_customers($conn) {
    $sql = "SELECT * FROM customers WHERE expires_at <= (NOW() - INTERVAL 1 SECOND)";
    $stmt = $conn->prepare($sql);
    $stmt->execute();
    $result = $stmt->get_result();
    $rows = $result->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
    return $rows;
}

// --- FETCH ALL MIKROTIK DEVICES ---
function get_mikrotik_devices($conn) {
    $sql = "SELECT * FROM mikrotik_devices";
    $stmt = $conn->prepare($sql);
    $stmt->execute();
    $result = $stmt->get_result();
    $devices = [];
    while ($row = $result->fetch_assoc()) {
        $devices[$row['device_name']] = $row;
    }
    $stmt->close();
    return $devices;
}

// --- FETCH ALL MIKROTIK PROFILES FOR A DEVICE ---
function get_all_mikrotik_profiles($ip, $user, $pass, $port) {
    $API = new RouterosAPI();
    $profiles = [];
    if ($API->connect($ip, $user, $pass, $port)) {
        $secrets = $API->comm("/ppp/secret/print");
        if (is_array($secrets)) {
            foreach ($secrets as $secret) {
                if (isset($secret['name']) && isset($secret['profile'])) {
                    $profiles[$secret['name']] = $secret['profile'];
                }
            }
        }
        $API->disconnect();
    }
    return $profiles;
}

$message = null;

// --- FETCH DATA FOR DISPLAY ---
try {
    $conn = db_connect($host, $user, $pass, $db);
    $due_customers = get_past_due_customers($conn);
    $devices = get_mikrotik_devices($conn);
    $conn->close();
} catch (Exception $e) {
    log_event("FATAL ERROR fetching customers or devices: " . $e->getMessage());
    die('Database connection or query failed.');
}

// --- FOR DISPLAY: FETCH ALL PROFILES FOR EACH CUSTOMER FROM THEIR ASSIGNED DEVICE ---
foreach ($due_customers as &$row) {
    $device_name = $row['device_name'];
    if (isset($devices[$device_name])) {
        $dev = $devices[$device_name];
        $all_profiles = get_all_mikrotik_profiles(
            $dev['ip_address'],
            $dev['api_username'],
            $dev['api_password'],
            $dev['api_port']
        );
        $row['mikrotik_profile'] = $all_profiles[$row['username']] ?? 'N/A';
    } else {
        $row['mikrotik_profile'] = 'Device Not Found';
    }
}
unset($row);

// --- FILTER: REMOVE users with Mikrotik Profile 'expired' (case-insensitive) ---
$due_customers = array_filter($due_customers, function($c) {
    return strcasecmp($c['mikrotik_profile'], 'expired') !== 0;
});

// --- HANDLE SUSPEND EXPIRED (ONLY DISPLAYED USERS, BATCHED) ---
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'suspend_expired') {
    log_event("Suspend process started by user {$_SERVER['REMOTE_ADDR']}");

    // Only process users that are displayed and posted
    $selected_usernames = isset($_POST['usernames']) && is_array($_POST['usernames']) ? $_POST['usernames'] : [];

    // Build a lookup table of displayed users (from $due_customers)
    $displayed_users = [];
    foreach ($due_customers as $c) {
        $displayed_users[$c['username']] = $c;
    }

    $batch_size = 5; // <--- Set your preferred batch size here
    $user_batches = array_chunk($selected_usernames, $batch_size);

    $suspended = 0;
    $errors = [];
    $batch_num = 1;
    foreach ($user_batches as $user_batch) {
        log_event("Processing batch #{$batch_num} (" . count($user_batch) . " users)");
        foreach ($user_batch as $username) {
            if (!isset($displayed_users[$username])) {
                $error = "User '{$username}' not found in displayed list (possible tampering)";
                $errors[] = $error;
                log_event("ERROR: $error");
                continue;
            }
            $c = $displayed_users[$username];
            $device_name = $c['mikrotik_devices'];
            if (!isset($devices[$device_name])) {
                $error = "Device '{$device_name}' not found for user '{$c['username']}'";
                $errors[] = $error;
                log_event("ERROR: $error");
                continue;
            }
            $dev = $devices[$device_name];
            try {
                $mt = new MikroTikManager(
                    $dev['ip_address'],
                    $dev['api_username'],
                    $dev['api_password'],
                    $dev['api_port']
                );
                $mt->suspendPppoeUser($c['username']);
                $suspended++;
                log_event("Suspended user '{$c['username']}' ({$c['full_name']}) on device '{$device_name}'");
            } catch (Exception $e) {
                $error = "Failed to suspend user '{$c['username']}' on device '{$device_name}': " . $e->getMessage();
                $errors[] = $error;
                log_event("ERROR: $error");
            }
        }
        $batch_num++;
        usleep(500_000); // sleep for 0.5 seconds between batches
    }

    $message = "Suspended " . $suspended . " expired user(s) on their assigned Mikrotik device(s).";
    if (!empty($errors)) {
        $message .= "<br><strong>Some errors occurred:</strong><ul>";
        foreach ($errors as $err) {
            $message .= "<li>" . htmlspecialchars($err) . "</li>";
        }
        $message .= "</ul>";
    }
    log_event("Suspend process completed: $suspended suspended, " . count($errors) . " errors.");
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Past Due Customers</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css">
</head>
<body>
<main class="container py-4">
  <div class="card mt-2">
    <div class="card-body">
      <h5 class="card-title">Past Due Customers (Auto-Suspended)</h5>

      <?php if (!empty($message)): ?>
        <div class="alert alert-info" role="alert"><?= $message ?></div>
      <?php endif; ?>

      <?php if (count($due_customers) > 0): ?>
        <form method="POST" action="" style="display:inline-block; margin-bottom:16px;">
          <input type="hidden" name="action" value="suspend_expired">
          <?php foreach ($due_customers as $c): ?>
            <input type="hidden" name="usernames[]" value="<?= htmlspecialchars($c['username']) ?>">
          <?php endforeach; ?>
          <button type="submit" class="btn btn-warning" onclick="return confirm('Are you sure you want to suspend and disconnect all expired users now?');">
            Suspend &amp; Disconnect All Expired Profiles
          </button>
        </form>

        <table class="table table-striped table-sm table-bordered">
          <thead>
            <tr>
              <th>Name</th>
              <th>Username</th>
              <th>Expires At</th>
              <th>Mikrotik Profile</th>
              <th>Mikrotik Devices</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach($due_customers as $c): ?>
              <tr>
                <td><?= htmlspecialchars($c['full_name']) ?></td>
                <td><?= htmlspecialchars($c['username']) ?></td>
                <td><?= htmlspecialchars($c['expires_at']) ?></td>
                <td><?= htmlspecialchars($c['mikrotik_profile']) ?></td>
                <td><?= htmlspecialchars($c['device_name']) ?></td>
              </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      <?php else: ?>
        <p class="text-success">No past due customers!</p>
      <?php endif; ?>
    </div>
  </div>
</main>
</body>
</html>
