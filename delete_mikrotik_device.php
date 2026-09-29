<?php
// delete_device.php
require_once 'database.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['id'])) {
    $id = (int)$_POST['id'];
    $type = 'error';
    $msg  = 'Invalid device ID.';

    if ($id > 0) {
        try {
            // Optional: get name for nicer message
            $nameStmt = $pdo->prepare("SELECT device_name FROM mikrotik_devices WHERE id = ?");
            $nameStmt->execute([$id]);
            $device = $nameStmt->fetch(PDO::FETCH_ASSOC);

            $stmt = $pdo->prepare("DELETE FROM mikrotik_devices WHERE id = ?");
            $stmt->execute([$id]);

            if ($stmt->rowCount()) {
                $type = 'success';
                $msg  = 'Device "' . ($device['device_name'] ?? 'ID ' . $id) . '" deleted successfully.';
            } else {
                $type = 'warning';
                $msg  = 'Device not found or already deleted.';
            }
        } catch (Throwable $e) {
            $type = 'error';
            $msg  = 'Database error: ' . $e->getMessage();
        }
    }

    header('Location: mikrotik_devices.php?toast_type=' . urlencode($type) . '&toast_msg=' . urlencode($msg));
    exit;
}

// Invalid request
header('Location: mikrotik_devices.php');
exit;
