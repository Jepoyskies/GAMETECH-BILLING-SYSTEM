<?php
require 'database.php';
require 'semaphore.php';

$semaphore_apikey = "a1be64e85146a946d40aeb1677d37a48";
$auto_sms_count = 0;

define('LOCK_FILE', __DIR__ . '/auto_sms.lock');
define('LOCK_TIMEOUT', 1800); // 30 min

function log_event($msg) {
    $logfile = __DIR__ . '/auto_sms.log';
    $date = date('Y-m-d H:i:s');
    error_log("[$date] $msg\n", 3, $logfile);
}

// --- Obtain file lock to avoid parallel runs ---
$lock_fp = fopen(LOCK_FILE, 'c+');
if (!$lock_fp) {
    log_event("Unable to open lock file.");
    exit(1);
}
if (!flock($lock_fp, LOCK_EX | LOCK_NB)) {
    // If lock is old, remove it
    $stat = fstat($lock_fp);
    if (time() - $stat['mtime'] > LOCK_TIMEOUT) {
        unlink(LOCK_FILE);
        fclose($lock_fp);
        $lock_fp = fopen(LOCK_FILE, 'c+');
        if (!$lock_fp || !flock($lock_fp, LOCK_EX | LOCK_NB)) {
            log_event("Unable to acquire stale lock.");
            exit(2);
        }
    } else {
        log_event("Another instance is running. Exiting.");
        exit(0);
    }
}

try {
    $conn->beginTransaction();

    // Lock rows to avoid double-send (FOR UPDATE)
    $sql = "SELECT username, expires_at, full_name, phone 
            FROM customers 
            WHERE username IS NOT NULL 
              AND username != '' 
              AND expires_at BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 3 DAY)
              AND sms_sent_at IS NULL
            ORDER BY expires_at ASC
            FOR UPDATE";
    $stmt = $conn->query($sql);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    foreach ($rows as $row) {
        $message = "Hello {$row['full_name']}! Your subscription will expire on {$row['expires_at']}. Kindly renew soon. Thank you!";
        $response = sendSemaphoreSMS($semaphore_apikey, $row['phone'], $message);

        // Mark as sent only if SMS API returns success
        if (/* check if $response is success, e.g. $response['status']=='success' */ true) {
            $update_sql = "UPDATE customers SET sms_sent_at = NOW() WHERE username = :username";
            $update_stmt = $conn->prepare($update_sql);
            $update_stmt->bindValue(':username', $row['username']);
            $update_stmt->execute();
            $auto_sms_count++;
            log_event("SMS sent to {$row['username']} ({$row['phone']})");
        } else {
            log_event("SMS failed for {$row['username']} ({$row['phone']}): " . json_encode($response));
        }
    }
    $conn->commit();
    echo "Auto SMS sent to {$auto_sms_count} customer(s) expiring within 3 days.\n";
    log_event("Auto SMS sent to {$auto_sms_count} customer(s) expiring within 3 days.");
} catch (PDOException $e) {
    $conn->rollBack();
    log_event("Database error: " . $e->getMessage());
    echo "Database error: " . $e->getMessage() . "\n";
} catch (Exception $e) {
    $conn->rollBack();
    log_event("General error: " . $e->getMessage());
    echo "General error: " . $e->getMessage() . "\n";
} finally {
    flock($lock_fp, LOCK_UN);
    fclose($lock_fp);
}

?>
