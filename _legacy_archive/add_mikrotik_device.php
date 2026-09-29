<?php
require_once 'database.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Collect and sanitize input
    $device_name  = trim($_POST['device_name']  ?? '');
    $ip_address   = trim($_POST['ip_address']   ?? '');
    $api_username = trim($_POST['api_username'] ?? '');
    $api_password = trim($_POST['api_password'] ?? '');
    $api_port     = trim($_POST['api_port']     ?? '');

    // Basic validation
    $errors = [];

    if ($device_name === '') {
        $errors[] = 'Device name is required.';
    }

    if ($ip_address === '' || !filter_var($ip_address, FILTER_VALIDATE_IP)) {
        $errors[] = 'A valid IP address is required.';
    }

    if ($api_username === '') {
        $errors[] = 'API username is required.';
    }

    if ($api_password === '') {
        $errors[] = 'API password is required.';
    }

    if ($api_port === '' || !ctype_digit($api_port)) {
        $errors[] = 'API port must be a number.';
    }

    if (empty($errors)) {
        try {
            // Check if device name already exists (optional but recommended)
            $check = $pdo->prepare("SELECT COUNT(*) FROM mikrotik_devices WHERE device_name = ?");
            $check->execute([$device_name]);
            if ($check->fetchColumn() > 0) {
                $errors[] = 'A device with this name already exists.';
            } else {
                $api_port_8700 = $_POST['api_port_8700'] ?? 8700;

$stmt = $pdo->prepare("
    INSERT INTO mikrotik_devices 
    (device_name, ip_address, api_username, api_password, api_port, api_port_8700)
    VALUES (?, ?, ?, ?, ?, ?)
");

$stmt->execute([
    $device_name,
    $ip_address,
    $api_username,
    $api_password,
    $api_port,
    $api_port_8700
]);


                // On success, go back to listing
                header('Location: mikrotik_devices.php?added=1');
                exit;
            }
        } catch (Throwable $e) {
            $errors[] = 'Database error: ' . $e->getMessage();
        }
    }

    // If there are errors, you can either:
    // 1) store them in session and redirect, or
    // 2) show them directly (simple approach below: redirect with error query)

    if (!empty($errors)) {
        // You can improve this using sessions/flash messages.
        $query = http_build_query([
            'error'        => implode(' ', $errors),
            'device_name'  => $device_name,
            'ip_address'   => $ip_address,
            'api_username' => $api_username,
            'api_port'     => $api_port,
        ]);
        header('Location: mikrotik_devices.php?' . $query);
        exit;
    }

} 

// Fallback: invalid request method, just redirect
header('Location: mikrotik_devices.php');
exit;
