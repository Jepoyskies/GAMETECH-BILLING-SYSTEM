<?php
require_once 'routeros_api.class.php';
require_once 'MikrotikManager_suspend.php';
require 'database.php';

define('LOCK_FILE', __DIR__ . '/auto_suspend.lock');
define('LOCK_TIMEOUT', 1800); // 30 minutes

// --- LOCKING MECHANISM ---
function obtain_lock() {
    $lock_file = LOCK_FILE;
    $fp = fopen($lock_file, 'c+');
    if (!$fp) return false;
    if (!flock($fp, LOCK_EX | LOCK_NB)) {
        // Check age, if older than timeout, remove
        $stat = fstat($fp);
        if (time() - $stat['mtime'] > LOCK_TIMEOUT) {
            unlink($lock_file);
            fclose($fp);
            // Try again
            $fp = fopen($lock_file, 'c+');
            if (!$fp) return false;
            if (!flock($fp, LOCK_EX | LOCK_NB)) {
                fclose($fp);
                return false;
            }
            // Got lock
        } else {
            fclose($fp);
            return false;
        }
    }
    // Write PID and time
    ftruncate($fp, 0);
    fwrite($fp, getmypid() . " " . time());
    fflush($fp);
    return $fp;
}

function release_lock($fp) {
    if ($fp) {
        flock($fp, LOCK_UN);
        fclose($fp);
    }
}

// --- LOGGING FUNCTION ---
function log_event($message) {
    $logfile = __DIR__ . '/suspend_users.log';
    $date = date('Y-m-d H:i:s');
    error_log("[$date] $message\n", 3, $logfile);
}

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
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
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
// Cache connections to avoid reconnecting for each user in the same device
function get_all_mikrotik_profiles($ip, $user, $pass, $port) {
    $API = new RouterosAPI();
    $profiles = [];
    try {
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
    } catch (Exception $e) {
        log_event("Mikrotik API error: " . $e->getMessage());
    }
    return $profiles;
}

$message = null;

// --- OBTAIN LOCK (prevent concurrent runs) ---
$lock_fp = obtain_lock();
if (!$lock_fp) {
    log_event("Another instance is already running. Exiting.");
    exit;
}

try {
    // --- FETCH DATA FOR DISPLAY ---
    $conn = db_connect($host, $user, $pass, $db);
    $due_customers = get_past_due_customers($conn);
    $devices = get_mikrotik_devices($conn);

    // Preload all device profiles (minimize API calls)
    $device_profiles = [];
    foreach ($devices as $dev_name => $dev) {
        $device_profiles[$dev_name] = get_all_mikrotik_profiles(
            $dev['ip_address'],
            $dev['api_username'],
            $dev['api_password'],
            $dev['api_port']
        );
    }

    // --- FOR DISPLAY: FETCH ALL PROFILES FOR EACH CUSTOMER FROM THEIR ASSIGNED DEVICE ---
    foreach ($due_customers as &$row) {
        $device_name = $row['device_name'];
        if (isset($device_profiles[$device_name])) {
            $all_profiles = $device_profiles[$device_name];
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

    // --- AUTOMATIC SUSPEND EXPIRED USERS (NO FORM) ---
    if (count($due_customers) > 0) {
        log_event("Suspend process started by system/cron, processing " . count($due_customers) . " users.");

        $batch_size = 20; // Increase for better throughput if server can handle
        $usernames = array_column($due_customers, 'username');
        $displayed_users = [];
        foreach ($due_customers as $c) {
            $displayed_users[$c['username']] = $c;
        }
        $user_batches = array_chunk($usernames, $batch_size);

        $suspended = 0;
        $errors = [];
        $batch_num = 1;
        foreach ($user_batches as $user_batch) {
            log_event("Processing batch #{$batch_num} (" . count($user_batch) . " users)");
            foreach ($user_batch as $username) {
                if (!isset($displayed_users[$username])) {
                    $error = "User '{$username}' not found in displayed list";
                    $errors[] = $error;
                    log_event("ERROR: $error");
                    continue;
                }
                $c = $displayed_users[$username];
                $device_name = $c['device_name'];
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
                // Free up resources!
                unset($mt);
            }
            $batch_num++;
            usleep(250_000); // 0.25 seconds between batches for rate-limiting
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

    $conn->close();
} catch (Exception $e) {
    log_event("FATAL ERROR: " . $e->getMessage());
    $message = "FATAL ERROR: " . $e->getMessage();
} finally {
    release_lock($lock_fp);
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
                <td><?= htmlspecialchars($c['mikrotik_devices']) ?></td>
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
