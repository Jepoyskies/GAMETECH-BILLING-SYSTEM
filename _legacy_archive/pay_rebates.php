<?php
include 'header.php';
include 'database.php'; // $pdo (PDO)

// Check username param
if (!isset($_GET['username'])) {
    echo "<p>Username is required.</p>";
    include 'footer.php';
    exit;
}

$username = $_GET['username'];

// Use prepared statement for security
$sql = "SELECT username, expires_at, plan_name, device_name FROM customers WHERE username = ? LIMIT 1";
$stmt = $pdo->prepare($sql);
$stmt->execute([$username]);
$user = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$user) {
    echo "<p>User not found.</p>";
    include 'footer.php';
    exit;
}

// No timezone conversion; use as-is
$expires_display = '';
$expires_js = '';
if (!empty($user['expires_at'])) {
    $expires_display = $user['expires_at'];
    // For <input type="datetime-local">, replace space with 'T'
    $expires_js = str_replace(' ', 'T', $user['expires_at']);
} else {
    // If blank, use now
    $now = date('Y-m-d H:i:s');
    $expires_display = '';
    $expires_js = date('Y-m-d\TH:i:s');
}

// (Optional) Fetch list of devices for dropdown (not used)
$device_options = [];
$dev_stmt = $pdo->query("SELECT device_name FROM mikrotik_devices");
while ($dev = $dev_stmt->fetch(PDO::FETCH_ASSOC)) {
    $device_options[] = $dev['device_name'];
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Rebate for <?php echo htmlspecialchars($user['username']); ?></title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        .pay-form {
            max-width: 400px;
            margin: 2rem auto;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        .pay-form label { font-weight: bold; }
        .pay-form input[type="text"], .pay-form textarea {
            width: 100%;
            padding: 0.5rem;
            margin-bottom: 1rem;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        .pay-form select, .pay-form input[type="date"], .pay-form input[type="datetime-local"] {
            width: 100%;
            padding: 0.5rem;
            margin-bottom: 1rem;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        .pay-form button {
            width: 100%;
            padding: 0.7rem;
            background: #28a745;
            color: #fff;
            border: none;
            border-radius: 4px;
            font-size: 1.1rem;
            font-weight: bold;
        }
        .due-label {
            margin-top: -15px;
            margin-bottom: 5px;
            color: #007bff;
            font-weight: bold;
            font-size: 0.98rem;
        }
        .due-date {
            margin-bottom: 1rem;
            color: #155724;
            font-weight: bold;
            font-size: 1.05rem;
        }
        .btn-full-width {
            display: inline-block;
            width: 100%;
            text-align: center;
        }
    </style>
    <script>
        // expireStr is always in 'YYYY-MM-DDTHH:MM:SS'
        var expireStr = "<?php echo $expires_js; ?>";

        function formatDisplay(dt) {
            // For showing as 'YYYY-MM-DD HH:MM:SS'
            function pad(n) { return n < 10 ? '0'+n : n }
            return dt.getFullYear() + '-' +
                   pad(dt.getMonth()+1) + '-' +
                   pad(dt.getDate()) + ' ' +
                   pad(dt.getHours()) + ':' +
                   pad(dt.getMinutes()) + ':' +
                   pad(dt.getSeconds());
        }

        function updateDue(){
            var dtInput = document.getElementById('new_due_date_time');
            if (!dtInput.value) {
                document.getElementById('due-date').textContent = '';
                return;
            }
            var selected = new Date(dtInput.value.replace(' ', 'T'));
            document.getElementById('due-date').textContent = formatDisplay(selected) + " (PH Time)";
        }

        window.onload = function() {
            var dtInput = document.getElementById('new_due_date_time');
            dtInput.min = expireStr;
            dtInput.value = expireStr;
            updateDue();
        };
    </script>
</head>
<body>
    <div class="pay-form">
        <h3>Get Rebates</h3>

        <form action="pay_process_rebates.php" method="post" autocomplete="off">
            <label>Username</label>
            <input type="text" name="username" value="<?php echo htmlspecialchars($user['username']); ?>" readonly>

            <label>Mikrotik Device</label>
            <input type="text" name="mikrotik_devices" value="<?php echo htmlspecialchars($user['device_name']); ?>" required>

            <label>Current Expiry (Philippine Time)</label>
            <input type="text" value="<?php echo htmlspecialchars($expires_display); ?>" readonly>

            <label>Set New Expiry Date and Time (PH Time)</label>
            <input type="datetime-local" name="new_due_date_time" id="new_due_date_time" step="1" required onchange="updateDue()">

            <div class="due-label">New Due For Rebates:</div>
            <div class="due-date" id="due-date"></div>

            <label>Plan</label>
            <input type="text" value="<?php echo htmlspecialchars($user['plan_name']); ?>" readonly>
            <input type="hidden" name="plan_name" value="<?php echo htmlspecialchars($user['plan_name']); ?>">

            <label>Note (Reason of Rebates)</label>
            <textarea name="note" rows="2" style="width:100%;" placeholder="Add a note..." required></textarea>

            <button type="submit" class="btn btn-success btn-full-width">Renew</button>

            <a href="subscription_plans.php" class="btn btn-secondary btn-full-width mt-2">
                Back
            </a>
        </form>
    </div>
    <script>updateDue();</script>
</body>
</html>
<?php include 'footer.php'; ?>
