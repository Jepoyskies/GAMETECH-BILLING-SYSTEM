<?php
require('routeros_api.class.php');
include 'database.php';

// Helper: Get MikroTik device details for this user
function getUserMikrotikDevices($pdo, $device_names_field) {
    $device_names = array_filter(array_map('trim', explode(',', $device_names_field)));
    if (empty($device_names)) return [];

    $in = implode(',', array_fill(0, count($device_names), '?'));
    $stmt = $pdo->prepare("SELECT * FROM mikrotik_devices WHERE device_name IN ($in)");
    $stmt->execute($device_names);
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

// User ID check
if (!isset($_GET['id'])) {
    echo "<div class='container mt-5'><div class='alert alert-danger'>User ID not specified.</div></div>";
    include 'footer.php';
    exit;
}

$id = intval($_GET['id']);

// Handle disconnect action
if (
    isset($_GET['action']) && $_GET['action'] === 'disconnect' &&
    isset($_GET['session_id']) && isset($_GET['device'])
) {
    $session_id = $_GET['session_id'];
    $device_name = $_GET['device'];

    // Look up device API details
    $stmt = $pdo->prepare("SELECT * FROM mikrotik_devices WHERE device_name = ?");
    $stmt->execute([$device_name]);
    $device = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($device) {
        $API = new RouterosAPI();
        if ($API->connect($device['ip_address'], $device['api_username'], $device['api_password'], $device['api_port'])) {
            $API->comm('/ppp/active/remove', [".id" => $session_id]);
            $API->disconnect();
            header("Location: user_view.php?id={$id}&disconnect=success");
            exit;
        } else {
            header("Location: user_view.php?id={$id}&disconnect=fail");
            exit;
        }
    } else {
        header("Location: user_view.php?id={$id}&disconnect=fail");
        exit;
    }
}

include 'header.php';

// Fetch user data
$stmt = $pdo->prepare("SELECT * FROM customers WHERE id = ?");
$stmt->execute([$id]);
$user = $stmt->fetch();

echo "<div class='container py-5'>";

// Handle ping POST
$pingOutput = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['ping_ip'], $_POST['device'])) {
    $ping_ip = $_POST['ping_ip'];
    $device_name = $_POST['device'];

    $stmt = $pdo->prepare("SELECT * FROM mikrotik_devices WHERE device_name = ?");
    $stmt->execute([$device_name]);
    $device = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($device) {
        $API = new RouterosAPI();
        if ($API->connect($device['ip_address'], $device['api_username'], $device['api_password'], $device['api_port'])) {
            $pingResult = $API->comm('/ping', [
                'address' => $ping_ip,
                'count'   => 4
            ]);
            $pingOutput = "<div class='alert alert-info'><strong>Ping results for $ping_ip:</strong><br>";
            if (is_array($pingResult) && count($pingResult) > 0) {
                foreach ($pingResult as $ping) {
                    $host = htmlspecialchars($ping['host'] ?? '');
                    $time = isset($ping['time']) ? htmlspecialchars($ping['time']) . " ms" : htmlspecialchars($ping['status'] ?? '');
                    $pingOutput .= "$host: $time<br>";
                }
            } else {
                $pingOutput .= 'No ping response.';
            }
            $pingOutput .= "</div>";
            $API->disconnect();
        } else {
            $pingOutput = "<div class='alert alert-danger'>Failed to connect to Mikrotik device.</div>";
        }
    } else {
        $pingOutput = "<div class='alert alert-danger'>Device not found in database.</div>";
    }
}

if (isset($_GET['disconnect'])) {
    if ($_GET['disconnect'] === 'success') {
        echo "<div class='alert alert-success'>User disconnected successfully.</div>";
    } else {
        echo "<div class='alert alert-danger'>Failed to disconnect user (API error).</div>";
    }
}

if ($pingOutput) echo $pingOutput;

echo "<div class='mb-3 d-flex justify-content-start'>
        <a href='subscription_plans.php' class='btn btn-outline-secondary me-2'>
            <i class='fas fa-arrow-left me-2'></i>Back
        </a>
        <button onclick='location.reload();' class='btn btn-outline-info'>
            <i class='fas fa-sync-alt me-2'></i>Refresh
        </button>
      </div>";

if ($user) {

    // ------ Get active PPPoE session and MAC address from all user devices ------
    $latest_mac = '';
    $pppoe_sessions = [];
    $devices = getUserMikrotikDevices($pdo, $user['device_name']);

    // --------- Fetch PPP profile status from each device -----------
    $ppp_profiles = [];
    foreach ($devices as $device) {
        $API = new RouterosAPI();
        if ($API->connect($device['ip_address'], $device['api_username'], $device['api_password'], $device['api_port'])) {
            // Fetch PPP secret for this user on this device
            $secrets = $API->comm('/ppp/secret/print', [
                "?name" => $user['username']
            ]);
            if (is_array($secrets) && count($secrets) > 0) {
                foreach ($secrets as $secret) {
                    $ppp_profiles[] = [
                        'device'   => $device['device_name'],
                        'profile'  => $secret['profile'] ?? 'Not Set',
                        'disabled' => isset($secret['disabled']) && $secret['disabled']=='true' ? 'Disabled' : 'Enabled',
                        'comment'  => $secret['comment'] ?? ''
                    ];
                }
            } else {
                $ppp_profiles[] = [
                    'device'   => $device['device_name'],
                    'profile'  => 'Not Found',
                    'disabled' => 'N/A',
                    'comment'  => ''
                ];
            }
            $API->disconnect();
        } else {
            $ppp_profiles[] = [
                'device'   => $device['device_name'],
                'profile'  => 'API Connect Fail',
                'disabled' => 'N/A',
                'comment'  => ''
            ];
        }
    }
    // -------------------------------------------------------------

    foreach ($devices as $device) {
        $API = new RouterosAPI();
        if ($API->connect($device['ip_address'], $device['api_username'], $device['api_password'], $device['api_port'])) {
            $sessions = $API->comm('/ppp/active/print');
            if (is_array($sessions)) {
                foreach ($sessions as $session) {
                    if (isset($session['name']) && $session['name'] === $user['username']) {
                        $session['_device'] = $device['device_name']; // Tag for display
                        $pppoe_sessions[] = $session;
                        if (!empty($session['caller-id']) && !$latest_mac) {
                            $latest_mac = $session['caller-id'];
                        }
                    }
                }
            }
            $API->disconnect();
        }
    }

    // Store the most recent MAC address (from 'caller-id'), update both tables
    if ($latest_mac && $latest_mac !== $user['mac_address']) {
        $pdo->prepare("UPDATE customers SET mac_address = ? WHERE id = ?")
            ->execute([$latest_mac, $user['id']]);
        $user['mac_address'] = $latest_mac;

        // Only insert if this MAC is not the latest in history
        $stmt = $pdo->prepare("SELECT mac_address FROM customer_mac_history WHERE customer_id = ? ORDER BY detected_at DESC, id DESC LIMIT 1");
        $stmt->execute([$user['id']]);
        $last_history = $stmt->fetchColumn();
        if ($last_history !== $latest_mac) {
            $pdo->prepare("INSERT INTO customer_mac_history (customer_id, mac_address) VALUES (?, ?)")
                ->execute([$user['id'], $latest_mac]);
        }
    }
    // -----------------------------------------------------

    function formatBytes($bytes, $precision = 2) {
        $units = array('B', 'KB', 'MB', 'GB', 'TB');
        $bytes = max($bytes, 0);
        $pow = floor(($bytes ? log($bytes) : 0) / log(1024));
        $pow = min($pow, count($units) - 1);
        $bytes /= (1 << (10 * $pow));
        return round($bytes, $precision) . ' ' . $units[$pow];
    }
    ?>

    <div class="row justify-content-center mb-4">
        <!-- User Details Card (Left) -->
        <div class="col-md-5 mb-4 mb-md-0">
            <div class="card shadow h-100">
                <div class="card-body">
                    <h3 class="card-title mb-3">
                        <i class="fas fa-user-circle me-2"></i>User Details
                    </h3>
                    <ul class="list-group list-group-flush mb-2">
                        <li class="list-group-item"><strong>ID:</strong> <?= htmlspecialchars($user['id']) ?></li>
                        <li class="list-group-item"><strong>Mikrotik Device(s) Connected:</strong>
                            <?= htmlspecialchars($user['device_name']) ?>

                        </li>
                        <li class="list-group-item"><strong>Username:</strong> <?= htmlspecialchars($user['username']) ?></li>
                        <li class="list-group-item"><strong>Full Name:</strong> <?= htmlspecialchars($user['full_name']) ?></li>
                        <li class="list-group-item"><strong>MAC Address:</strong>
                            <?= htmlspecialchars($user['mac_address'] ?: 'Not Available') ?>
                        </li>
                        <li class="list-group-item"><strong>MAC Address History:</strong><br>
                            <?php
                            // Show up to 5 most recent MACs
                            $stmt = $pdo->prepare("SELECT mac_address, detected_at FROM customer_mac_history WHERE customer_id = ? ORDER BY detected_at DESC, id DESC LIMIT 5");
                            $stmt->execute([$user['id']]);
                            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
                            if (count($rows) == 0) {
                                echo "<em>No history</em>";
                            } else {
                                echo "<ul class='mb-0 ps-3'>";
                                foreach ($rows as $row) {
                                    echo "<li>".htmlspecialchars($row['mac_address'])." <small class='text-muted'>(".htmlspecialchars($row['detected_at']).")</small></li>";
                                }
                                echo "</ul>";
                            }
                            ?>
                        </li>
                    </ul>
                </div>
            </div>
        </div>

        <!-- Active PPPoE Session Card (Right) -->
        <div class="col-md-7">
            <div class="card shadow h-100 border-primary">
                <div class="card-header bg-primary text-white py-2">
                    Active PPPoE Session(s)
                </div>
                <div class="card-body">
                    <?php
                    if (is_array($pppoe_sessions) && count($pppoe_sessions) > 0) {
                        foreach ($pppoe_sessions as $session) {
                            ?>
                            <div class="card mb-3 border-primary">
                                <div class="card-body p-3">
                                    <div class="row g-2">
                                        <div class="col-6"><strong>Device:</strong> <?= htmlspecialchars($session['_device']) ?></div>
                                        <div class="col-6"><strong>Name:</strong> <?= htmlspecialchars($session['name'] ?? '') ?></div>
                                        <div class="col-6"><strong>Service:</strong> <?= htmlspecialchars($session['service'] ?? '') ?></div>
                                      

                                        <div class="col-6"><strong>Caller ID:</strong> <?= htmlspecialchars($session['caller-id'] ?? '') ?></div>
                                        
                                        
<div class="col-6">
    <strong>IP Address (Remote Client):</strong>
    <?php if (!empty($session['address'])): ?>
        <a href="http://<?= htmlspecialchars($session['address']) ?>" target="_blank" rel="noopener">
            <?= htmlspecialchars($session['address']) ?>
        </a>
    <?php else: ?>
        <em>Not Assigned</em>
    <?php endif; ?>
</div>



                                        <div class="col-12"><strong>Uptime:</strong> <?= htmlspecialchars($session['uptime'] ?? '') ?></div>
                                    </div>

                                    <br>
                                    <!-- Disconnect Button -->
                                    <form method="get" class="mt-3 d-inline" onsubmit="return confirm('Are you sure you want to disconnect this user?');">
                                        <input type="hidden" name="id" value="<?= htmlspecialchars($user['id']) ?>">
                                        <input type="hidden" name="action" value="disconnect">
                                        <input type="hidden" name="session_id" value="<?= htmlspecialchars($session['.id']) ?>">
                                        <input type="hidden" name="device" value="<?= htmlspecialchars($session['_device']) ?>">
                                        <button type="submit" class="btn btn-danger">
                                            <i class="fas fa-sign-out-alt me-2"></i>Disconnect User
                                        </button>
                                    </form>
                                    <!-- Ping Button -->
                                    <form method="post" class="mt-3 d-inline">
                                        <input type="hidden" name="ping_ip" value="<?= htmlspecialchars($session['address'] ?? '') ?>">
                                        <input type="hidden" name="device" value="<?= htmlspecialchars($session['_device'] ?? '') ?>">
                                        <button type="submit" class="btn btn-info">
                                            <i class="fas fa-wifi me-2"></i>Ping User
                                        </button>
                                    </form>
                                                 </div>
                            </div>
                            <?php
                        }
                    } else {
                        echo "<div class='alert alert-warning mb-0'>No active PPPoE session found for this user on any device.</div>";
                    }
                    ?>
                </div>
            </div>
        </div>
    </div>

    <!-- Recent Disconnect Logs (full width) -->
    <div class="row justify-content-center">
        <div class="col-12">
            <div class="card shadow mb-4">
                <div class="card-header bg-light d-flex justify-content-between align-items-center">
                    <span><i class="fas fa-history me-2"></i> Recent Disconnect Logs for <?= htmlspecialchars($user['full_name']) ?></span>
                </div>
                <div class="card-body">
                    <?php
                    // Fetch logs from all user's devices
                    $userLogs = [];
                    foreach ($devices as $device) {
                        $API = new RouterosAPI();
                        if ($API->connect($device['ip_address'], $device['api_username'], $device['api_password'], $device['api_port'])) {
                            $logs = $API->comm("/log/print", [
                                ".proplist" => "time,message,topics",
                            ]);
                            if (is_array($logs)) {
                                foreach ($logs as $log) {
                                    $msg = $log['message'] ?? '';
                                    $topics = $log['topics'] ?? '';
                                    if (
                                        (
                                            stripos($msg, $user['username']) !== false ||
                                            stripos($msg, $user['full_name']) !== false
                                        ) &&
                                        (
                                            stripos($topics, 'pppoe') !== false ||
                                            stripos($msg, 'disconnected') !== false
                                        )
                                    ) {
                                        $log['_device'] = $device['device_name'];
                                        $userLogs[] = $log;
                                    }
                                }
                            }
                            $API->disconnect();
                        }
                    }
                    if (count($userLogs) > 0) {
                        echo "<table class='table table-sm table-striped mb-0'>
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Message</th>
                                        <th>Device</th>
                                    </tr>
                                </thead>
                                <tbody>";
                        foreach (array_slice(array_reverse($userLogs), 0, 10) as $log) {
                            $time = $log['time'] ?? '';
                            $device = $log['_device'] ?? '';
                            $message = $log['message'] ?? '';
                            echo "<tr>
                                    <td>" . htmlspecialchars($time) . "</td>
                                    <td>" . htmlspecialchars($message) . "</td>
                                    <td><span class='badge bg-secondary'>" . htmlspecialchars($device) . "</span></td>
                                </tr>";
                        }
                        echo "</tbody></table>";
                    } else {
                        echo "<div class='alert alert-info mb-0'>No disconnect logs found for this user on any device.</div>";
                    }
                    ?>
                </div>
            </div>
        </div>
    </div>

    <!-- PPP Profile Status Logs (full width) -->
    <div class="row justify-content-center">
        <div class="col-12">
            <div class="card shadow mb-4">
                <div class="card-header bg-info text-white d-flex justify-content-between align-items-center">
                    <span><i class="fas fa-user-shield me-2"></i> PPP Profile Status Logs for <?= htmlspecialchars($user['full_name']) ?></span>
                </div>
                <div class="card-body">
                    <?php
                    if (count($ppp_profiles) > 0) {
                        echo "<table class='table table-sm table-bordered mb-0'>
                                <thead>
                                    <tr>
                                        <th>Device</th>
                                        <th>Profile</th>
                                        <th>Status</th>
                                        <th>Comment</th>
                                    </tr>
                                </thead>
                                <tbody>";
                        foreach ($ppp_profiles as $p) {
                            // Badge coloring for profile
                            $profile = $p['profile'];
                            $badgeClass = 'secondary';
                            if (stripos($profile, 'default') !== false) $badgeClass = 'primary';
                            elseif (stripos($profile, 'premium') !== false) $badgeClass = 'success';
                            elseif (stripos($profile, 'limited') !== false) $badgeClass = 'warning';
                            elseif (stripos($profile, 'fail') !== false || stripos($profile, 'not found') !== false) $badgeClass = 'danger';

                            echo "<tr>
                                    <td>".htmlspecialchars($p['device'])."</td>
                                    <td><span class='badge bg-$badgeClass'>".htmlspecialchars($profile)."</span></td>
                                    <td>".htmlspecialchars($p['disabled'])."</td>
                                    <td>".htmlspecialchars($p['comment'])."</td>
                                </tr>";
                        }
                        echo "</tbody></table>";
                    } else {
                        echo "<div class='alert alert-info mb-0'>No PPP profile status data found for this user.</div>";
                    }
                    ?>
                </div>
            </div>
        </div>
    </div>

    <?php
} else {
    echo "<div class='alert alert-danger'>User not found.</div>";
}
echo "</div>"; // container

include 'footer.php';
?>
