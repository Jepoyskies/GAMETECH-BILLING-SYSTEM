<?php
session_start();

/*
if (!isset($_SESSION['is_admin']) || !$_SESSION['is_admin']) {
    http_response_code(403);
    exit('Access denied');
}
*/

// --- CONFIG ---
$db_host = 'localhost';
$db_name = 'gametech';
$db_user = 'root';
$db_pass = '@Marille2012';

// --- BACKUP ---
if (isset($_GET['download'])) {

    set_time_limit(0);
    ini_set('memory_limit', '-1');

    $mysqli = new mysqli($db_host, $db_user, $db_pass, $db_name);
    if ($mysqli->connect_errno) {
        die('Connection failed: ' . $mysqli->connect_error);
    }

    $mysqli->set_charset('utf8mb4');

    header('Content-Type: application/sql');
    header('Content-Disposition: attachment; filename="backup-' . date('Y-m-d_H-i-s') . '.sql"');

    echo "-- Database Backup\n";
    echo "-- Generated: " . date('Y-m-d H:i:s') . "\n\n";
    echo "SET FOREIGN_KEY_CHECKS=0;\n\n";

    $tables = $mysqli->query("SHOW FULL TABLES WHERE Table_type IN ('BASE TABLE','VIEW')");

    while ($row = $tables->fetch_array()) {
        $table = $row[0];
        $type = $row[1];

        echo "\n-- Structure for $type `$table`\n";
        echo "DROP $type IF EXISTS `$table`;\n";

        if ($type == 'VIEW') {
            $create = $mysqli->query("SHOW CREATE VIEW `$table`")->fetch_assoc();
            echo $create['Create View'] . ";\n\n";
            continue;
        }

        $create = $mysqli->query("SHOW CREATE TABLE `$table`")->fetch_assoc();
        echo $create['Create Table'] . ";\n\n";

        $rows = $mysqli->query("SELECT * FROM `$table`", MYSQLI_USE_RESULT);

        $batch = [];
        $count = 0;

        while ($data = $rows->fetch_assoc()) {
            $vals = array_map(function ($v) use ($mysqli) {
                return isset($v) ? "'" . $mysqli->real_escape_string($v) . "'" : "NULL";
            }, $data);

            $batch[] = "(" . implode(",", $vals) . ")";
            $count++;

            if ($count % 500 == 0) {
                echo "INSERT INTO `$table` VALUES " . implode(",", $batch) . ";\n";
                $batch = [];
            }
        }

        if (!empty($batch)) {
            echo "INSERT INTO `$table` VALUES " . implode(",", $batch) . ";\n";
        }

        $rows->close();
    }

    // TRIGGERS
    $triggers = $mysqli->query("SHOW TRIGGERS");
    while ($tr = $triggers->fetch_assoc()) {
        $name = $tr['Trigger'];
        $create = $mysqli->query("SHOW CREATE TRIGGER `$name`")->fetch_assoc();

        echo "DROP TRIGGER IF EXISTS `$name`;\n";
        echo $create['SQL Original Statement'] . ";\n\n";
    }

    echo "SET FOREIGN_KEY_CHECKS=1;";
    $mysqli->close();
    exit;
}

// --- RESTORE ---
$message = '';

if (isset($_POST['restore']) && isset($_FILES['sqlfile'])) {

    set_time_limit(0);
    ini_set('memory_limit', '-1');

    if ($_FILES['sqlfile']['error'] !== 0) {
        $message = '<div class="alert alert-danger">File upload error.</div>';
    } else {

        $file = $_FILES['sqlfile']['tmp_name'];
        $sql = file_get_contents($file);

        $mysqli = new mysqli($db_host, $db_user, $db_pass, $db_name);

        if ($mysqli->connect_errno) {
            $message = '<div class="alert alert-danger">DB connection failed.</div>';
        } else {

            $mysqli->set_charset('utf8mb4');

            if ($mysqli->multi_query($sql)) {
                do {
                    if ($result = $mysqli->store_result()) {
                        $result->free();
                    }
                } while ($mysqli->more_results() && $mysqli->next_result());

                $message = '<div class="alert alert-success">✅ Database restored successfully.</div>';
            } else {
                $message = '<div class="alert alert-danger">❌ Restore failed: ' . $mysqli->error . '</div>';
            }

            $mysqli->close();
        }
    }
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Database Manager</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <style>
        body {
            background: linear-gradient(135deg, #1d2671, #c33764);
            color: #fff;
        }
        .card {
            border-radius: 15px;
        }
        .btn-lg {
            padding: 12px;
            font-size: 18px;
        }
        .title {
            font-weight: bold;
            letter-spacing: 1px;
        }
    </style>
</head>
<body>

<div class="container py-5">

    <div class="text-center mb-5">
        <h1 class="title">Database Backup & Restore</h1>
        <p class="text-light">Securely manage your database</p>
    </div>

    <div class="row g-4">

        <!-- BACKUP -->
        <div class="col-md-6">
            <div class="card shadow p-4 text-center">
                <h4>📥 Backup Database</h4>
                <p class="text-muted">Download full database backup</p>
                <a href="?download=1" class="btn btn-primary btn-lg w-100">
                    Download Backup
                </a>
            </div>
        </div>

        <!-- RESTORE -->
        <div class="col-md-6">
            <div class="card shadow p-4 text-center">
                <h4>📤 Restore Database</h4>
                <p class="text-muted">Upload .sql file to restore</p>

                <?= $message ?>

                <form method="post" enctype="multipart/form-data">
                    <input type="file" name="sqlfile" class="form-control mb-3" accept=".sql" required>
                    <button name="restore" class="btn btn-danger btn-lg w-100">
                        Restore Database
                    </button>
                </form>
            </div>
        </div>

    </div>

</div>

</body>
</html>
