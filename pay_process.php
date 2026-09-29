<?php
include 'database.php'; // $pdo (PDO object)
require_once 'MikrotikManager/MikrotikManager_pay_process.php';

session_start();

function parseDatetimeLocal($str, $timezone) {
    $dt = DateTime::createFromFormat('Y-m-d\TH:i:s', $str, $timezone);
    if ($dt === false) {
        $dt = DateTime::createFromFormat('Y-m-d\TH:i', $str, $timezone);
    }
    return $dt;
}

// --- Input Validation ---
$required_fields = ['username', 'end_date', 'amount', 'payment_method', 'mikrotik_devices', 'plan_name', 'start_date'];
foreach ($required_fields as $field) {
    if (!isset($_POST[$field]) || $_POST[$field] === '') {
        echo "<p>Invalid request. Please fill in all fields.</p>";
        include 'footer.php';
        exit;
    }
}

// --- Sanitize and assign inputs ---
$username         = trim($_POST['username']);
$start_date_str   = trim($_POST['start_date']); // 'Y-m-d\TH:i[:s]'
$end_date_str     = trim($_POST['end_date']);   // 'Y-m-d\TH:i[:s]'
$amount           = (float)$_POST['amount'];
$plan_name        = trim($_POST['plan_name']);
$mikrotik_devices = trim($_POST['mikrotik_devices']); // Comma separated
$payment_method   = trim($_POST['payment_method']);
$reference_no     = isset($_POST['reference_no']) ? trim($_POST['reference_no']) : null;
$reason           = isset($_POST['reason']) ? trim($_POST['reason']) : null;
$adjusted_by      = $_SESSION['username'] ?? 'system';

// --- Payment Date Received ---
$payment_date_received_str = isset($_POST['payment_date_received']) ? trim($_POST['payment_date_received']) : null;
$manilaTz = new DateTimeZone('Asia/Manila');
$payment_date_received_db = null;
if ($payment_date_received_str !== null && $payment_date_received_str !== '') {
    $payment_date_received_dt = parseDatetimeLocal($payment_date_received_str, $manilaTz);
    if ($payment_date_received_dt !== false && $payment_date_received_dt !== null) {
        $payment_date_received_db = $payment_date_received_dt->format('Y-m-d H:i:s');
    }
}

// --- Validate reference_no (CHANGES FOR CASH) ---
if ($payment_method !== 'cash') {
    if (empty($reference_no)) {
        echo "<p>Reference No. is required for this payment method.</p>";
        include 'footer.php';
        exit;
    }
} else {
    $reference_no = null; // Use NULL for cash payments
}

// --- Validate date formats (server-side) ---
try {
    $start_date = parseDatetimeLocal($start_date_str, $manilaTz);
    $end_date   = parseDatetimeLocal($end_date_str, $manilaTz);
    if (!$start_date || !$end_date) {
        throw new Exception("Invalid date format.");
    }
    if ($end_date <= $start_date) {
        throw new Exception("End date must be after start date.");
    }
} catch (Exception $e) {
    echo "<p>Invalid date provided: " . htmlspecialchars($e->getMessage() ?? '') . "</p>";
    include 'footer.php';
    exit;
}

// Save as string in PH time
$start_date_str_db = $start_date->format('Y-m-d H:i:s');
$end_date_str_db   = $end_date->format('Y-m-d H:i:s');

// --- Fetch customer record ---
$sql  = "SELECT expires_at, plan_name, device_name FROM customers WHERE username = ? LIMIT 1";
$stmt = $pdo->prepare($sql);
$stmt->execute([$username]);
$user = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$user) {
    echo "<p>User not found.</p>";
    include 'footer.php';
    exit;
}

// --- Check that new expiry is after current expiry ---
$current_expiry = $user['expires_at'] ?? '';
if (!empty($current_expiry)) {
    try {
        $current_expiry_dt = new DateTime($current_expiry, $manilaTz);
        if ($end_date <= $current_expiry_dt) {
            echo "<p>New expiry date must be after current expiry.</p>";
            include 'footer.php';
            exit;
        }
    } catch (Exception $e) {
        // ignore, treat as no expiry
    }
}

// --- Check for duplicate reference number (CHANGES FOR CASH) ---
if ($payment_method !== 'cash') {
    $check_sql  = "SELECT 1 FROM payments WHERE reference_no = ? LIMIT 1";
    $check_stmt = $pdo->prepare($check_sql);
    $check_stmt->execute([$reference_no]);
    if ($check_stmt->fetchColumn()) {
        echo "<div style='text-align:center; margin-top:40px;'>
            <p style='color:red; font-size:1.2em;'>
                Reference No. already used. Please check your payment slip!
                <br><br>
                <a href='javascript:history.back()' style='display:inline-block; font-size:2em; text-decoration:none;' title='Go Back'>🔙</a>
            </p>
        </div>";
        include 'footer.php';
        exit;
    }
}

// --- Update customer expiry ---
$update_sql  = "UPDATE customers SET expires_at = ? WHERE username = ?";
$update_stmt = $pdo->prepare($update_sql);
$update_stmt->execute([$end_date_str_db, $username]);

// --- Insert payment record ---
$now     = new DateTime('now', $manilaTz);
$paid_at = $now->format('Y-m-d H:i:s');

// Days paid (based on start/end input)
$days_paid = round(($end_date->getTimestamp() - $start_date->getTimestamp()) / (60 * 60 * 24), 4);

// --- Insert including payment_date_received ---
$insert_sql = "INSERT INTO payments 
    (username, plan_name, mikrotik_devices, days, amount, payment_method, reference_no, expires_at, adjusted_by, paid_at, reason, payment_date_received)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
$insert_stmt = $pdo->prepare($insert_sql);
$insert_stmt->execute([
    $username,
    $plan_name,
    $mikrotik_devices,
    $days_paid,
    $amount,
    $payment_method,
    $reference_no,
    $end_date_str_db,
    $adjusted_by,
    $paid_at,
    $reason,
    $payment_date_received_db
]);

// --- CLEAR sms_sent_at FIELD IF USER PAID ---
$clear_sms_sql  = "UPDATE customers SET sms_sent_at = NULL WHERE username = ?";
$clear_sms_stmt = $pdo->prepare($clear_sms_sql);
$clear_sms_stmt->execute([$username]);

// --- MikroTik Integration for MULTIPLE devices ---
$device_list = array_map('trim', explode(',', $mikrotik_devices));
$device_list = array_filter($device_list, fn($d) => $d !== '');

$mikrotik_results = [];

foreach ($device_list as $dev_name) {
    $device_sql  = "SELECT * FROM mikrotik_devices WHERE device_name = ? LIMIT 1";
    $device_stmt = $pdo->prepare($device_sql);
    $device_stmt->execute([$dev_name]);
    $device = $device_stmt->fetch(PDO::FETCH_ASSOC);

    if (!$device) {
        $mikrotik_results[] = "🔴 Device <b>" . htmlspecialchars($dev_name) . "</b> not found.";
        continue;
    }

    $mt = new MikroTikManager(
        $device['ip_address']   ?? '',
        $device['api_username'] ?? '',
        $device['api_password'] ?? '',
        (int)($device['api_port'] ?? 22),     // SSH port, usually 22
        true,
        __DIR__ . '/mikrotik.log'
    );

    try {
        // Update PPP secret (profile, optionally name/password)
        $mt->updatePppoeUser(
            $username,   // original username
            $username,   // new username (same)
            null,        // password (leave as is)
            $plan_name   // profile
        );

        // --- Update /ppp secret comment ---
        $expiry_for_comment = (new DateTime($end_date_str_db, $manilaTz))->format('Y-m-d H:i');
        $comment_text       = "EXP: $expiry_for_comment | Adjusted at $paid_at | Plan: $plan_name | Adjusted by: $adjusted_by ";
        try {
            $mt->setPppSecretComment($username, $comment_text);
        } catch (Exception $e) {
            $mikrotik_results[] = "⚠️ Unable to update comment on <b>" . htmlspecialchars($dev_name) . "</b>: " . htmlspecialchars($e->getMessage());
        }

        // Was user expired?
        $user_expired = true;
        if (!empty($current_expiry)) {
            try {
                $current_expiry_dt = new DateTime($current_expiry, $manilaTz);
                $user_expired      = ($current_expiry_dt < $now);
            } catch (Exception $e) {
                $user_expired = true;
            }
        }

        // --- Only disconnect if user was expired ---
        if ($user_expired) {
            try {
                $mt->disconnectPppoeUser($username);
                $mikrotik_results[] = "🟢 Profile updated and disconnected on <b>" . htmlspecialchars($dev_name) . "</b>.";
            } catch (Exception $e) {
                $mikrotik_results[] = "⚠️ Updated profile but failed to disconnect on <b>" . htmlspecialchars($dev_name) . "</b>: " . htmlspecialchars($e->getMessage());
            }
        } else {
            $mikrotik_results[] = "🟢 Profile updated (no disconnect needed) on <b>" . htmlspecialchars($dev_name) . "</b>.";
        }
    } catch (Exception $e) {
        $mikrotik_results[] = "🔴 Failed to update user on <b>" . htmlspecialchars($dev_name) . "</b>: " . htmlspecialchars($e->getMessage());
    }
}

// --- Compose HTML Message (for display) ---
$msg  = "User <strong>" . htmlspecialchars($username ?? '') . "</strong> renewed successfully.<br>";
$msg .= "<strong>New expiry (PH time):</strong> <strong>" . htmlspecialchars($end_date_str_db ?? '') . "</strong>.<br>";
$msg .= "<ul style='text-align:left; max-width:500px; margin:0 auto;'>";
foreach ($mikrotik_results as $line) {
    $msg .= "<li>$line</li>";
}
$msg .= "</ul>";
$msg .= "<small>Adjusted at: " . htmlspecialchars($paid_at ?? '') . " (PH time) by " . htmlspecialchars($adjusted_by ?? '') . "</small>";

// --- Compose PLAIN TEXT Message (for copy/send to client) ---
$lines_plain = [];
$lines_plain[] = "Hello " . $username . ",";
$lines_plain[] = "Thank you for your continued support! Your internet subscription has been renewed successfully.";
$lines_plain[] = "Plan: " . $plan_name;
$lines_plain[] = "Amount Paid: " . number_format($amount, 2);
$lines_plain[] = "New Expiry (PH time): " . $end_date_str_db;
$lines_plain[] = "";
$lines_plain[] = "System Notes:";

foreach ($mikrotik_results as $line) {
    // Strip HTML tags and convert multiple spaces
    $clean = trim(preg_replace('/\s+/', ' ', strip_tags($line)));
    $lines_plain[] = "- " . $clean;
}

$lines_plain[] = "";
$lines_plain[] = "Processed at: " . $paid_at . " (PH time)";
$lines_plain[] = "Processed by: " . $adjusted_by;

$msg_plain = implode("\n", $lines_plain);

// Escape for JS (will be placed in data attribute)
$msg_plain_js = htmlspecialchars($msg_plain, ENT_QUOTES, 'UTF-8');
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Payment Result</title>
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
        ul { text-align: left; }
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
        <!-- Copy buttons -->
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
        <!-- Hidden textarea for fallback -->
        <textarea id="copyTextArea"></textarea>
    </div>

    <script>
        (function() {
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
                        // Fallback
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

            copyPlainBtn.addEventListener('click', function() {
                const msg = this.getAttribute('data-msg') || '';
                copyText(msg);
            });

            copyHtmlBtn.addEventListener('click', function() {
                const container = document.querySelector('.success-message');
                if (!container) return;
                // Clone and remove control buttons from the copy
                const clone = container.cloneNode(true);
                // Remove buttons and status so only the message HTML remains
                clone.querySelectorAll('.btn-primary, .btn-secondary, .copy-status, #copyTextArea').forEach(el => el.remove());
                const html = clone.innerHTML.trim();
                copyText(html);
            });
        })();
    </script>
</body>
</html>
<?php include 'footer.php'; ?>
