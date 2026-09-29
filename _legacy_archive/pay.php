<?php
include 'header.php';
include 'database.php'; // $pdo (PDO)

if (!isset($_GET['username'])) {
    echo "<p>Username is required.</p>";
    include 'footer.php';
    exit;
}

$username = $_GET['username'];
$stmt = $pdo->prepare("SELECT username, expires_at, plan_name, device_name FROM customers WHERE username = :username LIMIT 1");
$stmt->execute(['username' => $username]);
$user = $stmt->fetch();

if (!$user) {
    echo "<p>User not found.</p>";
    include 'footer.php';
    exit;
}

// --- Current Expiry (display as UTC, 24h format) ---
$current_expiry_display = '';
if (!empty($user['expires_at'])) {
    try {
        $dt_utc = new DateTime($user['expires_at'], new DateTimeZone('UTC'));
        $current_expiry_display = $dt_utc->format('Y-m-d H:i:s'); // 24h format, UTC
        $current_expiry_ph = clone $dt_utc; // You can still use for calculations if needed
    } catch (Exception $e) {
        $current_expiry_display = htmlspecialchars($user['expires_at']);
        $current_expiry_ph = new DateTime('now', new DateTimeZone('UTC'));
    }
} else {
    $current_expiry_display = '';
    $current_expiry_ph = new DateTime('now', new DateTimeZone('UTC'));
}

// ---- Default Start Date = current expiry (but user can set any date) ----
$start_dt = clone $current_expiry_ph;
$start_default_str = $start_dt->format('Y-m-d\TH:i:s');

// -- End date is exactly next month (UTC calendar) from new start date
$end_default_dt = clone $start_dt;
$end_default_dt->modify('+1 month');
$end_default_str = $end_default_dt->format('Y-m-d\TH:i:s');

$plan_stmt = $pdo->prepare("SELECT price FROM service_plans WHERE plan_name = :plan_name LIMIT 1");
$plan_stmt->execute(['plan_name' => $user['plan_name']]);
$plan = $plan_stmt->fetch();
$monthly_price = $plan ? floatval($plan['price']) : 0;

$current_expiry_display_safe = htmlspecialchars($current_expiry_display);
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Pay for <?php echo htmlspecialchars($user['username']); ?></title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        .pay-form { max-width: 440px; margin: 2rem auto; border: 1px solid #eee; border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08);}
        .pay-form label { font-weight: bold; }
        .pay-form input[type="text"], .pay-form input[type="datetime-local"], .pay-form input[type="number"] { width: 100%; padding: 0.5rem; margin-bottom: 1rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;}
        .pay-form select { width: 100%; padding: 0.5rem; margin-bottom: 1rem; border: 1px solid #ccc; border-radius: 4px;}
        .pay-form button, .pay-form a.btn { width: 100%; padding: 0.7rem; background: #28a745; color: #fff; border: none; border-radius: 4px; font-size: 1.1rem; font-weight: bold; text-align: center; display: block; text-decoration: none; margin-top: 10px;}
        .pay-form a.btn { background: #6c757d; }
        .due-label, .due-date { margin-top: -10px; margin-bottom: 10px; color: #007bff; font-weight: bold; font-size: 1.02rem;}
        .due-date { color: #155724; font-size: 1.08rem;}
        #amount-note { color: #555; font-size: 0.95em; margin-bottom: 8px;}
        #reason-block label { font-weight: normal;}
        #reason-block input[type="text"] { margin-bottom: 0.5em;}
    </style>
</head>
<body>
    <div class="pay-form">
        <h3>Renew Subscription</h3>
        <form action="pay_process.php" method="post" autocomplete="off" id="renew-form">
            <label for="username">Username</label>
            <input type="text" name="username" id="username" value="<?php echo htmlspecialchars($user['username']); ?>" readonly>

            <label for="mikrotik_devices">Mikrotik Device</label>
            <input type="text" id="mikrotik_devices_show" value="<?php echo htmlspecialchars($user['device_name']); ?>" readonly>
            <input type="hidden" name="mikrotik_devices" value="<?php echo htmlspecialchars($user['device_name']); ?>">

            <label for="current_expiry">Current Expiry (UTC, 24h)</label>
            <input type="text" id="current_expiry" value="<?php echo $current_expiry_display_safe; ?>" readonly>

            <label for="start_date">Start Date (UTC Time)</label>
            <input
                type="datetime-local"
                id="start_date"
                name="start_date"
                required
                value="<?php echo $start_default_str; ?>"
                step="1"
            >

            <label for="end_date">End Date (UTC Time)</label>
            <input
                type="datetime-local"
                id="end_date"
                name="end_date"
                required
                value="<?php echo $end_default_str; ?>"
                min=""
                step="1"
            >

            <label for="days">Days Adjusted</label>
            <input
                type="number"
                id="days"
                name="days"
                min="1"
                value=""
                required
                readonly
            >

            <div class="due-label">New Expiry Date:</div>
            <div class="due-date" id="due-date"></div>

            <label for="plan_name">Plan</label>
            <input type="text" id="plan_name_show" value="<?php echo htmlspecialchars($user['plan_name']); ?>" readonly>
            <input type="hidden" name="plan_name" value="<?php echo htmlspecialchars($user['plan_name']); ?>">

            <label for="amount">Amount (₱)</label>
            <div id="amount-confirm-block">
                <input type="text" id="amount" name="amount" value="" readonly>
                <div id="amount-question" style="margin: 0.5em 0; display: flex; align-items: center; gap: 12px;">
                    <span style="white-space: nowrap;">Is this amount correct?</span>
                    <label style="display: flex; align-items: center; gap: 4px; font-weight: normal; cursor:pointer;">
                        <input type="radio" name="amount_correct" id="amount_yes" value="yes" checked>
                        Yes
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-weight: normal; cursor:pointer;">
                        <input type="radio" name="amount_correct" id="amount_no" value="no">
                        No
                    </label>
                </div>
                <div id="reason-block" style="display:none; margin-top:8px;">
                    <label for="reason" style="font-weight:normal;">Reason why?</label>
                    <input type="text" id="reason" name="reason" maxlength="255" placeholder="Please specify reason">
                </div>
            </div>

            <label for="payment_method">Payment Method</label>
            <select name="payment_method" id="payment_method" required>
                <option value="">-- Select --</option>
                <option value="cash">Cash</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="e-wallet">E-Wallet</option>
                <option value="payment_center">Payment Center</option>
                <option value="online_banking">Online Banking</option>
            </select>

            <label for="reference_no">Reference No.</label>
            <input type="text" name="reference_no" id="reference_no" maxlength="64">

            <!-- Payment Date Received field (REQUIRED) -->
            <label for="payment_date_received">Payment Date Received</label>
            <input 
                type="datetime-local" 
                name="payment_date_received" 
                id="payment_date_received"
                value=""
                step="1"
                required
            >

            <button type="submit" class="btn btn-success btn-full-width">Pay & Renew</button>
            <a href="subscription_plans.php" class="btn btn-secondary btn-full-width mt-2">
                Back
            </a>
        </form>
    </div>
<script>
document.addEventListener('DOMContentLoaded', function() {
    // Helpers
    function pad(n) { return n < 10 ? '0'+n : n; }
    function formatUtcDatetime(dt) {
        return dt.getUTCFullYear() + '-' +
               pad(dt.getUTCMonth()+1) + '-' +
               pad(dt.getUTCDate()) + ' ' +
               pad(dt.getUTCHours()) + ':' +
               pad(dt.getUTCMinutes()) + ':' +
               pad(dt.getUTCSeconds());
    }
    function formatInputDatetime(dt) {
        // yyyy-mm-ddTHH:MM:SS
        return dt.getUTCFullYear() + '-' +
               pad(dt.getUTCMonth()+1) + '-' +
               pad(dt.getUTCDate()) + 'T' +
               pad(dt.getUTCHours()) + ':' +
               pad(dt.getUTCMinutes()) + ':' +
               pad(dt.getUTCSeconds());
    }

    // Amount radio logic
    function handleAmountRadioChange() {
        var yesChecked = document.getElementById('amount_yes').checked;
        var amountInput = document.getElementById('amount');
        var reasonBlock = document.getElementById('reason-block');
        var reasonInput = document.getElementById('reason');
        if (yesChecked) {
            amountInput.readOnly = true;
            reasonBlock.style.display = 'none';
            reasonInput.required = false;
            reasonInput.value = '';
            var note = document.getElementById('amount-note');
            if (note) note.remove();
        } else {
            amountInput.readOnly = false;
            amountInput.focus();
            reasonBlock.style.display = '';
            reasonInput.required = true;
            if (!document.getElementById('amount-note')) {
                var note = document.createElement('div');
                note.id = 'amount-note';
                note.textContent = "Please enter the correct amount and specify the reason.";
                amountInput.parentNode.appendChild(note);
            }
        }
    }
    document.getElementById('amount_yes').addEventListener('change', handleAmountRadioChange);
    document.getElementById('amount_no').addEventListener('change', handleAmountRadioChange);
    handleAmountRadioChange();

    // Main logic for Start Date / End Date / Days / Amount
    const startInput = document.getElementById('start_date');
    const endInput = document.getElementById('end_date');
    const daysInput = document.getElementById('days');
    const dueDateDiv = document.getElementById('due-date');
    const amountInput = document.getElementById('amount');
    const monthlyPrice = <?php echo json_encode($monthly_price); ?>;

    function getDateFromInput(str) {
        if (!str || !str.includes(':')) return null;
        let base = str;
        if (base.length === 16) base += ":00";
        return new Date(base.replace('T', ' ') + 'Z');
    }

    function addOneMonthUTC(dt) {
        let year = dt.getUTCFullYear();
        let month = dt.getUTCMonth();
        let day = dt.getUTCDate();
        let hours = dt.getUTCHours();
        let minutes = dt.getUTCMinutes();
        let seconds = dt.getUTCSeconds();

        let nextMonth = new Date(Date.UTC(year, month, day, hours, minutes, seconds));
        nextMonth.setUTCMonth(month + 1);

        if (nextMonth.getUTCDate() !== day) {
            nextMonth.setUTCDate(0);
        }
        nextMonth.setUTCHours(hours, minutes, seconds, 0);
        return nextMonth;
    }

    function updateEndMin() {
        if (!startInput.value) return;
        let startDate = getDateFromInput(startInput.value);
        if (!startDate) return;
        let minEndDate = new Date(startDate.getTime() + 1000);
        endInput.min = formatInputDatetime(minEndDate);
        let endDate = getDateFromInput(endInput.value);
        if (endDate && endDate < minEndDate) {
            endInput.value = formatInputDatetime(minEndDate);
        }
    }

    function isExactlyOneUTCMonth(startDate, endDate) {
        let exactlyOneMonth = addOneMonthUTC(startDate);
        return Math.abs(endDate.getTime() - exactlyOneMonth.getTime()) < 2000;
    }

    function updateDueDaysAmount(from) {
        let startStr = startInput.value;
        let endStr = endInput.value;

        let showDue = "";
        let days = 0;
        let amount = 0;

        if (!startStr || !endStr) {
            daysInput.value = "";
            amountInput.value = "";
            dueDateDiv.textContent = "";
            return;
        }

        let startDate = getDateFromInput(startStr);
        let endDate = getDateFromInput(endStr);

        if (endDate <= startDate) {
            if (from === 'end') {
                let newStart = new Date(endDate.getTime() - 1000);
                startInput.value = formatInputDatetime(newStart);
                startDate = newStart;
            } else {
                let newEnd = new Date(startDate.getTime() + 1000);
                endInput.value = formatInputDatetime(newEnd);
                endDate = newEnd;
            }
        }

        let diffMs = endDate - startDate;
        days = diffMs / (1000 * 60 * 60 * 24);
        daysInput.value = (Math.round(days * 100000) / 100000).toFixed(5).replace(/\.?0+$/, '');

        showDue = formatUtcDatetime(endDate) + " (UTC)";
        dueDateDiv.textContent = showDue;

        if (isExactlyOneUTCMonth(startDate, endDate)) {
            amount = monthlyPrice;
        } else {
            amount = (monthlyPrice / 30) * days;
        }
        amountInput.value = Math.round(amount * 100) / 100;
    }

    startInput.addEventListener('change', function() {
        let startDate = getDateFromInput(startInput.value);
        if (startDate) {
            let nextMonth = addOneMonthUTC(startDate);
            endInput.value = formatInputDatetime(nextMonth);
        }
        updateEndMin();
        updateDueDaysAmount('start');
    });

    endInput.addEventListener('change', function() {
        updateDueDaysAmount('end');
    });

    startInput.value = "<?php echo $start_default_str; ?>";
    let initialStartDate = getDateFromInput(startInput.value);
    if (initialStartDate) {
        let initialEndDate = addOneMonthUTC(initialStartDate);
        endInput.value = formatInputDatetime(initialEndDate);
    }
    updateEndMin();
    updateDueDaysAmount();

    var paymentMethodSelect = document.getElementById('payment_method');
    var referenceNoInput = document.getElementById('reference_no');
    function handleReferenceNoRequirement() {
        if (paymentMethodSelect.value === 'cash') {
            referenceNoInput.disabled = true;
            referenceNoInput.required = false;
            referenceNoInput.value = '';
        } else {
            referenceNoInput.disabled = false;
            referenceNoInput.required = true;
        }
    }
    paymentMethodSelect.addEventListener('change', handleReferenceNoRequirement);
    handleReferenceNoRequirement();

    // ENFORCE Payment Date Received is required
    document.getElementById('renew-form').addEventListener('submit', function(e) {
        var yesChecked = document.getElementById('amount_yes').checked;
        var reasonInput = document.getElementById('reason');
        var paymentDateInput = document.getElementById('payment_date_received');

        if (!paymentDateInput.value) {
            alert('Payment Date Received is required.');
            paymentDateInput.focus();
            e.preventDefault();
            return;
        }
        if (!yesChecked && reasonInput.value.trim() === '') {
            alert('Amount does not match expected value and no reason provided.');
            reasonInput.focus();
            e.preventDefault();
            return;
        }
        if (paymentMethodSelect.value !== 'cash') {
            if (referenceNoInput.value.trim() === '') {
                alert('Reference No. is required for this payment method.');
                referenceNoInput.focus();
                e.preventDefault();
                return;
            }
        }
    });
});
</script>
</body>
</html>
<?php include 'footer.php'; ?>
