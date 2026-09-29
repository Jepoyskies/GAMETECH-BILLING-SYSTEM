<?php
require 'database.php';

header('Content-Type: application/json');

if (!isset($_GET['id']) || !is_numeric($_GET['id'])) {
    echo json_encode(['success' => false, 'message' => 'Invalid ID.']);
    exit;
}

$id = (int)$_GET['id'];

$stmt = $pdo->prepare("DELETE FROM service_plans WHERE id = ?");
if ($stmt->execute([$id])) {
    echo json_encode(['success' => true, 'message' => 'Plan deleted successfully!']);
} else {
    echo json_encode(['success' => false, 'message' => 'Failed to delete plan.']);
}
