<?php

include 'database.php'; // $pdo (PDO)
require_once 'MikrotikManager/MikrotikManager_pay_process_rebates.php'; // MikroTik API class
session_start();

// --- Validate input ---
if (
    empty($_POST['username']) ||
    empty($_POST['new_due_date_time']) ||
    empty($_POST['mikrotik_devices'])
) {
    echo "<p>Invalid request. Please fill in all required fields.</p>";
    include 'footer.php';
    exit;
}

$username          = trim($_POST['username']);
$new_due_date_time = trim($_POST['new_due_date_time']); // e.g. '2025-10-22T15:45:10'
$mikrotik_devices  = trim($_POST['mikrotik_devices']);
$plan_name         = isset($_POST['plan_name']) ? trim($_POST['plan_name']) : null;
$adjusted_by       = $_SESSION['username'] ?? 'system';
$note              = isset($_POST['note']) ? trim($_POST['note']) : '';

// --- Insert [REBATES] prefix to note if not already present ---
if (stripos($note, '[REBATES]') !== 0) {
    $note = '[REBATES] ' . $note;
}

// --- Fetch customer info ---
$sql  = "SELECT expires_at, plan_name FROM customers WHERE username=? LIMIT 1";
$stmt = $pdo->prepare($sql);
$stmt->execute([$username]);
$row = $stmt->fetch(PDO::FETCH_ASSOC);
if (!$row) {
    echo "<p>User not found.</p>";
    include 'footer.php';
    exit;
}
$current_expiry = $row['expires_at']; // expiry before adjustment
$db_plan_name   = $row['plan_name'];
if (!$plan_name) $plan_name = $db_plan_name;

// --- Fetch MikroTik Device Credentials using user-supplied device ---
$device_sql  = "SELECT * FROM mikrotik_devices WHERE device_name = ? LIMIT 1";
$device_stmt = $pdo->prepare($device_sql);
$device_stmt->execute([$mikrotik_devices]);
$device = $device_stmt->fetch(PDO::FETCH_ASSOC);

if (!$device) {
    echo "<p>MikroTik device not found.</p>";
    include 'footer.php';
    exit;
}

// --- Initialize MikroTik connection using the device info ---
$mt = new MikroTikManager(
    $device['ip_address'],
    $device['api_username'],
    $device['api_password'],
    (int)$device['api_port'],
    true,
    __DIR__ . '/mikrotik.log'
);

// --- Use exact expiry from user selection (with seconds) ---
$manilaTz = new DateTimeZone('Asia/Manila');
$now      = new DateTime('now', $manilaTz);

// Convert 'YYYY-MM-DDTHH:MM:SS' to 'YYYY-MM-DD HH:MM:SS'
$new_expiry = str_replace('T', ' ', $new_due_date_time);

// For logic: check if user was expired before this action
$user_expired = true;
if (!empty($current_expiry)) {
    try {
        $expiryDate   = new DateTime($current_expiry, $manilaTz);
        $user_expired = ($expiryDate < $now);
    } catch (Exception $e) {
        $user_expired = true;
    }
}

// --- Calculate days between old and new expiry ---
$days = 0;
try {
    if (!empty($current_expiry) && !empty($new_expiry)) {
        $prev     = new DateTime($current_expiry, $manilaTz);
        $next     = new DateTime($new_expiry, $manilaTz);
        $interval = $prev->diff($next);
        $days     = (int)$interval->format('%r%a'); // signed days
    }
} catch (Exception $e) {
    $days = 0;
}

// --- Update the customers table (expires_at only) ---
$update_sql  = "UPDATE customers SET expires_at=? WHERE username=?";
$update_stmt = $pdo->prepare($update_sql);
$update_stmt->execute([$new_expiry, $username]);

// --- Insert rebate record into rebates table ---
$paid_at    = $now->format('Y-m-d H:i:s');
$insert_sql = "INSERT INTO rebates 
    (username, plan_name, mikrotik_devices, current_expiry, days, expires_at, paid_at, adjusted_by, note) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";
$insert_stmt = $pdo->prepare($insert_sql);
$insert_stmt->execute([
    $username,
    $plan_name,
    $mikrotik_devices,
    $current_expiry,
    $days,
    $new_expiry,
    $paid_at,
    $adjusted_by,
    $note
]);

// --- CLEAR sms_sent_at FIELD IF USER PAID ---
$clear_sms_sql  = "UPDATE customers SET sms_sent_at = NULL WHERE username = ?";
$clear_sms_stmt = $pdo->prepare($clear_sms_sql);
$clear_sms_stmt->execute([$username]);

// --- MikroTik Integration ---
try {
    $mt->updatePppoeUser(
        $username,   // original username
        $username,   // new username (same)
        null,        // password (leave as is)
        $plan_name   // profile
    );

    // --- Update /ppp secret comment ---
    $expiry_for_comment = (new DateTime($new_expiry, $manilaTz))->format('Y-m-d H:i:s');
    $comment_text       = "EXP: $expiry_for_comment | Adjusted at $paid_at | Plan: $plan_name | Adjusted by: $adjusted_by";
    if ($note) $comment_text .= " | Note: $note";
    try {
        $mt->setPppSecretComment($username, $comment_text);
    } catch (Exception $e) {
        // Optionally log error, but do not interrupt main flow
    }

    if ($user_expired) {
        $msg = "User <strong>$username</strong> rebate applied successfully.<br>
                <strong>New expiry (PH time):</strong> <strong>$new_expiry</strong>.<br>
                MikroTik profile set to <strong>{$plan_name}</strong>.<br>
                <strong>Active session(s) disconnected</strong>. Please reconnect to apply changes.<br>
                <small>Adjusted at: $paid_at (PH time) by $adjusted_by</small>";
    } else {
        $msg = "User <strong>$username</strong> rebate applied successfully.<br>
                <strong>New expiry (PH time):</strong> <strong>$new_expiry</strong>.<br>
                MikroTik profile set to <strong>{$plan_name}</strong>.<br>
                <strong>No disconnect needed</strong> as user was not expired.<br>
                <small>Adjusted at: $paid_at (PH time) by $adjusted_by</small>";
    }
} catch (Exception $e) {
    $msg = "Rebate processed, but failed to update MikroTik profile: " . htmlspecialchars($e->getMessage());
}

// --------- Build PLAIN TEXT message for clients ----------
$lines_plain = [];

$lines_plain[] = "Hello " . $username . ",";
$lines_plain[] = "We have adjusted your internet subscription (rebate applied).";
$lines_plain[] = "Plan: " . $plan_name;
$lines_plain[] = "Previous Expiry (PH time): " . ($current_expiry ?: 'N/A');
$lines_plain[] = "New Expiry (PH time): " . $new_expiry;
$lines_plain[] = "Days difference: " . $days;
if ($note) {
    $lines_plain[] = "Note: " . $note;
}
$lines_plain[] = "";
$lines_plain[] = "Technical details:";
$lines_plain[] = "- Account was " . ($user_expired ? "EXPIRED" : "ACTIVE") . " before this rebate.";
$lines_plain[] = "- MikroTik profile: " . $plan_name;
$lines_plain[] = "- Device: " . $mikrotik_devices;
$lines_plain[] = "";
$lines_plain[] = "Processed at: " . $paid_at . " (PH time)";
$lines_plain[] = "Processed by: " . $adjusted_by;

$msg_plain    = implode("\n", $lines_plain);
$msg_plain_js = htmlspecialchars($msg_plain, ENT_QUOTES, 'UTF-8');
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Rebate Result</title>
    <style>
        body {
            min-height: 100vh;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f8f9fa;
        }
        .success-message {
            border: 1px solid #d4edda;
            background: #d4edda;
            color: #155724;
            border-radius: 8px;
            max-width: 600px;
            width: 90%;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            position: relative;
        }
        .btn-primary {
            display: inline-block;
            margin-top: 1rem;
            padding: 8px 20px;
            background: #007bff;
            color: #fff;
            text-decoration: none;
            border-radius: 4px;
        }
        .btn-primary:hover { background: #0056b3; }
        .btn-secondary {
            display: inline-block;
            margin-top: 1rem;
            padding: 8px 20px;
            background: #6c757d;
            color: #fff;
            text-decoration: none;
            border-radius: 4px;
            margin-left: 0.5rem;
        }
        .btn-secondary:hover { background: #5a6268; }
        .copy-status {
            margin-top: 0.5rem;
            font-size: 0.9rem;
            color: #155724;
        }
        textarea#copyTextArea {
            position: absolute;
            left: -9999px;
            top: -9999px;
            opacity: 0;
        }
    </style>
</head>
<body>
    <div class="success-message">
        <?php echo $msg; ?>
        <br><br>
        <button
            type="button"
            class="btn-secondary"
            id="copyPlainBtn"
            data-msg="<?php echo $msg_plain_js; ?>"
        >
            Copy Message (Text)
        </button>
        <button
            type="button"
            class="btn-secondary"
            id="copyHtmlBtn"
        >
            Copy Message (HTML)
        </button>
        <a href="subscription_plans.php" class="btn-primary">Back to Home</a>
        <div class="copy-status" id="copyStatus"></div>
        <textarea id="copyTextArea"></textarea>
    </div>

    <script>
        (function () {
            const copyPlainBtn = document.getElementById('copyPlainBtn');
            const copyHtmlBtn  = document.getElementById('copyHtmlBtn');
            const copyStatus   = document.getElementById('copyStatus');
            const hiddenTa     = document.getElementById('copyTextArea');

            function showStatus(text) {
                copyStatus.textContent = text;
                if (!text) return;
                setTimeout(() => { copyStatus.textContent = ''; }, 3000);
            }

            async function copyText(text) {
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(text);
                    } else {
                        hiddenTa.value = text;
                        hiddenTa.select();
                        document.execCommand('copy');
                    }
                    showStatus('Message copied to clipboard.');
                } catch (e) {
                    console.error(e);
                    showStatus('Failed to copy. Please select and copy manually.');
                }
            }

            copyPlainBtn.addEventListener('click', function () {
                const msg = this.getAttribute('data-msg') || '';
                copyText(msg);
            });

            copyHtmlBtn.addEventListener('click', function () {
                const container = document.querySelector('.success-message');
                if (!container) return;
                const clone = container.cloneNode(true);
                clone.querySelectorAll('.btn-primary, .btn-secondary, .copy-status, #copyTextArea').forEach(el => el.remove());
                const html = clone.innerHTML.trim();
                copyText(html);
            });
        })();
    </script>
</body>
</html>

<?php include 'footer.php'; ?>
