<?php
session_start();
require_once('database.php');

if (isset($_SESSION['admin_logged_in']) && isset($_SESSION['username']) && isset($_SESSION['admin_id'])) {
    $username = $_SESSION['username'];
    $admin_id = $_SESSION['admin_id'];

    $ip = $_SERVER['REMOTE_ADDR'];
    $agent = $_SERVER['HTTP_USER_AGENT'] ?? '';

    // Log the logout event (PDO version)
    $log_stmt = $conn->prepare(
        "INSERT INTO admin_logins (admin_id, username, event_type, ip_address, user_agent) VALUES (?, ?, 'logout', ?, ?)"
    );
    $log_stmt->execute([$admin_id, $username, $ip, $agent]);
}

// Destroy the session and redirect
session_unset();
session_destroy();
header('Location: login.php');
exit;
?>
