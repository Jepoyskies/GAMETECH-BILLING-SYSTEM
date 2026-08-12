<?php
include 'header.php';
include 'database.php';
date_default_timezone_set('Asia/Manila');
require_once('routeros_api.class.php');

// Helper: status HTML
function get_status_html($row, $now_unix, $soon_unix, $inactive_limit_unix, $for = 'desktop') {
    $expires_at = $row['expires_at'];
    $expires_timestamp = $expires_at ? strtotime($expires_at) : 0;
    $row_id = $row['id'];

    if (!$expires_at) {
        return '<span class="status-icon status-expired" aria-label="Expired"><i class="fas fa-times-circle"></i></span> <span style="color:#dc3545;">Expired</span>';
    } elseif ($expires_timestamp <= $inactive_limit_unix) {
        return '<span class="status-icon status-inactive" aria-label="Inactive"><i class="fas fa-user-slash"></i></span> <span style="color:#6c757d;">Inactive</span>';
    } elseif ($expires_timestamp <= $now_unix) {
        return '<span class="status-icon status-expired" aria-label="Expired"><i class="fas fa-times-circle"></i></span> <span style="color:#dc3545;">Expired</span>';
    } elseif ($expires_timestamp > $now_unix && $expires_timestamp <= $soon_unix) {
        $seconds_left = $expires_timestamp - $now_unix;
        $elem_id = $for === 'mobile' ? "countdown-mobile-$row_id" : "countdown-$row_id";
        return '<span class="status-icon status-warning" aria-label="Expiring soon"><i class="fas fa-exclamation-triangle"></i></span>
                <span style="color:#ff9800;" id="'.$elem_id.'" data-seconds="'.$seconds_left.'">
                    (<span class="time"></span>)
                </span>';
    } else {
        return '<span class="status-icon status-active" aria-label="Active"><i class="fas fa-check-circle"></i></span> <span style="color:#28a745;">Active</span>';
    }
}

function get_connection_status_html($username, $connected_usernames) {
    if (isset($connected_usernames[$username])) {
        return '<span class="status-icon status-active" aria-label="Connected"><i class="fas fa-link"></i></span> <span style="color:#28a745;">Connected</span>';
    } else {
        return '<span class="status-icon status-expired" aria-label="Not Connected"><i class="fas fa-unlink"></i></span> <span style="color:#dc3545;">Not Connected</span>';
    }
}

function get_ppp_profile_html($username, $ppp_users_status) {
    if (!isset($ppp_users_status[$username])) {
        return '<span class="badge bg-secondary">N/A</span>';
    }
    $profile = $ppp_users_status[$username]['profile'] ?? '';
    if ($profile === '') {
        return '<span class="badge bg-secondary">N/A</span>';
    }
    return '<span class="badge bg-info text-dark">'.htmlspecialchars($profile, ENT_QUOTES, 'UTF-8').'</span>';
}



function get_account_type_html($type) {
    if (!$type) {
        return '<span class="badge bg-secondary">N/A</span>';
    }

    $type_lower = strtolower($type);

    switch ($type_lower) {
        case 'residential':
            return '<span class="badge bg-primary">Residential</span>';
        case 'business':
            return '<span class="badge bg-success">Business</span>';
        case 'vip':
            return '<span class="badge bg-warning text-dark">VIP</span>';
        case 'suspended':
            return '<span class="badge bg-danger">Suspended</span>';
        default:
            return '<span class="badge bg-dark">'.htmlspecialchars($type).'</span>';
    }
}






// --- MikroTik API Section ---
$connected_usernames = [];
$ppp_users_status = [];

$stmt = $pdo->query("SELECT ip_address, api_username, api_password, api_port FROM mikrotik_devices");
$devices = $stmt->fetchAll(PDO::FETCH_ASSOC);

foreach ($devices as $device) {
    $API = new RouterosAPI();
    $ip   = $device['ip_address'];
    $user = $device['api_username'];
    $pass = $device['api_password'];
    $port = $device['api_port'];

    if ($API->connect($ip, $user, $pass, $port)) {

        // ACTIVE USERS (for uptime)
        $API->write('/ppp/active/print');
        $activeUsers = $API->read();

        foreach ($activeUsers as $userRow) {
            if (!empty($userRow['name'])) {
                $connected_usernames[$userRow['name']] = [
                    'uptime' => $userRow['uptime'] ?? ''
                ];
            }
        }

        // PPP SECRETS (profile + last logout)
        $API->write('/ppp/secret/print');
        $pppUsers = $API->read();

        foreach ($pppUsers as $pppRow) {
            if (!empty($pppRow['name'])) {
                $ppp_users_status[$pppRow['name']] = [
                    'profile' => $pppRow['profile'] ?? '',
                    'last_logged_out' => $pppRow['last-logged-out'] ?? ''
                ];
            }
        }

        $API->disconnect();
    }
}


// --- Input (with sane defaults) ---
$search = isset($_GET['search']) ? trim($_GET['search']) : '';
$status_filter = isset($_GET['status']) ? $_GET['status'] : '';
$page = isset($_GET['page']) ? max(1, intval($_GET['page'])) : 1;
$per_page = isset($_GET['per_page']) && intval($_GET['per_page']) > 0 ? intval($_GET['per_page']) : 35;
$offset = ($page - 1) * $per_page;

// --- Device & Connection filters ---
$device_filter = isset($_GET['device']) ? trim($_GET['device']) : '';
$connection_filter = isset($_GET['connection']) ? trim($_GET['connection']) : '';

$valid_sort_columns = [
    'id' => 'c.id',
    'username' => 'c.username',
    'full_name' => 'c.full_name',
    'address' => 'c.address',
    'expires_at' => 'c.expires_at',
    'plan_name' => 's.plan_name',
    'price' => 's.price',
    'device_name' => 'c.device_name'
];

$sort = (isset($_GET['sort']) && isset($valid_sort_columns[$_GET['sort']])) ? $_GET['sort'] : 'expires_at';
$order = (isset($_GET['order']) && strtoupper($_GET['order']) === 'ASC') ? 'ASC' : 'DESC';
$sort_sql = $valid_sort_columns[$sort] . ' ' . $order;

$now = new DateTime();
$now_str = $now->format('Y-m-d H:i:s');
$soon = clone $now; $soon->modify('+7 days');
$soon_str = $soon->format('Y-m-d H:i:s');
$one_month_ago = clone $now; $one_month_ago->modify('-1 month');
$one_month_ago_str = $one_month_ago->format('Y-m-d H:i:s');

$where = [];
$params = [];
$where[] = "c.username IS NOT NULL AND c.username != '' AND (c.status IS NULL OR c.status != 'pull out')";

if ($search !== '') {
    $where[] = "(c.username LIKE :search1 OR c.full_name LIKE :search2 OR c.address LIKE :search3)";
$params[':search1'] = "%$search%";
$params[':search2'] = "%$search%";
$params[':search3'] = "%$search%";

}

switch ($status_filter) {
    case 'active':
        $where[] = "c.expires_at IS NOT NULL AND c.expires_at > :soon";
        $params[':soon'] = $soon_str;
        break;
    case 'expiring':
        $where[] = "c.expires_at IS NOT NULL AND c.expires_at > :now AND c.expires_at <= :soon";
        $params[':now'] = $now_str;
        $params[':soon'] = $soon_str;
        break;
    case 'expired':
        $where[] = "((c.expires_at IS NULL) OR (c.expires_at <= :now AND c.expires_at > :one_month_ago))";
        $params[':now'] = $now_str;
        $params[':one_month_ago'] = $one_month_ago_str;
        break;
    case 'inactive':
        $where[] = "c.expires_at IS NOT NULL AND c.expires_at <= :one_month_ago";
        $params[':one_month_ago'] = $one_month_ago_str;
        break;
}

if ($device_filter !== '') {
    $where[] = 'c.device_name = :device_name';
    $params[':device_name'] = $device_filter;
}

// Apply connection filter at DB-level using connected usernames list
if ($connection_filter !== '') {
    if ($connection_filter === 'Connected') {
        if (count($connected_usernames) === 0) {
            $where[] = "1=0"; // none connected
        } else {
            $in = [];
            foreach (array_keys($connected_usernames) as $i => $u) {
                $k = ":cu_$i";
                $in[] = $k;
                $params[$k] = $u;
            }
            $where[] = "c.username IN (" . implode(',', $in) . ")";
        }
    } elseif ($connection_filter === 'Not Connected') {
        if (count($connected_usernames) > 0) {
            $in = [];
            foreach (array_keys($connected_usernames) as $i => $u) {
                $k = ":cu_$i";
                $in[] = $k;
                $params[$k] = $u;
            }
            $where[] = "c.username NOT IN (" . implode(',', $in) . ")";
        }
        // if no connected users, all are Not Connected => no extra where
    }
}

$where_sql = implode(' AND ', $where);

try {
    // Device dropdown values
    $device_sql = "SELECT DISTINCT c.device_name
                   FROM customers c
                   WHERE c.device_name IS NOT NULL AND c.device_name != ''
                     AND c.username IS NOT NULL AND c.username != ''
                     AND (c.status IS NULL OR c.status != 'pull out')
                   ORDER BY c.device_name";
    $device_stmt = $pdo->query($device_sql);
    $device_names = $device_stmt->fetchAll(PDO::FETCH_COLUMN);

    // Pagination totals (after all filters)
    $count_sql = "SELECT COUNT(*)
                  FROM customers c
                  JOIN service_plans s ON c.plan_name = s.plan_name
                  WHERE $where_sql";
    $stmt = $pdo->prepare($count_sql);
    foreach ($params as $name => $value) $stmt->bindValue($name, $value);
    $stmt->execute();
    $total = (int)$stmt->fetchColumn();
    $total_pages = max(1, (int)ceil($total / $per_page));

    // Fetch page
    $sql = "SELECT c.id, c.username, c.full_name, c.address, c.expires_at, c.device_name, c.account_type, s.plan_name, s.price, c.connection
            FROM customers c
            JOIN service_plans s ON c.plan_name = s.plan_name
            WHERE $where_sql
            ORDER BY $sort_sql
            LIMIT :limit OFFSET :offset";
    $stmt = $pdo->prepare($sql);
    foreach ($params as $name => $value) $stmt->bindValue($name, $value);
    $stmt->bindValue(':limit', $per_page, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // Status summary across ALL filtered users
    $count_active = $count_expiring = $count_expired = $count_inactive = 0;
    $now_unix = time();
    $soon_unix = $now_unix + 7 * 24 * 60 * 60;
    $inactive_limit_unix = strtotime('-1 month', $now_unix);

    $status_query = "SELECT c.expires_at
                     FROM customers c
                     JOIN service_plans s ON c.plan_name = s.plan_name
                     WHERE $where_sql";
    $status_stmt = $pdo->prepare($status_query);
    foreach ($params as $name => $value) $status_stmt->bindValue($name, $value);
    $status_stmt->execute();

    while ($r = $status_stmt->fetch(PDO::FETCH_ASSOC)) {
        $expires_at = $r['expires_at'];
        $expires_timestamp = $expires_at ? strtotime($expires_at) : 0;

        if (!$expires_at) {
            $count_expired++;
        } elseif ($expires_timestamp <= $inactive_limit_unix) {
            $count_inactive++;
        } elseif ($expires_timestamp <= $now_unix) {
            $count_expired++;
        } elseif ($expires_timestamp <= $soon_unix) {
            $count_expiring++;
        } else {
            $count_active++;
        }
    }

    // Connected / Not Connected counts across ALL filtered users
    $count_connected = 0;
    $count_not_connected = 0;

    $conn_query = "SELECT c.username
                   FROM customers c
                   JOIN service_plans s ON c.plan_name = s.plan_name
                   WHERE $where_sql";
    $conn_stmt = $pdo->prepare($conn_query);
    foreach ($params as $name => $value) $conn_stmt->bindValue($name, $value);
    $conn_stmt->execute();

    while ($r = $conn_stmt->fetch(PDO::FETCH_ASSOC)) {
        $u = $r['username'] ?? '';
        if ($u !== '' && isset($connected_usernames[$u])) $count_connected++;
        else $count_not_connected++;
    }

} catch (PDOException $e) {
    echo "<pre>PDO ERROR: " . htmlspecialchars($e->getMessage()) . "</pre>";
    exit;
}
?>



















<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Subscription Plans</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
    .subscription-card { border: 1px solid #dee2e6; border-radius: .5rem; margin-bottom: 1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.03); padding: 1rem;}
    .subscription-card .card-label { font-weight: 600; color: #495057;}
    .status-icon { font-size: 1.1em; vertical-align: middle; margin-right: 0.2em;}
    .status-active { color: #28a745; }
    .status-warning { color: #ff9800; }
    .status-expired { color: #dc3545; }
    .status-inactive { color: #6c757d; }
    .small-table table { font-size: 0.74rem; margin-bottom: 0; }
    .small-table th, .small-table td { padding: 0.16rem 0.19rem; vertical-align: middle; white-space: nowrap; }
    .small-table .btn { padding: 0.06rem 0.17rem; font-size: 0.62rem; }
    .small-table .badge { font-size: 0.54rem; }
    .summary-status-table th, .summary-status-table td { font-size: 1.1rem; padding: 0.5rem 0.5rem; }
    @media (max-width: 767.98px) {
        .summary-status-table th, .summary-status-table td { font-size:0.95rem; padding: 0.35rem 0.2rem;}
        .summary-status-table { font-size: 0.95rem; }
    }
    </style>
</head>







<body>

<main class="container py-4">

<h2 class="mb-4 fw-bold text-primary">
    <i class="fa-regular fa-address-book"></i> Subscription Plans
</h2>

<!-- STATUS SUMMARY -->
<div class="row mb-4">
    <div class="col-12">
        <div class="card shadow-sm">
            <div class="card-body p-3">
                <div class="table-responsive">
                    <table class="table table-bordered text-center align-middle mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>
                                    <span class="text-success"><i class="fas fa-check-circle"></i></span><br>
                                    Active
                                </th>
                                <th>
                                    <span class="text-warning"><i class="fas fa-exclamation-triangle"></i></span><br>
                                    Expiring Soon
                                </th>
                                <th>
                                    <span class="text-danger"><i class="fas fa-times-circle"></i></span><br>
                                    Expired
                                </th>
                                <th>
                                    <span class="text-secondary"><i class="fas fa-user-slash"></i></span><br>
                                    Inactive
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr class="fw-bold fs-4">
                                <td class="text-success"><?= htmlspecialchars($count_active ?? 0) ?></td>
                                <td class="text-warning"><?= htmlspecialchars($count_expiring ?? 0) ?></td>
                                <td class="text-danger"><?= htmlspecialchars($count_expired ?? 0) ?></td>
                                <td class="text-secondary"><?= htmlspecialchars($count_inactive ?? 0) ?></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- CONNECTION CARDS -->
<div class="row mb-4">
    <div class="col-md-6 mb-3">
        <div class="card shadow-sm text-center border-0 border-start border-4 border-success">
            <div class="card-body">
                <i class="fas fa-link fs-3 text-success mb-2"></i>
                <h3 class="fw-bold"><?= htmlspecialchars($count_connected ?? 0) ?></h3>
                <div class="text-muted">Connected</div>
            </div>
        </div>
    </div>

    <div class="col-md-6 mb-3">
        <div class="card shadow-sm text-center border-0 border-start border-4 border-secondary">
            <div class="card-body">
                <i class="fas fa-unlink fs-3 text-secondary mb-2"></i>
                <h3 class="fw-bold"><?= htmlspecialchars($count_not_connected ?? 0) ?></h3>
                <div class="text-muted">Not Connected</div>
            </div>
        </div>
    </div>
</div>

<!-- FILTER BAR -->
<div class="card shadow-sm mb-4">
<div class="card-body">

<form id="filterForm" class="row g-3 align-items-end" method="get">

<div class="col-lg-3 col-md-6">
<input id="searchInput" type="text" name="search"
value="<?= htmlspecialchars($search) ?>"
class="form-control"
placeholder="Search username or name...">
</div>

<div class="col-lg-2 col-md-6">
<select name="status" class="form-select">
<option value="" <?= $status_filter==''?'selected':'' ?>>All Statuses</option>
<option value="active" <?= $status_filter=='active'?'selected':'' ?>>Active</option>
<option value="expiring" <?= $status_filter=='expiring'?'selected':'' ?>>Expiring</option>
<option value="expired" <?= $status_filter=='expired'?'selected':'' ?>>Expired</option>
<option value="inactive" <?= $status_filter=='inactive'?'selected':'' ?>>Inactive</option>
</select>
</div>

<div class="col-lg-2 col-md-6">
<select name="device" class="form-select">
<option value="" <?= $device_filter==''?'selected':'' ?>>All MT Devices</option>
<?php foreach ($device_names as $d): ?>
<option value="<?= htmlspecialchars($d) ?>" <?= $device_filter==$d?'selected':'' ?>>
<?= htmlspecialchars($d) ?>
</option>
<?php endforeach; ?>
</select>
</div>

<div class="col-lg-2 col-md-6">
<select name="connection" class="form-select">
<option value="" <?= $connection_filter==''?'selected':'' ?>>All Connections</option>
<option value="Connected" <?= $connection_filter=='Connected'?'selected':'' ?>>Connected</option>
<option value="Not Connected" <?= $connection_filter=='Not Connected'?'selected':'' ?>>Not Connected</option>
</select>
</div>

<div class="col-lg-2 col-md-6 d-flex gap-2">
<button type="submit" class="btn btn-primary w-100">
<i class="fas fa-search"></i>
</button>

<button type="button" class="btn btn-outline-secondary w-100" onclick="location.reload();">
<i class="fas fa-sync-alt"></i>
</button>
</div>

<div class="col-lg-1 col-md-6">
<select name="per_page" class="form-select">
<?php foreach ([10,20,35,50,100] as $n): ?>
<option value="<?= $n ?>" <?= $per_page==$n?'selected':'' ?>>
<?= $n ?>
</option>
<?php endforeach; ?>
</select>
</div>

</form>
</div>
</div>





















<?php
function sort_link($label, $column, $current_sort, $current_order) {
    $curSort = $current_sort;
    $curOrder = strtoupper($current_order);
    $isActive = ($curSort === $column);
    $nextOrder = ($isActive && $curOrder === 'ASC') ? 'desc' : 'asc';
    $query = $_GET;
    $query['sort'] = $column;
    $query['order'] = $nextOrder;
    $url = '?' . http_build_query($query);
    $icon = '';
    if ($isActive) {
        $icon = ($curOrder === 'ASC') ? '<i class="fas fa-sort-up"></i>' : '<i class="fas fa-sort-down"></i>';
    }
    return '<a href="' . htmlspecialchars($url, ENT_QUOTES, 'UTF-8') . '" style="text-decoration:none; color:inherit;">' .
           htmlspecialchars($label, ENT_QUOTES, 'UTF-8') . ' ' . $icon . '</a>';
}









function get_uptime_downtime_html($username, $connected_usernames, $ppp_users_status) {

    if (isset($connected_usernames[$username])) {
        $uptime = $connected_usernames[$username]['uptime'] ?? '';
        if ($uptime == '') $uptime = '0s';

        return '<span class="badge bg-success">Uptime: '.htmlspecialchars($uptime).'</span>';
    }

    if (isset($ppp_users_status[$username]['last_logged_out'])) {
        $last = $ppp_users_status[$username]['last_logged_out'];

        if ($last != '') {
            $last_time = strtotime($last);
            if ($last_time) {
                $diff = time() - $last_time;

                $days = floor($diff / 86400);
                $hours = floor(($diff % 86400) / 3600);
                $mins = floor(($diff % 3600) / 60);

                $down = '';
                if ($days > 0) $down .= $days.'d ';
                if ($hours > 0) $down .= $hours.'h ';
                $down .= $mins.'m';

                return '<span class="badge bg-danger">Down: '.$down.'</span>';
            }
        }
    }

    return '<span class="badge bg-secondary">Unknown</span>';
}










?>




<div class="table-responsive d-none d-lg-block small-table" aria-label="Desktop table">
    <table class="table table-striped table-bordered">
        <thead class="table-light">
            <tr>
                <th>Status</th>
                <th><?= sort_link('Expires At', 'expires_at', $sort, $order) ?></th>
<th>Router Status</th>
<th>Account Type</th>
<th>Uptime / Downtime</th>
<th>Profile</th>

                <th>Action</th>
                <th><?= sort_link('ID', 'id', $sort, $order) ?></th>
                <th><?= sort_link('Username', 'username', $sort, $order) ?></th>
                <th><?= sort_link('MT Device', 'device_name', $sort, $order) ?></th>
                <th><?= sort_link('Full Name', 'full_name', $sort, $order) ?></th>
                <th><?= sort_link('Address', 'address', $sort, $order) ?></th>
                <th><?= sort_link('Plan Name', 'plan_name', $sort, $order) ?></th>
                <th><?= sort_link('Price', 'price', $sort, $order) ?></th>
            </tr>
        </thead>
        <tbody>
        <?php if ($rows && count($rows) > 0): ?>
            <?php foreach ($rows as $row): ?>
            <tr>
                <td><?= get_status_html($row, $now_unix, $soon_unix, $inactive_limit_unix, 'desktop'); ?></td>
                <td><?= htmlspecialchars($row['expires_at'], ENT_QUOTES, 'UTF-8') ?></td>
<td><?= get_connection_status_html($row['username'], $connected_usernames) ?></td>
<td><?= get_account_type_html($row['account_type']) ?></td>

<td><?= get_uptime_downtime_html($row['username'], $connected_usernames, $ppp_users_status) ?></td>
<td><?= get_ppp_profile_html($row['username'], $ppp_users_status) ?></td>


                <td>
                    <a href="user_view.php?id=<?= urlencode($row['id']) ?>" class="btn btn-info btn-sm" title="View"><i class="fas fa-eye"></i></a>
                    <a href="pay.php?username=<?= urlencode($row['username']) ?>" class="btn btn-success btn-sm" title="Pay"><i class="fas fa-credit-card"></i></a>
                    <a href="pay_rebates.php?username=<?= urlencode($row['username']) ?>" class="btn btn-warning btn-sm" title="Rebates"><i class="fa-solid fa-coins"></i></a>
                    <a href="pay_readjustments.php?username=<?= urlencode($row['username']) ?>" class="btn btn-danger btn-sm" title="Re-Adjustments"><i class="fa-regular fa-face-meh"></i></a>
                  <a href="statement_of_account.php?username=<?= urlencode($row['username']) ?>"class="btn btn-success btn-sm"><i class="bi bi-file-earmark-text"></i> SOA
</a>
 <a href="user_logs.php?username=<?= urlencode($row['username']) ?>" class="btn btn-secondary btn-sm" title="User Log"><i class="fas fa-clipboard-list"></i></a>
                    <a href="user_logs_rebates.php?username=<?= urlencode($row['username']) ?>" class="btn btn-secondary btn-sm" title="User Log Rebates/Re-adjustments"><i class="fa-solid fa-person-walking-dashed-line-arrow-right"></i></a>
                </td>
                <td><?= htmlspecialchars($row['id'], ENT_QUOTES, 'UTF-8') ?></td>
                <td><?= htmlspecialchars($row['username'], ENT_QUOTES, 'UTF-8') ?></td>
                <td>
                    <?php if (!empty($row['device_name'])): ?>
                        <span class="badge bg-warning text-dark"><?= htmlspecialchars($row['device_name'], ENT_QUOTES, 'UTF-8') ?></span>
                    <?php else: ?>
                        <span class="badge bg-secondary">None</span>
                    <?php endif; ?>
                </td>
                <td><?= htmlspecialchars($row['full_name'], ENT_QUOTES, 'UTF-8') ?></td>
                <td><?= htmlspecialchars($row['address'], ENT_QUOTES, 'UTF-8') ?></td>
                <td><?= htmlspecialchars($row['plan_name'], ENT_QUOTES, 'UTF-8') ?></td>
                <td><?= htmlspecialchars(number_format((float)$row['price'], 2), ENT_QUOTES, 'UTF-8') ?></td>
            </tr>
            <?php endforeach; ?>
        <?php else: ?>
            <tr><td colspan="12" class="text-center text-muted">No results found.</td></tr>
        <?php endif; ?>
        </tbody>
    </table>
</div>

<div class="d-lg-none" aria-label="Mobile cards" id="mobileCards">
    <?php if ($rows && count($rows) > 0): ?>
        <?php foreach ($rows as $row): ?>
            <div class="subscription-card mb-4 shadow-sm">
                <div class="mb-2 fw-bold"><?= get_status_html($row, $now_unix, $soon_unix, $inactive_limit_unix, 'mobile'); ?></div>
                <div class="row g-0">
                    <div class="col-6"><span class="card-label">Expires At:</span></div>
                    <div class="col-6"><?= !empty($row['expires_at']) ? htmlspecialchars($row['expires_at'], ENT_QUOTES, 'UTF-8') : 'N/A' ?></div>

                    <div class="col-6"><span class="card-label">ID:</span></div>
                    <div class="col-6"><?= htmlspecialchars($row['id'], ENT_QUOTES, 'UTF-8') ?></div>

                    <div class="col-6"><span class="card-label">Username:</span></div>
                    <div class="col-6"><?= htmlspecialchars($row['username'], ENT_QUOTES, 'UTF-8') ?></div>

                    <div class="col-6"><span class="card-label">Router Status:</span></div>
                    <div class="col-6"><?= get_connection_status_html($row['username'], $connected_usernames) ?></div>

                    <div class="col-6"><span class="card-label">Account Type:</span></div>
                    <div class="col-6"><?= get_account_type_html($row['account_type']) ?></div>



                    

<div class="col-6"><span class="card-label">Uptime / Downtime:</span></div>
<div class="col-6"><?= get_uptime_downtime_html($row['username'], $connected_usernames, $ppp_users_status) ?></div>



                    <div class="col-6"><span class="card-label">Profile:</span></div>
                    <div class="col-6"><?= get_ppp_profile_html($row['username'], $ppp_users_status) ?></div>

                    <div class="col-6"><span class="card-label">Full Name:</span></div>
                    <div class="col-6"><?= htmlspecialchars($row['full_name'], ENT_QUOTES, 'UTF-8') ?></div>

                    <div class="col-6"><span class="card-label">Address:</span></div>
                    <div class="col-6"><?= htmlspecialchars($row['address'], ENT_QUOTES, 'UTF-8') ?></div>

                    <div class="col-6"><span class="card-label">Plan Name:</span></div>
                    <div class="col-6"><?= htmlspecialchars($row['plan_name'], ENT_QUOTES, 'UTF-8') ?></div>

                    <div class="col-6"><span class="card-label">Price:</span></div>
                    <div class="col-6"><?= htmlspecialchars(number_format((float)$row['price'], 2), ENT_QUOTES, 'UTF-8') ?></div>

                    <div class="col-6"><span class="card-label">MT Device:</span></div>
                    <div class="col-6"><?= !empty($row['device_name'])
                        ? '<span class="badge bg-warning text-dark">'.htmlspecialchars($row['device_name'], ENT_QUOTES, 'UTF-8').'</span>'
                        : '<span class="badge bg-secondary">None</span>' ?></div>
                </div>
                <div class="mt-3 d-flex flex-wrap gap-2">
                    <a href="user_view.php?id=<?= urlencode($row['id']) ?>" class="btn btn-info btn-sm flex-fill" title="View"><i class="fas fa-eye"></i></a>
                    <a href="pay.php?username=<?= urlencode($row['username']) ?>" class="btn btn-success btn-sm flex-fill" title="Pay"><i class="fas fa-credit-card"></i></a>
                    <a href="pay_rebates.php?username=<?= urlencode($row['username']) ?>" class="btn btn-warning btn-sm flex-fill" title="Rebates"><i class="fa-solid fa-coins"></i></a>
                    <a href="pay_readjustments.php?username=<?= urlencode($row['username']) ?>" class="btn btn-danger btn-sm flex-fill" title="Re-Adjustments"><i class="fa-regular fa-face-meh"></i></a>
                    <a href="user_logs.php?username=<?= urlencode($row['username']) ?>" class="btn btn-secondary btn-sm flex-fill" title="User Log"><i class="fas fa-clipboard-list"></i></a>
                    <a href="user_logs_rebates.php?username=<?= urlencode($row['username']) ?>" class="btn btn-secondary btn-sm flex-fill" title="User Log Rebates/Re-adjustments"><i class="fa-solid fa-person-walking-dashed-line-arrow-right"></i></a>
                </div>
            </div>
        <?php endforeach; ?>
    <?php endif; ?>
</div>

<br>

<?php if ($total_pages > 1): ?>
    <?php
    $query_string = $_GET;
    $query_string['sort']  = $sort;
    $query_string['order'] = strtolower($order);

    $prevPage = max(1, $page - 1);
    $nextPage = min($total_pages, $page + 1);

    // how many neighbors to show around current page
    $delta = 1;

    $pages = [1, $total_pages, $page];
    for ($p = $page - $delta; $p <= $page + $delta; $p++) {
        if ($p >= 1 && $p <= $total_pages) $pages[] = $p;
    }
    $pages = array_values(array_unique($pages));
    sort($pages);

    $pageUrl = function($p) use ($query_string, $per_page) {
        return '?' . http_build_query(array_merge($query_string, ['page' => $p, 'per_page' => $per_page]));
    };
    ?>

    <style>
        /* Mobile-friendly pagination */
        .pagination { flex-wrap: wrap; gap: .25rem; }
        .pagination .page-link { padding: .375rem .6rem; }
        @media (max-width: 576px) {
            .pagination { justify-content: center; }
        }
    </style>

    <nav aria-label="Page navigation">
        <ul class="pagination pagination-sm justify-content-center">
            <li class="page-item <?= ($page == 1) ? 'disabled' : '' ?>">
                <a class="page-link" href="<?= $pageUrl($prevPage) ?>" aria-label="Prev">&laquo;</a>
            </li>

            <?php
            $prevShown = null;
            foreach ($pages as $p):
                if ($prevShown !== null && $p > $prevShown + 1): ?>
                    <li class="page-item disabled d-none d-sm-block">
                        <span class="page-link">…</span>
                    </li>
                <?php endif; ?>

                <li class="page-item <?= ($p == $page) ? 'active' : '' ?>">
                    <a class="page-link" href="<?= $pageUrl($p) ?>"><?= $p ?></a>
                </li>

                <?php $prevShown = $p;
            endforeach; ?>

            <li class="page-item <?= ($page == $total_pages) ? 'disabled' : '' ?>">
                <a class="page-link" href="<?= $pageUrl($nextPage) ?>" aria-label="Next">&raquo;</a>
            </li>
        </ul>
    </nav>
<?php endif; ?>


</main>

<script>
function startCountdown() {
    function formatTimer(seconds) {
        if (seconds < 0) seconds = 0;
        const d = Math.floor(seconds / (24 * 60 * 60));
        seconds %= 24 * 60 * 60;
        const h = Math.floor(seconds / (60 * 60));
        seconds %= 60 * 60;
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        let parts = [];
        if (d > 0) parts.push(d+'d');
        if (h > 0 || d > 0) parts.push(h+'h');
        if (m > 0 || h > 0 || d > 0) parts.push(m+'m');
        parts.push(s+'s');
        return parts.join(' ');
    }

    function updateAllCountdowns() {
        const now = Math.floor(Date.now() / 1000);
        document.querySelectorAll('[id^="countdown-"]').forEach(function(el) {
            const secondsLeftAttr = el.getAttribute('data-seconds');
            if (secondsLeftAttr === null) return;

            const orig = parseInt(el.getAttribute('data-seconds'), 10);
            const start = parseInt(el.getAttribute('data-start') || (now), 10);
            const elapsed = now - start;
            const secondsLeft = orig - elapsed;

            const timeSpan = el.querySelector('.time');
            if (timeSpan) timeSpan.textContent = formatTimer(secondsLeft);

            if (secondsLeft <= 0) {
                el.innerHTML = '<span class="status-icon status-expired" aria-label="Expired"><i class="fas fa-times-circle"></i></span> <span style="color:#dc3545;">Expired</span>';
            }
        });
    }

    if (window._countdownTimerRunning) return;
    window._countdownTimerRunning = true;
    setInterval(updateAllCountdowns, 1000);
    updateAllCountdowns();
}
document.addEventListener('DOMContentLoaded', startCountdown);
</script>
</body>














</html>
