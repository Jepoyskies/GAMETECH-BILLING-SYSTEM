<?php
include 'database.php'; // $pdo (PDO)
require_once 'MikrotikManager/MikrotikManager_pay_process_readjustments.php';
session_start();

// --- Validate input ---
if (
    empty($_POST['username']) ||
    empty($_POST['mikrotik_devices']) ||
    empty($_POST['rollback_to']) ||
    empty($_POST['note'])
) {
    echo "<p>Invalid request. Please fill in all required fields.</p>";
    include 'footer.php';
    exit;
}

$username         = trim($_POST['username']);
$mikrotik_devices = trim($_POST['mikrotik_devices']);
$rollback_to      = trim($_POST['rollback_to']); // expects 'Y-m-d\TH:i' from datetime-local
$note             = trim($_POST['note']);
$adjusted_by      = $_SESSION['username'] ?? 'system';

// --- Insert [ROLLBACK] prefix to note if not already present ---
if (stripos($note, '[ROLLBACK]') !== 0) {
    $note = '[ROLLBACK] ' . $note;
}

// --- Parse rollback_to as Manila time ---
$manilaTz = new DateTimeZone('Asia/Manila');
try {
    $new_expiry_dt = DateTime::createFromFormat('Y-m-d\TH:i', $rollback_to, $manilaTz);
    if (!$new_expiry_dt) {
        throw new Exception("Invalid rollback date/time format.");
    }
    $new_expiry = $new_expiry_dt->format('Y-m-d H:i:s');
} catch (Exception $e) {
    echo "<p>Invalid rollback date/time format.</p>";
    include 'footer.php';
    exit;
}

// --- Fetch customer info ---
$sql  = "SELECT expires_at, plan_name FROM customers WHERE username=? LIMIT 1";
$stmt = $pdo->prepare($sql);
$stmt->execute([$username]);
$user = $stmt->fetch(PDO::FETCH_ASSOC);
if (!$user) {
    echo "<p>User not found.</p>";
    include 'footer.php';
    exit;
}
$current_expiry = $user['expires_at'];
$plan_name      = $user['plan_name'];

// --- Prepare current_expiry (PH time) for rebates table ---
$current_expiry_ph = null;
if (!empty($current_expiry)) {
    // $current_expiry is assumed to be in UTC, so convert to Manila time
    $current_expiry_dt = new DateTime($current_expiry, new DateTimeZone('UTC'));
    $current_expiry_dt->setTimezone($manilaTz);
    $current_expiry_ph = $current_expiry_dt->format('Y-m-d H:i:s');
} else {
    $current_expiry_dt = null;
    $current_expiry_ph = null;
}

// --- Check rollback date is not after current expiry ---
if ($current_expiry_dt) {
    if ($new_expiry_dt > $current_expiry_dt) {
        echo "<p>Rollback date/time cannot be after the current expiry.</p>";
        include 'footer.php';
        exit;
    }
}

// --- Calculate days adjusted (DIFFERENCE) ---
$adjusted_days = null;
if ($current_expiry_dt && $new_expiry_dt) {
    $interval      = $current_expiry_dt->getTimestamp() - $new_expiry_dt->getTimestamp();
    $adjusted_days = $interval / 86400; // 86400 seconds per day
    $adjusted_days = round($adjusted_days, 2); // up to 2 decimal places
    if ($adjusted_days < 0) $adjusted_days = 0;
}

// --- Fetch MikroTik Device Credentials ---
$device_sql  = "SELECT * FROM mikrotik_devices WHERE device_name = ? LIMIT 1";
$device_stmt = $pdo->prepare($device_sql);
$device_stmt->execute([$mikrotik_devices]);
$device = $device_stmt->fetch(PDO::FETCH_ASSOC);
if (!$device) {
    echo "<p>MikroTik device not found.</p>";
    include 'footer.php';
    exit;
}

// --- Update the customers table (expires_at only) ---
$update_sql  = "UPDATE customers SET expires_at=? WHERE username=?";
$update_stmt = $pdo->prepare($update_sql);
$update_stmt->execute([$new_expiry, $username]);

// --- Insert adjustment record into rebates table (store days adjusted and current_expiry PH time) ---
$paid_at    = (new DateTime('now', $manilaTz))->format('Y-m-d H:i:s');
$insert_sql = "INSERT INTO rebates 
    (username, plan_name, mikrotik_devices, days, expires_at, current_expiry, paid_at, adjusted_by, note) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";
$insert_stmt = $pdo->prepare($insert_sql);
$insert_stmt->execute([
    $username,
    $plan_name,
    $mikrotik_devices,
    $adjusted_days,
    $new_expiry,
    $current_expiry_ph,
    $paid_at,
    $adjusted_by,
    $note
]);

// --- Clear sms_sent_at so next SMS can be triggered if needed ---
$clear_sms_sql  = "UPDATE customers SET sms_sent_at = NULL WHERE username = ?";
$clear_sms_stmt = $pdo->prepare($clear_sms_sql);
$clear_sms_stmt->execute([$username]);

// --- MikroTik Integration ---
try {
    $mt = new MikroTikManager(
        $device['ip_address'],
        $device['api_username'],
        $device['api_password'],
        (int)$device['api_port'],
        true,
        __DIR__ . '/mikrotik.log'
    );

    $mt->updatePppoeUser(
        $username,
        $username,
        null,
        $plan_name
    );

    // Update PPP secret comment
    $expiry_for_comment = $new_expiry_dt->format('Y-m-d H:i');
    $comment_text       = "EXP: $expiry_for_comment | Rolled back at $paid_at | Plan: $plan_name | Adjusted by: $adjusted_by";
    if ($note) $comment_text .= " | Note: $note";
    try {
        $mt->setPppSecretComment($username, $comment_text);
    } catch (Exception $e) {}

    // Disconnect if rollback date is already expired
    $now = new DateTime('now', $manilaTz);
    if ($new_expiry_dt < $now) {
        $msg = "User <strong>$username</strong>'s expiry rolled back successfully.<br>
                <strong>New expiry (PH time):</strong> <strong>$new_expiry</strong>.<br>
                MikroTik profile set to <strong>{$plan_name}</strong>.<br>
                <strong>Active session(s) disconnected.</strong><br>
                <small>Rolled back at: $paid_at (PH time) by $adjusted_by</small>";
    } else {
        $msg = "User <strong>$username</strong>'s expiry rolled back successfully.<br>
                <strong>New expiry (PH time):</strong> <strong>$new_expiry</strong>.<br>
                MikroTik profile set to <strong>{$plan_name}</strong>.<br>
                <strong>No disconnect needed.</strong><br>
                <small>Rolled back at: $paid_at (PH time) by $adjusted_by</small>";
    }
} catch (Exception $e) {
    $msg = "Rollback processed, but failed to update MikroTik profile: " . htmlspecialchars($e->getMessage());
}

// --------- Build PLAIN TEXT message for clients ----------
$lines_plain = [];

$lines_plain[] = "Hello " . $username . ",";
$lines_plain[] = "We have rolled back your internet subscription expiry.";
$lines_plain[] = "Plan: " . $plan_name;
$lines_plain[] = "Previous Expiry (PH time): " . ($current_expiry_ph ?: 'N/A');
$lines_plain[] = "New Expiry (PH time): " . $new_expiry;
$lines_plain[] = "Days adjusted: " . ($adjusted_days !== null ? $adjusted_days : 'N/A');
if ($note) {
    $lines_plain[] = "Note: " . $note;
}
$lines_plain[] = "";
$lines_plain[] = "Technical details:";
$lines_plain[] = "- MikroTik device: " . $mikrotik_devices;
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
    <title>Rollback Result</title>
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
