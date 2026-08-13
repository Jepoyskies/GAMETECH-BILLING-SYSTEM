<?php
// pppoe_user_management.php

require_once __DIR__ . '/MikroTikManager/MikrotikManager_mtpppoe_list.php';
require_once __DIR__ . '/database.php';            // must expose $pdo
require_once __DIR__ . '/log_system_action.php';   // must expose log_system_action($pdo, ...)



include 'header.php';

// --- PPPoE User Deletion: MikroTik + Database + Logging ---
$toast = null;

if (isset($_GET['delete']) && $_SERVER['REQUEST_METHOD'] === 'GET') {
    $usernameToDelete = trim($_GET['delete']);

    if ($usernameToDelete !== '') {
        try {
            // 1. Fetch old data for logging
            $stmtOld = $pdo->prepare("SELECT * FROM customers WHERE username = ?");
            $stmtOld->execute([$usernameToDelete]);
            $old_data = $stmtOld->fetch(PDO::FETCH_ASSOC);

            // 2. Get device_name
            $stmt = $pdo->prepare("SELECT device_name FROM pppoe_users WHERE username = ?");
            $stmt->execute([$usernameToDelete]);
            $device_name = $stmt->fetchColumn();

            if (!$device_name) {
                $toast = [
                    'type' => 'warning',
                    'msg'  => "User <b>" . htmlspecialchars($usernameToDelete) . "</b> not found in database."
                ];
            } else {
                // 3. Get MikroTik device info
                $deviceStmt = $pdo->prepare("
                    SELECT ip_address, api_username, api_password, api_port 
                    FROM mikrotik_devices 
                    WHERE device_name = ?
                ");
                $deviceStmt->execute([$device_name]);
                $device = $deviceStmt->fetch(PDO::FETCH_ASSOC);

                if (!$device) {
                    $toast = [
                        'type' => 'warning',
                        'msg'  => "Device <b>" . htmlspecialchars($device_name) . "</b> not found."
                    ];
                } else {

                    // 4. Connect to MikroTik
                    $mt = new MikroTikManager(
                        $device['ip_address'],
                        $device['api_username'],
                        $device['api_password'],
                        $device['api_port']
                    );

                    $mt->connect();

                    // ✅ IMPORTANT: Check if user exists first
                    $userExists = $mt->pppoeUserExists($usernameToDelete);

                    if (!$userExists) {
                        $mt->disconnect();

                        $toast = [
                            'type' => 'warning',
                            'msg'  => "User <b>" . htmlspecialchars($usernameToDelete) . "</b> does not exist on MikroTik. Deletion cancelled."
                        ];
                    } else {

                        // Try deleting
                        $deleted = $mt->deletePppoeUser($usernameToDelete);
                        $mt->disconnect();

                        if (!$deleted) {
                            // ❌ Stop if deletion failed
                            $toast = [
                                'type' => 'danger',
                                'msg'  => "Failed to delete <b>" . htmlspecialchars($usernameToDelete) . "</b> on MikroTik. No database changes made."
                            ];
                        } else {

                            // ✅ Only now proceed with DB deletion
                            $pdo->beginTransaction();

                            // Delete from pppoe_users
                            $stmt1 = $pdo->prepare("DELETE FROM pppoe_users WHERE username = ?");
                            $stmt1->execute([$usernameToDelete]);

                            // Delete from customers
                            $stmt2 = $pdo->prepare("DELETE FROM customers WHERE username = ?");
                            $stmt2->execute([$usernameToDelete]);

                            // Logging
                            $customer_id_for_log = $old_data['id'] ?? null;
                            $changed_by = $_SESSION['username'] ?? 'system';

                            if ($customer_id_for_log !== null) {
                                log_system_action(
                                    $pdo,
                                    'customers',
                                    $customer_id_for_log,
                                    'delete',
                                    $changed_by,
                                    $old_data,
                                    null
                                );
                            }

                            $pdo->commit();

                            $toast = [
                                'type' => 'success',
                                'msg'  => "User <b>" . htmlspecialchars($usernameToDelete) . "</b> deleted successfully from MikroTik and database."
                            ];
                        }
                    }
                }
            }
        } catch (Exception $e) {
            if ($pdo->inTransaction()) {
                $pdo->rollBack();
            }

            $toast = [
                'type' => 'danger',
                'msg'  => "Error: " . htmlspecialchars($e->getMessage())
            ];
        }
    }
}





if (isset($_GET['sync']) && $_SERVER['REQUEST_METHOD'] === 'GET') {
    $usernameToSync = trim($_GET['sync']);

    if ($usernameToSync !== '') {
        try {
            // 1. Get user from DB
            $stmt = $pdo->prepare("
    SELECT p.*, c.plan_name 
    FROM pppoe_users p
    LEFT JOIN customers c ON p.username = c.username
    WHERE p.username = ?
");
$stmt->execute([$usernameToSync]);
$user = $stmt->fetch(PDO::FETCH_ASSOC);


            if (!$user) {
    $toast = [
        'type' => 'warning',
        'msg'  => "User <b>" . htmlspecialchars($usernameToSync) . "</b> not found in database."
    ];
} elseif (empty($user['plan_name'])) {
    $toast = [
        'type' => 'danger',
        'msg'  => "User <b>" . htmlspecialchars($usernameToSync) . "</b> has no plan assigned."
    ];
} else {


                // 2. Get ALL MikroTik devices
                $allDevicesStmt = $pdo->query("
                    SELECT device_name, ip_address, api_username, api_password, api_port 
                    FROM mikrotik_devices
                ");
                $allDevices = $allDevicesStmt->fetchAll(PDO::FETCH_ASSOC);

                $targetDeviceName = $user['device_name'];
                $targetDevice = null;

                foreach ($allDevices as $dev) {
                    if ($dev['device_name'] === $targetDeviceName) {
                        $targetDevice = $dev;
                        continue;
                    }

                    // ✅ DELETE user from OTHER devices
                    try {
                        $mtOther = new MikroTikManager(
                            $dev['ip_address'],
                            $dev['api_username'],
                            $dev['api_password'],
                            $dev['api_port']
                        );

                        $mtOther->connect();

                        if ($mtOther->pppoeUserExists($usernameToSync)) {
                            $mtOther->deletePppoeUser($usernameToSync);
                        }

                        $mtOther->disconnect();

                    } catch (Exception $e) {
                        // skip failure but continue
                    }
                }

                if (!$targetDevice) {
                    $toast = [
                        'type' => 'danger',
                        'msg'  => "Target device not found for user <b>" . htmlspecialchars($usernameToSync) . "</b>."
                    ];
                } else {

                    // ✅ SYNC TO CORRECT DEVICE
                    $mt = new MikroTikManager(
                        $targetDevice['ip_address'],
                        $targetDevice['api_username'],
                        $targetDevice['api_password'],
                        $targetDevice['api_port']
                    );

                    $mt->connect();

                    $exists = $mt->pppoeUserExists($usernameToSync);

                    if ($exists) {
                        $mt->updatePppoeUser(
                            $usernameToSync,
                            $user['plan_name']
                        );

                        $mt->disconnect();

                        $toast = [
                            'type' => 'info',
                            'msg'  => "User <b>$usernameToSync</b> updated and cleaned from other devices."
                        ];
                    } else {
                        $created = $mt->addPppoeUser(
                            $usernameToSync,
                            $user['password'],
                            $user['plan_name']
                        );

                        $mt->disconnect();

                        if ($created) {
                            $toast = [
                                'type' => 'success',
                                'msg'  => "User <b>$usernameToSync</b> synced and removed from other devices."
                            ];
                        } else {
                            $toast = [
                                'type' => 'danger',
                                'msg'  => "Failed to sync user <b>$usernameToSync</b>."
                            ];
                        }
                    }
                }
            }
        } catch (Exception $e) {
            $toast = [
                'type' => 'danger',
                'msg'  => "Error: " . htmlspecialchars($e->getMessage())
            ];
        }
    }
}







// ------------ Pagination, Search, Device Filter & Sorting ------------
$perPage      = 10;
$page         = isset($_GET['page']) && is_numeric($_GET['page']) ? max(1, (int)$_GET['page']) : 1;
$search       = isset($_GET['search']) ? trim($_GET['search']) : '';
$deviceFilter = isset($_GET['device']) ? trim($_GET['device']) : '';

$validSortColumns = [
    'username'    => 'p.username',
    'profile'     => 'p.profile',
    'plan_name'   => 'c.plan_name',
    'created'     => 'p.created_at',
    'device_name' => 'p.device_name'
];

$sort  = isset($_GET['sort']) ? $_GET['sort'] : 'created';
$order = isset($_GET['order']) ? strtolower($_GET['order']) : 'desc';

if (!isset($validSortColumns[$sort])) {
    $sort = 'created';
}
if (!in_array($order, ['asc', 'desc'], true)) {
    $order = 'desc';
}
$orderBySql = $validSortColumns[$sort] . ' ' . strtoupper($order);

// ---- Build WHERE + positional params once ----
$whereParts = [];
$params     = [];

if ($search !== '') {
    $whereParts[] = "(p.username LIKE ? OR p.profile LIKE ? OR c.plan_name LIKE ?)";
$like = "%$search%";
$params[] = $like;
$params[] = $like;
$params[] = $like;

}
if ($deviceFilter !== '') {
    $whereParts[] = "device_name LIKE ?";
    $params[] = '%' . $deviceFilter . '%';
}

$whereSql = '';
if (!empty($whereParts)) {
    $whereSql = 'WHERE ' . implode(' AND ', $whereParts);
}

// ---- COUNT query ----
$countSql  = "
    SELECT COUNT(*) 
    FROM pppoe_users p
    LEFT JOIN customers c ON p.username = c.username
    $whereSql
";
$countStmt = $pdo->prepare($countSql);
$countStmt->execute($params);
$totalRows   = (int)$countStmt->fetchColumn();
$totalPages  = (int)ceil($totalRows / $perPage);
$offset      = ($page - 1) * $perPage;

// ---- DATA query ----
$dataSql = "
    SELECT 
        p.username, 
        p.profile,
        c.plan_name,
        p.device_name, 
        p.created_at
    FROM pppoe_users p
    LEFT JOIN customers c ON p.username = c.username
    $whereSql
    ORDER BY $orderBySql
    LIMIT ? OFFSET ?
";


$dataStmt = $pdo->prepare($dataSql);
$dataParams   = $params;
$dataParams[] = (int)$perPage;
$dataParams[] = (int)$offset;
$dataStmt->execute($dataParams);
$users = $dataStmt->fetchAll(PDO::FETCH_ASSOC);

// For device filter dropdown
$deviceListStmt  = $pdo->query("SELECT DISTINCT device_name FROM pppoe_users ORDER BY device_name ASC");
$allDeviceNames  = $deviceListStmt->fetchAll(PDO::FETCH_COLUMN);

// --- Sort link helper ---
function sort_link(string $caption, string $column, string $currentSort, string $currentOrder, array $extraParams = []): string {
    $order = 'asc';
    $icon  = '';
    if ($currentSort === $column) {
        if ($currentOrder === 'asc') {
            $order = 'desc';
            $icon  = ' <i class="fas fa-sort-up"></i>';
        } else {
            $order = 'asc';
            $icon  = ' <i class="fas fa-sort-down"></i>';
        }
    }
    $params = array_merge($extraParams, ['sort' => $column, 'order' => $order]);
    $url    = '?' . http_build_query($params);
    return '<a href="' . htmlspecialchars($url) . '" class="text-decoration-none">' . $caption . $icon . '</a>';
}

$baseQueryParams = ['search' => $search, 'device' => $deviceFilter, 'page' => $page];

?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PPPoe User Management</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
  <style>
    .toast-container { position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 1080; }
  </style>
</head>
<body>
<main class="container py-5" style="min-height: 100vh;">

<!-- Toast Notification -->
<div class="toast-container">
  <?php if ($toast): ?>
    <div class="toast align-items-center text-bg-<?= htmlspecialchars($toast['type']) ?> border-0 show" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body"><?= $toast['msg'] ?></div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  <?php endif; ?>
</div>

<div class="d-flex align-items-center flex-wrap gap-2 mb-4">
  <button type="button" class="btn btn-outline-secondary d-flex align-items-center px-3 py-2 fw-bold" onclick="window.location.href='customers.php';">
    <i class="fas fa-arrow-left me-2"></i> Back
  </button>
  <button type="button" class="btn btn-outline-info d-flex align-items-center px-3 py-2 fw-bold" onclick="location.reload();" title="Refresh">
    <i class="fas fa-sync-alt me-2"></i> Refresh
  </button>
  <span class="vr mx-2 d-none d-md-block" aria-hidden="true"></span>
  <form class="d-flex flex-wrap gap-2 flex-grow-1" method="get" action="">
    <div class="input-group flex-grow-1" style="min-width: 220px;">
      <input class="form-control form-control-lg" type="search" name="search" placeholder="Search by username or profile..." value="<?php echo htmlspecialchars($search); ?>" aria-label="Search" style="font-size: 1.05rem;">
      <button class="btn btn-primary btn-lg" type="submit" aria-label="Search"><i class="fas fa-search me-1"></i> Search</button>
    </div>
    <div class="input-group" style="max-width: 260px;">
      <label class="input-group-text" for="device-filter">Device Name</label>
      <select class="form-select" id="device-filter" name="device" onchange="this.form.submit()">
        <option value="">All Devices</option>
        <?php foreach ($allDeviceNames as $devName): ?>
          <option value="<?php echo htmlspecialchars($devName); ?>" <?php if ($deviceFilter === $devName) echo 'selected'; ?>>
            <?php echo htmlspecialchars($devName); ?>
          </option>
        <?php endforeach; ?>
      </select>
    </div>
    <input type="hidden" name="sort" value="<?php echo htmlspecialchars($sort); ?>">
    <input type="hidden" name="order" value="<?php echo htmlspecialchars($order); ?>">
  </form>
</div>

<h5 class="mb-3">Current PPPoE Users (Database):</h5>
<div class="d-none d-md-block mb-4">
  <div class="table-responsive">
    <table class="table table-striped table-sm align-middle">
      <thead class="table-light">
        <tr>
          <th><?php echo sort_link('Username', 'username', $sort, $order, $baseQueryParams); ?></th>
          <th><?php echo sort_link('Profile', 'profile', $sort, $order, $baseQueryParams); ?></th>
<th><?php echo sort_link('Plan', 'plan_name', $sort, $order, $baseQueryParams); ?></th>
<th><?php echo sort_link('Device Name', 'device_name', $sort, $order, $baseQueryParams); ?></th>

          <th class="d-none d-sm-table-cell"><?php echo sort_link('Created', 'created', $sort, $order, $baseQueryParams); ?></th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        <?php foreach ($users as $row): ?>
          <tr>
            <td data-label="Username"><?= htmlspecialchars($row['username']) ?></td>
           <td data-label="Profile"><?= htmlspecialchars($row['profile']) ?></td>
<td data-label="Plan"><?= htmlspecialchars($row['plan_name'] ?? '') ?></td>
<td data-label="Device Name"><?= htmlspecialchars($row['device_name'] ?? '') ?></td>

            <td data-label="Created" class="d-none d-sm-table-cell"><?= htmlspecialchars($row['created_at']) ?></td>
            <td data-label="Action">
              <a href="?delete=<?= urlencode($row['username']) ?>&<?= http_build_query(['search' => $search, 'page' => $page, 'device' => $deviceFilter, 'sort' => $sort, 'order' => $order]) ?>"
                 class="btn btn-danger btn-sm"
                 onclick="return confirm('Delete user <?= htmlspecialchars($row['username'], ENT_QUOTES) ?>?');">
                Delete
              </a>


<a href="?sync=<?= urlencode($row['username']) ?>&<?= http_build_query(['search' => $search, 'page' => $page, 'device' => $deviceFilter, 'sort' => $sort, 'order' => $order]) ?>"
   class="btn btn-success btn-sm"
   onclick="return confirm('Sync user <?= htmlspecialchars($row['username'], ENT_QUOTES) ?> to MikroTik?');">
   Sync
</a>

    </td>


            
          </tr>
        <?php endforeach ?>
        <?php if (empty($users)): ?>
          <tr><td colspan="6" class="text-center">No users found.</td></tr>

        <?php endif; ?>
      </tbody>
    </table>
  </div>
</div>












<!-- Mobile stacked cards (visible on small screens) -->
<div class="d-block d-md-none">
  <?php foreach ($users as $row): ?>
    <div class="card mb-3 shadow-sm">
      <div class="card-body p-2">
        <div class="row g-2 align-items-center">
          <div class="col-12"><strong class="d-block">Username</strong><span><?= htmlspecialchars($row['username']) ?></span></div>
          <div class="col-12"><strong class="d-block mt-1">Profile</strong><span><?= htmlspecialchars($row['profile']) ?></span></div>
<div class="col-12"><strong class="d-block mt-1">Plan</strong><span><?= htmlspecialchars($row['plan_name'] ?? '') ?></span></div>
<div class="col-12"><strong class="d-block mt-1">Device Name</strong><span><?= htmlspecialchars($row['device_name'] ?? '') ?></span></div>

          <div class="col-12"><strong class="d-block mt-1">Created</strong><span><?= htmlspecialchars($row['created_at']) ?></span></div>
          <div class="col-12 mt-2">
            <a href="?delete=<?= urlencode($row['username']) ?>&<?= http_build_query(['search' => $search, 'page' => $page, 'device' => $deviceFilter, 'sort' => $sort, 'order' => $order]) ?>"
               class="btn btn-danger btn-sm w-100"
               onclick="return confirm('Delete user <?= htmlspecialchars($row['username'], ENT_QUOTES) ?>?');">
              Delete
            </a>
          </div>
        </div>
      </div>
    </div>
  <?php endforeach; ?>
  <?php if (empty($users)): ?>
    <div class="text-center text-muted">No users found.</div>
  <?php endif; ?>
</div>















<!-- Pagination Controls -->
<nav aria-label="Page navigation" class="mt-3">
  <ul class="pagination justify-content-center">
    <?php
      $pageParams = ['search' => $search, 'device' => $deviceFilter, 'sort' => $sort, 'order' => $order];
    ?>
    <?php if ($page > 1): ?>
      <li class="page-item">
        <a class="page-link" href="?<?= http_build_query($pageParams + ['page' => $page - 1]) ?>">&laquo; Prev</a>
      </li>
    <?php endif; ?>
    <?php
      $start = max(1, $page - 2);
      $end   = min($totalPages, $page + 2);
      for ($i = $start; $i <= $end; $i++): ?>
      <li class="page-item <?= ($i == $page) ? 'active' : '' ?>">
        <a class="page-link" href="?<?= http_build_query($pageParams + ['page' => $i]) ?>"><?= $i ?></a>
      </li>
    <?php endfor; ?>
    <?php if ($page < $totalPages): ?>
      <li class="page-item">
        <a class="page-link" href="?<?= http_build_query($pageParams + ['page' => $page + 1]) ?>">Next &raquo;</a>
      </li>
    <?php endif; ?>
  </ul>
</nav>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
  document.addEventListener('DOMContentLoaded', function () {
    const toastEl = document.querySelector('.toast');
    if (toastEl) {
      const bsToast = new bootstrap.Toast(toastEl, { delay: 3000 });
      bsToast.show();
    }
  });
</script>
</main>
<?php include 'footer.php'; ?>
</body>
</html>
