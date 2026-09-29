<?php
require 'database.php';
require 'log_system_action.php';

if (session_status() === PHP_SESSION_NONE) session_start();
header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['id'], $_POST['csrf_token'])) {
    // CSRF check
    if (!hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {
        echo json_encode(['success' => false, 'message' => 'Invalid CSRF token.']);
        exit;
    }

    $customer_id = intval($_POST['id']);

    // Fetch old data for logging
    $stmt = $conn->prepare("SELECT * FROM customers WHERE id = ?");
    $stmt->execute([$customer_id]);
    $old_data = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$old_data) {
        echo json_encode(['success' => false, 'message' => 'Customer not found.']);
        exit;
    }

    // Delete the record
    $stmt = $conn->prepare("DELETE FROM customers WHERE id = ?");
    $success = $stmt->execute([$customer_id]);

    $changed_by = $_SESSION['username'] ?? 'system';
    log_system_action($conn, 'customers', $customer_id, 'delete', $changed_by, $old_data, null);

    echo json_encode(['success' => $success]);
    exit;
}

echo json_encode(['success' => false, 'message' => 'Invalid request.']);
exit;
?>
