<?php
declare(strict_types=1);
session_start();
include 'database.php'; // Your PDO connection file

if (empty($_SESSION['admin_logged_in']) || empty($_SESSION['admin_id'])) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $current_password = $_POST['current_password'] ?? '';
    $new_password = $_POST['new_password'] ?? '';
    $confirm_new_password = $_POST['confirm_new_password'] ?? '';
    $admin_id = $_SESSION['admin_id'];

    try {
        $stmt = $pdo->prepare("SELECT password FROM admins WHERE id = ?");
        $stmt->execute([$admin_id]);
        $admin = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$admin) {
            throw new Exception("User not found.");
        }

        if (!password_verify($current_password, $admin['password'])) {
            throw new Exception("Current password is incorrect.");
        }

        if (strlen($new_password) < 6) {
            throw new Exception("New password must be at least 6 characters.");
        }

        if ($new_password !== $confirm_new_password) {
            throw new Exception("New passwords do not match.");
        }

        $hashed = password_hash($new_password, PASSWORD_DEFAULT);
        $stmt = $pdo->prepare("UPDATE admins SET password = ? WHERE id = ?");
        $stmt->execute([$hashed, $admin_id]);

        $_SESSION['flash_msg'] = 'Password changed successfully!';
        $_SESSION['flash_type'] = 'success';

    } catch (Exception $e) {
        $_SESSION['flash_msg'] = $e->getMessage();
        $_SESSION['flash_type'] = 'error';
    }
} else {
    $_SESSION['flash_msg'] = 'Invalid request.';
    $_SESSION['flash_type'] = 'error';
}

header('Location: edit_password.php');
exit;
