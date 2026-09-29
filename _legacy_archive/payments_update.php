<?php
// payments_update.php

include 'database.php'; // provides $pdo

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = $_POST['id'] ?? '';
    $method = trim($_POST['method'] ?? '');
    $reference = trim($_POST['reference'] ?? '');

    if (!$id) {
        echo json_encode(['success' => false, 'error' => 'Missing payment ID.']);
        exit;
    }

    $sql = "UPDATE payments SET payment_method = ?, reference_no = ? WHERE id = ?";
    $stmt = $pdo->prepare($sql);
    $ok = $stmt->execute([$method, $reference, $id]);
    if ($ok) {
        echo json_encode(['success' => true]);
    } else {
        echo json_encode(['success' => false, 'error' => 'Update failed.']);
    }
    exit;
}

header('HTTP/1.1 405 Method Not Allowed');
