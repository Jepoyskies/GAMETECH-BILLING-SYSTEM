<?php
// backup-restore-database.php

// --- SECURITY: Simple session check (replace with your login system!) ---
session_start();
/*
if (!isset($_SESSION['is_admin']) || !$_SESSION['is_admin']) {
    http_response_code(403);
    exit('Access denied');
}
*/

// --- CONFIGURE YOUR DB ---
$db_host = 'localhost';
$db_name = 'gametech';
$db_user = 'root';
$db_pass = '@Marille2012';

// --- BACKUP HANDLER ---
if (isset($_GET['download'])) {
    header('Content-Type: application/sql');
    header('Content-Disposition: attachment; filename="db-backup-' . date('Y-m-d_H-i-s') . '.sql"');
    header('Pragma: no-cache');
    header('Expires: 0');

    $mysqli = new mysqli($db_host, $db_user, $db_pass, $db_name);
    if ($mysqli->connect_errno) {
        die('Connection failed: ' . $mysqli->connect_error);
    }
    $mysqli->set_charset('utf8');

    // Get all tables
    $tables = [];
    $result = $mysqli->query("SHOW TABLES");
    while ($row = $result->fetch_array()) {
        $tables[] = $row[0];
    }

    foreach ($tables as $table) {
        // Drop statement
        echo "DROP TABLE IF EXISTS `$table`;\n";
        // Create table statement
        $create = $mysqli->query("SHOW CREATE TABLE `$table`")->fetch_row();
        echo $create[1] . ";\n\n";

        // Dump data
        $rows = $mysqli->query("SELECT * FROM `$table`");
        if ($rows->num_rows) {
            while ($row = $rows->fetch_assoc()) {
                $vals = array_map(function($v) use ($mysqli) {
                    return isset($v) ? "'" . $mysqli->real_escape_string($v) . "'" : "NULL";
                }, $row);
                echo "INSERT INTO `$table` (`" . implode('`,`', array_keys($row)) . "`) VALUES (".implode(',', $vals).");\n";
            }
        }
        echo "\n";
    }
    $mysqli->close();
    exit;
}

// --- RESTORE HANDLER ---
$restore_message = '';
if (isset($_POST['restore']) && isset($_FILES['sqlfile']) && $_FILES['sqlfile']['error'] === UPLOAD_ERR_OK) {
    $tmp_name = $_FILES['sqlfile']['tmp_name'];
    $sql = file_get_contents($tmp_name);

    // Split queries (simple split, works for most exports)
    $queries = array_filter(array_map('trim', explode(";\n", $sql)));

    $mysqli = new mysqli($db_host, $db_user, $db_pass, $db_name);
    if ($mysqli->connect_errno) {
        $restore_message = '<div class="alert alert-danger">Connection failed: '.$mysqli->connect_error.'</div>';
    } else {
        $success = true;
        $mysqli->set_charset('utf8');
        foreach ($queries as $query) {
            if (trim($query)) {
                if (!$mysqli->query($query)) {
                    $success = false;
                    $restore_message .= '<div class="alert alert-warning">Error on: <code>'.htmlspecialchars($query).'</code><br>'.$mysqli->error.'</div>';
                }
            }
        }
        $mysqli->close();
        if ($success) {
            $restore_message = '<div class="alert alert-success">Database restored successfully.</div>';
        } else {
            $restore_message .= '<div class="alert alert-danger">Restore completed with some errors.</div>';
        }
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Database Backup & Restore</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body class="bg-light">
<div class="container py-5">
    <div class="row">
        <div class="col-lg-6 mx-auto">
            <div class="card shadow-sm mb-4">
                <div class="card-body text-center">
                    <h3 class="mb-3">Database Backup</h3>
                    <p class="mb-4 text-muted">Click to download a full MySQL backup of your database.</p>
                    <a href="?download=1" class="btn btn-primary btn-lg">
                        <i class="bi bi-download"></i> Download Backup
                    </a>
                </div>
            </div>
            <div class="card shadow-sm">
                <div class="card-body text-center">
                    <h3 class="mb-3">Restore Database</h3>
                    <?php if ($restore_message) echo $restore_message; ?>
                    <form method="post" enctype="multipart/form-data" onsubmit="return confirm('Are you sure? This will overwrite your database!');">
                        <input type="file" name="sqlfile" accept=".sql" class="form-control mb-3" required>
                        <button type="submit" name="restore" class="btn btn-danger btn-lg">
                            <i class="bi bi-upload"></i> Restore from SQL File
                        </button>
                        <p class="mt-3 text-warning small">
                            <b>Warning:</b> Restoring will OVERWRITE all data. Backup first.
                        </p>
                    </form>
                </div>
            </div>
            <div class="text-center mt-4">
                <p class="small text-muted">
                    <b>Tip:</b> Always download and keep backups <b>off the server</b> (e.g. Google Drive, Dropbox, USB).<br>
                    For maximum safety, restrict this page to admins only.
                </p>
            </div>
        </div>
    </div>
</div>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
</body>
</html>
