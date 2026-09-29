<?php
require_once 'database.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id           = isset($_POST['id'])           ? intval($_POST['id'])        : 0;
    $device_name  = isset($_POST['device_name'])  ? trim($_POST['device_name']) : '';
    $ip_address   = isset($_POST['ip_address'])   ? trim($_POST['ip_address'])  : '';
    $api_username = isset($_POST['api_username']) ? trim($_POST['api_username']): '';
    $api_port     = isset($_POST['api_port'])     ? trim($_POST['api_port'])    : '';
    $api_password = isset($_POST['api_password']) ? trim($_POST['api_password']): '';

    // Validate required fields
    if (
        $id > 0 &&
        $device_name &&
        $ip_address &&
        $api_username &&
        is_numeric($api_port)
    ) {
        try {
            // Fetch old device name
            $stmt = $pdo->prepare("SELECT device_name FROM mikrotik_devices WHERE id = ?");
            $stmt->execute([$id]);
            $row = $stmt->fetch(PDO::FETCH_ASSOC);

            if (!$row) {
                header("Location: mikrotik_devices.php?toast_type=danger&toast_msg=" . urlencode("Device not found."));
                exit;
            }

            $old_device_name = $row['device_name'];

            $pdo->beginTransaction();

            // Update mikrotik_devices table
            if ($api_password !== '') {
               $api_port_8700 = $_POST['api_port_8700'] ?? 8700;

$stmt = $pdo->prepare("
    UPDATE mikrotik_devices 
    SET device_name=?, ip_address=?, api_username=?, api_port=?, api_port_8700=?
    WHERE id=?
");

$stmt->execute([
    $device_name,
    $ip_address,
    $api_username,
    $api_port,
    $api_port_8700,
    $id
]);

            } else {
                $stmt = $pdo->prepare(
                    "UPDATE mikrotik_devices 
                    SET device_name = ?, ip_address = ?, api_username = ?, api_port = ?
                    WHERE id = ?"
                );
                $stmt->execute([$device_name, $ip_address, $api_username, $api_port, $id]);
            }

            // If device_name changed, update BOTH customers and pppoe_users
            if ($device_name !== $old_device_name) {
                // Update customers table
                $stmt = $pdo->prepare("UPDATE customers SET device_name = ? WHERE device_name = ?");
                $stmt->execute([$device_name, $old_device_name]);

                // Update pppoe_users table
                $stmt = $pdo->prepare("UPDATE pppoe_users SET device_name = ? WHERE device_name = ?");
                $stmt->execute([$device_name, $old_device_name]);
            }

            $pdo->commit();
            header("Location: mikrotik_devices.php?toast_type=success&toast_msg=" . urlencode("Device updated successfully."));
            exit;
        } catch (Throwable $e) {
            if ($pdo->inTransaction()) $pdo->rollBack();
            header("Location: mikrotik_devices.php?toast_type=danger&toast_msg=" . urlencode("Error updating device: " . $e->getMessage()));
            exit;
        }
    } else {
        header("Location: mikrotik_devices.php?toast_type=danger&toast_msg=" . urlencode("Missing or invalid fields."));
        exit;
    }
} else {
    header("Location: mikrotik_devices.php");
    exit;
}
?>
