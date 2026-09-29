<?php
require_once __DIR__ . '/MikroTikManager/MikrotikManager_mtpppoe_synchronize_mt.php';
require_once __DIR__ . '/database.php';

include 'header.php';

$toast = null;

/* =========================
   SYNC USERS (OPTIMIZED)
========================= */
if (isset($_GET['sync'])) {
    try {
        $stmt = $pdo->query("SELECT * FROM pppoe_users");
        $users = $stmt->fetchAll(PDO::FETCH_ASSOC);

        // group users per device ✅ (IMPORTANT OPTIMIZATION)
        $devices = [];

        foreach ($users as $u) {
            $devices[$u['device_name']][] = $u;
        }

        $totalSynced = 0;

        foreach ($devices as $deviceName => $deviceUsers) {

            $d = $pdo->prepare("SELECT * FROM mikrotik_devices WHERE device_name=?");
            $d->execute([$deviceName]);
            $device = $d->fetch(PDO::FETCH_ASSOC);

            if (!$device) continue;

            $mt = new MikroTikManager(
                $device['ip_address'],
                $device['api_username'],
                $device['api_password'],
                $device['api_port']
            );

            $mt->connect();

            foreach ($deviceUsers as $u) {
                $mt->addOrUpdatePppoeUser(
                    $u['username'],
                    'gametechisp',
                    $u['profile']
                );
                $totalSynced++;
            }

            $mt->disconnect();
        }

        $toast = ['type'=>'success','msg'=>"✅ Synced $totalSynced users"];

    } catch (Exception $e) {
        $toast = ['type'=>'danger','msg'=>$e->getMessage()];
    }
}

/* =========================
   DELETE USER
========================= */
if (isset($_GET['delete'])) {
    $username = $_GET['delete'];

    try {
        $stmt = $pdo->prepare("SELECT device_name FROM pppoe_users WHERE username=?");
        $stmt->execute([$username]);
        $deviceName = $stmt->fetchColumn();

        if ($deviceName) {
            $d = $pdo->prepare("SELECT * FROM mikrotik_devices WHERE device_name=?");
            $d->execute([$deviceName]);
            $device = $d->fetch(PDO::FETCH_ASSOC);

            if ($device) {
                $mt = new MikroTikManager(
                    $device['ip_address'],
                    $device['api_username'],
                    $device['api_password'],
                    $device['api_port']
                );
                $mt->connect();
                $mt->deletePppoeUser($username);
                $mt->disconnect();
            }
        }

        $pdo->prepare("DELETE FROM pppoe_users WHERE username=?")->execute([$username]);
        $pdo->prepare("DELETE FROM customers WHERE username=?")->execute([$username]);

        $toast = ['type'=>'success','msg'=>"User deleted"];

    } catch (Exception $e) {
        $toast = ['type'=>'danger','msg'=>$e->getMessage()];
    }
}

/* =========================
   FETCH USERS
========================= */
$users = $pdo->query("SELECT * FROM pppoe_users ORDER BY created_at DESC")->fetchAll(PDO::FETCH_ASSOC);
?>

<!doctype html>
<html>
<head>
<title>PPPoE Manager</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>

<div class="container py-4">

<h4>PPPoE User Management</h4>

<div class="mb-3">
    <a href="?sync=1" class="btn btn-success">🔄 Sync MikroTik</a>
    <button onclick="location.reload()" class="btn btn-secondary">Refresh</button>
</div>

<?php if ($toast): ?>
<div class="alert alert-<?= $toast['type'] ?>">
    <?= $toast['msg'] ?>
</div>
<?php endif; ?>

<table class="table table-bordered">
<thead>
<tr>
<th>Username</th>
<th>Profile</th>
<th>Device</th>
<th>Created</th>
<th>Action</th>
</tr>
</thead>

<tbody>
<?php foreach ($users as $u): ?>
<tr>
<td><?= htmlspecialchars($u['username']) ?></td>
<td><?= htmlspecialchars($u['profile']) ?></td>
<td><?= htmlspecialchars($u['device_name']) ?></td>
<td><?= htmlspecialchars($u['created_at']) ?></td>
<td>
<a href="?delete=<?= urlencode($u['username']) ?>" 
   class="btn btn-danger btn-sm"
   onclick="return confirm('Delete user?')">
   Delete
</a>
</td>
</tr>
<?php endforeach; ?>
</tbody>
</table>

</div>
</body>
</html>
