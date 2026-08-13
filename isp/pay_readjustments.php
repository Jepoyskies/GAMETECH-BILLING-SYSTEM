<?php
include 'header.php';
include 'database.php';

if (!isset($_GET['username'])) {
    echo "<p>Username is required.</p>";
    include 'footer.php';
    exit;
}
$username = $_GET['username'];
$stmt = $pdo->prepare("SELECT username, expires_at, plan_name, device_name FROM customers WHERE username = ? LIMIT 1");
$stmt->execute([$username]);
$user = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$user) {
    echo "<p>User not found.</p>";
    include 'footer.php';
    exit;
}

// Get expiry in UTC
$expires_display = '';
$expires_js = '';
if (!empty($user['expires_at'])) {
    try {
        $dt = new DateTime($user['expires_at'], new DateTimeZone('UTC'));
        $expires_display = $dt->format('Y-m-d H:i:s'); // 24h UTC
        $expires_js = $dt->format('Y-m-d\TH:i'); // for datetime-local (no seconds)
    } catch (Exception $e) {
        $expires_display = htmlspecialchars($user['expires_at']);
        $expires_js = '';
    }
} else {
    $expires_display = 'N/A';
    $expires_js = '';
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Rollback Expiry for <?php echo htmlspecialchars($user['username']); ?></title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        .pay-form { max-width: 420px; margin: 2rem auto; border: 1px solid #eee;
            border-radius: 8px; padding: 1.5rem; }
        .pay-form label { font-weight: bold; }
        .pay-form input[type="text"], .pay-form input[type="datetime-local"], .pay-form textarea {
            width: 100%; padding: 0.5rem; margin-bottom: 1rem; border: 1px solid #ccc; border-radius: 4px;
        }
        .pay-form button { width: 100%; padding: 0.7rem; background: #dc3545; color: #fff; border: none;
            border-radius: 4px; font-size: 1.1rem; font-weight: bold;}
        .info-label { font-weight: bold; color: #444; margin-bottom: 4px;}
        .due-date { margin-bottom: 1rem; color: #155724; font-weight: bold; font-size: 1.05rem;}
        .days-count { font-weight: bold; color: #c0392b; margin-bottom: 1rem;}
        .btn-full-width { display: inline-block; width: 100%; text-align: center;}
        .error-msg { color: #b71c1c; font-weight: bold; margin-bottom: 1rem;}
    </style>
    <script>
        function calcRollback() {
            var currentExpiryStr = "<?php echo $expires_js; ?>";
            // Date parsing: expects 'YYYY-MM-DDTHH:MM'
            var currentExpiry = currentExpiryStr ? new Date(currentExpiryStr + ":00Z") : null; // Add seconds + Z for UTC
            // User-selected rollback date
            var rollbackToStr = document.getElementById('rollback-to').value;
            var rollbackTo = rollbackToStr ? new Date(rollbackToStr + ":00Z") : null; // Add seconds + Z for UTC
            var daysField = document.getElementById('rollback-days');
            var daysLabel = document.getElementById('rollback-days-label');
            var newExpiryField = document.getElementById('rollback-expiry');
            var errMsg = document.getElementById('error-msg');

            if (currentExpiry && rollbackTo) {
                var ms = currentExpiry - rollbackTo;
                if (ms < 0) {
                    daysField.value = '';
                    daysLabel.textContent = '';
                    newExpiryField.textContent = '';
                    errMsg.textContent = "Rollback date/time is after current expiry!";
                } else {
                    errMsg.textContent = '';
                    // Calculate difference in days, hours, minutes
                    var totalMinutes = Math.floor(ms / (1000 * 60));
                    var days = Math.floor(totalMinutes / (60 * 24));
                    var hours = Math.floor((totalMinutes % (60 * 24)) / 60);
                    var mins = totalMinutes % 60;

                    daysField.value = ms;
                    daysLabel.textContent = "Rollback: " +
                        (days > 0 ? days + " day(s) " : "") +
                        (hours > 0 ? hours + " hour(s) " : "") +
                        (mins > 0 ? mins + " minute(s)" : "");

                    // Format new expiry for display (UTC)
                    var y = rollbackTo.getUTCFullYear();
                    var m = String(rollbackTo.getUTCMonth()+1).padStart(2, '0');
                    var d = String(rollbackTo.getUTCDate()).padStart(2, '0');
                    var h = String(rollbackTo.getUTCHours()).padStart(2, '0');
                    var min = String(rollbackTo.getUTCMinutes()).padStart(2, '0');
                    var s = String(rollbackTo.getUTCSeconds()).padStart(2, '0');
                    newExpiryField.textContent = y + '-' + m + '-' + d + ' ' + h + ':' + min + ':' + s + " (UTC)";
                }
            } else {
                daysField.value = '';
                daysLabel.textContent = '';
                newExpiryField.textContent = '';
                errMsg.textContent = '';
            }
        }
        window.addEventListener('DOMContentLoaded', function() {
            calcRollback();
            document.getElementById('rollback-to').addEventListener('input', calcRollback);
        });
    </script>
</head>
<body>
<div class="pay-form">
    <h3>Rollback Expiry</h3>
    <form action="pay_process_readjustments.php" method="post" autocomplete="off">
        <label>Username</label>
        <input type="text" name="username" value="<?php echo htmlspecialchars($user['username']); ?>" readonly>

        <label>Mikrotik Device</label>
        <input type="text" name="mikrotik_devices" value="<?php echo htmlspecialchars($user['device_name']); ?>" required>

        <label>Current Plan</label>
        <input type="text" value="<?php echo htmlspecialchars($user['plan_name']); ?>" readonly>

        <label>Current Expiry (UTC, 24h)</label>
        <input type="text" value="<?php echo htmlspecialchars($expires_display); ?>" readonly>

        <label>Rollback To (set new expiry date and time, UTC)</label>
        <input type="datetime-local" id="rollback-to" name="rollback_to"
               required
               value="<?php echo $expires_js; ?>">

        <input type="hidden" id="rollback-days" name="rollback_ms">
        <div class="days-count" id="rollback-days-label"></div>
        <div class="error-msg" id="error-msg"></div>

        <div class="info-label">New Expiry After Rollback:</div>
        <div class="due-date" id="rollback-expiry"></div>

        <label>Note (Reason for rollback)</label>
        <textarea name="note" rows="2" placeholder="Reason for rollback..." required></textarea>

        <button type="submit" class="btn btn-danger btn-full-width">Rollback</button>
        <a href="subscription_plans.php" class="btn btn-secondary btn-full-width mt-2">Back</a>
    </form>
</div>
</body>
</html>
<?php include 'footer.php'; ?>
