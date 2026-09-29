<?php
// save_marker_positions.php
require 'database.php';
header('Content-Type: application/json');

// TEMP: show PHP errors while debugging
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Do NOT use mysqli_report strict here, we want to catch errors manually
// mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

try {
    $raw = file_get_contents('php://input');

    // Debug: log raw input
    file_put_contents(__DIR__ . '/save_marker_debug.log', date('c') . " RAW: " . $raw . PHP_EOL, FILE_APPEND);

    $data = json_decode($raw, true);

    if (!is_array($data)) {
        echo json_encode(['success' => false, 'message' => 'Invalid JSON input']);
        exit;
    }

    $conn = new mysqli($host, $user, $pass, $db);
    if ($conn->connect_errno) {
        echo json_encode(['success' => false, 'message' => 'DB connect error: ' . $conn->connect_error]);
        exit;
    }
    $conn->set_charset('utf8mb4');

    // Prepare statements and check for errors
    $stmtNap = $conn->prepare(
        "UPDATE napbox_mapping
         SET nap_latitude = ?, nap_longitude = ?
         WHERE id = ?"
    );
    if (!$stmtNap) {
        echo json_encode(['success' => false, 'message' => 'Prepare NAP failed: ' . $conn->error]);
        exit;
    }

    $stmtCust = $conn->prepare(
        "UPDATE customers
         SET latitude = ?, longitude = ?
         WHERE id = ?"
    );
    if (!$stmtCust) {
        echo json_encode(['success' => false, 'message' => 'Prepare Customer failed: ' . $conn->error]);
        exit;
    }

    foreach ($data as $row) {
        if (!isset($row['type'], $row['id'], $row['lat'], $row['lng'])) {
            continue;
        }

        $id  = (int)$row['id'];
        $lat = (string)$row['lat'];
        $lng = (string)$row['lng'];

        if ($row['type'] === 'nap') {
            if (!$stmtNap->bind_param('ssi', $lat, $lng, $id)) {
                echo json_encode(['success' => false, 'message' => 'bind NAP failed: ' . $stmtNap->error]);
                exit;
            }
            if (!$stmtNap->execute()) {
                echo json_encode(['success' => false, 'message' => 'exec NAP failed: ' . $stmtNap->error]);
                exit;
            }
        } elseif ($row['type'] === 'customer') {
            if (!$stmtCust->bind_param('ssi', $lat, $lng, $id)) {
                echo json_encode(['success' => false, 'message' => 'bind Cust failed: ' . $stmtCust->error]);
                exit;
            }
            if (!$stmtCust->execute()) {
                echo json_encode(['success' => false, 'message' => 'exec Cust failed: ' . $stmtCust->error]);
                exit;
            }
        }
    }

    $stmtNap->close();
    $stmtCust->close();
    $conn->close();

    echo json_encode(['success' => true]);
} catch (Throwable $e) {
    error_log("save_marker_positions.php error: " . $e->getMessage());
    echo json_encode(['success' => false, 'message' => 'Server exception: ' . $e->getMessage()]);
}
