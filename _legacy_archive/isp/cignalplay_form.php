<?php
session_start();
require 'database.php';

$customer_id = $_GET['customer_id'] ?? ($_POST['customer_id'] ?? '');
$error = '';

// Fetch customer
$customer = null;
if ($customer_id) {
    $stmt = $conn->prepare("SELECT id, full_name, cignalplay_no FROM customers WHERE id=?");
    $stmt->execute([$customer_id]);
    $customer = $stmt->fetch(PDO::FETCH_ASSOC);
}

// Latest subscription + distinct plans
$latest_sub = null;
$distinct_plans = [];

if ($customer_id) {

    $stmt = $conn->prepare("
        SELECT plan_name, start_date, end_date, payment_date
        FROM cignal_play
        WHERE customer_id = ?
        ORDER BY end_date DESC, id DESC
        LIMIT 1
    ");
    $stmt->execute([$customer_id]);
    $latest_sub = $stmt->fetch(PDO::FETCH_ASSOC) ?: null;

    $stmt = $conn->prepare("
        SELECT plan_name, MAX(end_date) AS latest_end_date
        FROM cignal_play
        WHERE customer_id = ?
        GROUP BY plan_name
        ORDER BY latest_end_date DESC
    ");
    $stmt->execute([$customer_id]);
    $distinct_plans = $stmt->fetchAll(PDO::FETCH_ASSOC) ?: [];
}

// Helpers
function normalize_datetime($dt) {
    $dt = trim((string)$dt);
    if ($dt === '') return null;

    $dt = str_replace('T', ' ', $dt);
    if (strlen($dt) === 16) $dt .= ':00';

    return $dt;
}

function fmt_dt($dt) {
    return $dt ? date('M d, Y h:i A', strtotime($dt)) : '';
}

// HANDLE FORM
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $plan_name      = trim($_POST['plan_name'] ?? '');
    $rates          = (float)($_POST['rates'] ?? 0);
    $payment_method = trim($_POST['payment_method'] ?? '');
    $reference_no   = trim($_POST['reference_no'] ?? '');
    $payment_date   = $_POST['payment_date'] ?? '';
    $admin_id       = $_SESSION['admin_id'] ?? null;

    $payment_date_db = normalize_datetime($payment_date);

    // ✅ VALIDATION (THIS WAS MISSING)
    if (!$customer_id) {
        $error = "Invalid customer.";
    } 
    elseif (!$plan_name) {
        $error = "Plan name is required.";
    } 
    elseif (!$rates) {
        $error = "Rates are required.";
    } 
    elseif (!$payment_method) {
        $error = "Payment method is required.";
    } 
    elseif (!$payment_date_db) {
        $error = "Payment date is required.";
    } 
    elseif (strtolower($payment_method) !== 'cash' && empty($reference_no)) {
        $error = "Reference number is required for non-cash payments.";
    }

    // ✅ AUTO DATES
    $start_date_db = $payment_date_db;
    $end_date_db   = null;

    if ($payment_date_db) {
        $dt = new DateTime($payment_date_db);
        $day = $dt->format('d');

        $dt->modify('+1 month');
        if ($dt->format('d') !== $day) {
            $dt->modify('last day of previous month');
        }

        $dt->modify('+3 days');
        $end_date_db = $dt->format('Y-m-d H:i:s');
    }

    // ✅ GET SUBSCRIBER
    $subscriber_no = null;
    if ($customer_id) {
        $stmt = $conn->prepare("SELECT cignalplay_no FROM customers WHERE id=?");
        $stmt->execute([$customer_id]);
        $subscriber_no = $stmt->fetchColumn();
    }

    $reference_no_db = strtolower($payment_method) === 'cash' ? '' : $reference_no;

    // ✅ FINAL INSERT (NOW RELIABLE)
    if (!$error) {
        try {
            $stmt = $conn->prepare("
                INSERT INTO cignal_play
                (customer_id, subscriber_no, plan_name, rates, payment_method, reference_no, payment_date, admin_id, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ");

            $stmt->execute([
                $customer_id,
                $subscriber_no,
                $plan_name,
                $rates,
                $payment_method,
                $reference_no_db,
                $payment_date_db,
                $admin_id,
                $start_date_db,
                $end_date_db
            ]);

            header("Location: add_on_payments.php?success=1");
            exit;

        } catch (PDOException $e) {
            $error = "Database error: " . $e->getMessage();
        }
    }
}

?>




<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Client Addons Payment</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet" />
    <style>
        body{
            min-height:100vh;
            background:
                radial-gradient(1200px 600px at 10% 10%, rgba(13,110,253,.18), transparent 55%),
                radial-gradient(1000px 500px at 90% 20%, rgba(25,135,84,.16), transparent 55%),
                linear-gradient(180deg, #0b1220 0%, #0e1a2b 50%, #0b1220 100%);
        }
        .page-wrap{ min-height:100vh; display:flex; align-items:center; justify-content:center; padding: 28px 14px; }
        .card-glass{
            width:100%;
            max-width: 720px;
            border: 1px solid rgba(255,255,255,.12);
            background: rgba(255,255,255,.06);
            box-shadow: 0 18px 60px rgba(0,0,0,.45);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 18px;
            overflow:hidden;
        }
        .card-header-custom{
            background: linear-gradient(90deg, rgba(13,110,253,.22), rgba(25,135,84,.18));
            border-bottom: 1px solid rgba(255,255,255,.10);
            color: #e9f2ff;
        }
        .label-ink{ color: rgba(255,255,255,.90); }
        .form-control, .form-select{
            background-color: rgba(255,255,255,.92) !important;
            border: 1px solid rgba(0,0,0,.08) !important;
            color: #111 !important;
        }
        .form-control:focus, .form-select:focus{
            background-color: #fff !important;
            border-color: rgba(13,110,253,.65) !important;
            box-shadow: 0 0 0 .2rem rgba(13,110,253,.18) !important;
            color: #111 !important;
        }
        .divider{ height:1px; background: rgba(255,255,255,.10); margin: 14px 0; }
        .btn-soft{ border: 1px solid rgba(255,255,255,.14); background: rgba(255,255,255,.06); color: #fff; }
        .btn-soft:hover{ background: rgba(255,255,255,.10); color:#fff; }
        .badge-soft{ background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.14); color: rgba(255,255,255,.85); }
        .muted-ink{ color: rgba(255,255,255,.72); }
        .form-text{ color: rgba(255,255,255,.75) !important; }
        .alert{ border-radius: 12px; }

        /* Make "Other Plans Used (Distinct)" ALL WHITE TEXT */
        .distinct-white{
            background: rgba(255,255,255,.06) !important;
            border: 1px solid rgba(255,255,255,.14) !important;
            color: #fff !important;
        }
        .distinct-white *{ color: #fff !important; }
        .distinct-white .badge{ color: #fff !important; }
        .distinct-white .table{ color: #fff !important; }
        .distinct-white .table thead th{
            color: #fff !important;
            background: rgba(255,255,255,.10) !important;
            border-color: rgba(255,255,255,.14) !important;
        }
        .distinct-white .table tbody td{
            color: #fff !important;
            background: transparent !important;
            border-color: rgba(255,255,255,.12) !important;
        }
        .distinct-white .table tbody tr:nth-child(odd) td{
            background: rgba(255,255,255,.05) !important;
        }
    </style>
</head>
<body>
<div class="page-wrap">
    <div class="card card-glass">
        <div class="p-4 p-md-4 card-header-custom">
            <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge badge-soft rounded-pill px-3 py-2">
                        <i class="fa-solid fa-satellite-dish me-2"></i>Payment
                    </span>
                    <h4 class="m-0 fw-semibold">Client Addon Payments</h4>
                </div>
                <div class="muted-ink small">
                    <i class="fa-regular fa-clock me-2"></i><?= date('Y-m-d') ?>
                </div>
            </div>

            <?php if ($customer): ?>
                <div class="mt-3 muted-ink">
                    <i class="fa-solid fa-user me-2"></i>
                    <span class="fw-semibold text-white"><?= htmlspecialchars($customer['full_name']) ?></span>
                    <span class="ms-2 badge badge-soft">ID: <?= htmlspecialchars($customer['id']) ?></span>
                    <span class="ms-2 badge badge-soft">
                        Subscriber No: <?= htmlspecialchars($customer['cignalplay_no'] ?? '') ?>
                    </span>
                </div>

  

        <div class="p-4 p-md-4 text-white">
            <?php if ($error): ?>
                <div class="alert alert-danger mb-4">
                    <i class="fa-solid fa-triangle-exclamation me-2"></i>
                    <?= htmlspecialchars($error) ?>
                </div>
            <?php endif; ?>

            <form method="post" autocomplete="off">
                <input type="hidden" name="customer_id" value="<?= htmlspecialchars($customer_id) ?>">

                <div class="row g-3">
                    <div class="col-12">
                        <label class="form-label label-ink">Item Name</label>
                        <input type="text" name="plan_name" id="plan_name" class="form-control" required
       value="<?= htmlspecialchars($_POST['plan_name'] ?? '') ?>"
       placeholder="Enter item name">

                    </div>



                    <div class="col-12 col-md-6">
                        <label class="form-label label-ink">Total Rates (PHP)</label>
                        <div class="input-group">
                            <span class="input-group-text">₱</span>
                          <input type="number" name="rates" id="rates" class="form-control" step="0.01" required
       value="<?= htmlspecialchars($_POST['rates'] ?? '') ?>">

                        </div>
                    </div>

                    <div class="col-12"><div class="divider"></div></div>

                    <div class="col-12 col-md-6">
                        <label class="form-label label-ink">Payment Method</label>
                        <select name="payment_method" id="payment_method" class="form-select" required onchange="handlePaymentMethodChange()">
                            <option value="">-- Select Payment Method --</option>
                            <option value="cash">Cash</option>
                            <option value="bank transfer">Bank Transfer</option>
                            <option value="e-wallet">E-wallet</option>
                            <option value="payment center">Payment Center</option>
                            <option value="online banking">Online Banking</option>
                        </select>
                    </div>

                    <div class="col-12 col-md-6">
                        <label class="form-label label-ink">Payment Date Received</label>
                        <input type="datetime-local" name="payment_date" class="form-control" required step="1">
                    </div>



                    <div class="col-12">
                        <label class="form-label label-ink">Reference No</label>
                        <input type="text" name="reference_no" id="reference_no" class="form-control" maxlength="100" disabled
                               placeholder="Enter reference number (non-cash)">
                        <div id="reference_no_note" class="form-text">
                            Required for non-cash payments.
                        </div>
                    </div>

                    <div class="col-12 d-flex gap-2 flex-wrap mt-2">
                        <button type="submit" class="btn btn-success px-4">
                            <i class="fas fa-save me-2"></i>Submit Payment
                        </button>
                        <a href="add_on_payments.php" class="btn btn-soft px-4">
                            <i class="fa-solid fa-arrow-left me-2"></i>Back to List
                        </a>
                    </div>
                </div>
            </form>
        </div>
    </div>
</div>

<script>


function handlePaymentMethodChange() {
    const pm = (document.getElementById('payment_method').value || '').toLowerCase();
    const ref = document.getElementById('reference_no');
    const note = document.getElementById('reference_no_note');

    if (pm === 'cash' || pm === '') {
        ref.disabled = true;
        ref.value = '';
        note.classList.remove('text-danger');
        note.classList.add('text-white-50');
    } else {
        ref.disabled = false;
        note.classList.remove('text-white-50');
        note.classList.add('text-danger');
    }
}

// Add 1 calendar month + 3 days grace (preserves time)
function calcEndFromStart(startLocal) {
    if (!startLocal) return '';
    const d = new Date(startLocal);
    if (isNaN(d.getTime())) return '';

    const originalDay = d.getDate();
    d.setMonth(d.getMonth() + 1);
    if (d.getDate() !== originalDay) d.setDate(0);
    d.setDate(d.getDate() + 3);

    const pad = (n) => String(n).padStart(2, '0');
    return (
        d.getFullYear() + '-' +
        pad(d.getMonth() + 1) + '-' +
        pad(d.getDate()) + 'T' +
        pad(d.getHours()) + ':' +
        pad(d.getMinutes()) + ':' +
        pad(d.getSeconds())
    );
}

function updateEndDateIfEmptyOrAuto() {
    const startEl = document.getElementById('start_date');
    const endEl = document.getElementById('end_date');

    const auto = calcEndFromStart(startEl.value);
    if (!auto) return;

    // Only overwrite end_date if user hasn't edited it:
    // - end is empty OR matches last auto value
    const prevAuto = endEl.dataset.autoValue || '';
    if (endEl.value === '' || endEl.value === prevAuto) {
        endEl.value = auto;
    }
    endEl.dataset.autoValue = auto; // remember latest auto calc
}

window.addEventListener('load', () => {
    handlePaymentMethodChange();
  
    updateEndDateIfEmptyOrAuto();
});

document.getElementById('start_date').addEventListener('change', updateEndDateIfEmptyOrAuto);
document.getElementById('start_date').addEventListener('input', updateEndDateIfEmptyOrAuto);
</script>








<script>
function handlePaymentMethodChange() {
    const pm = (document.getElementById('payment_method').value || '').toLowerCase();
    const ref = document.getElementById('reference_no');
    const note = document.getElementById('reference_no_note');

    if (!ref || !note) return;

    if (pm === 'cash' || pm === '') {
        ref.disabled = true;
        ref.value = '';
        note.classList.remove('text-danger');
        note.classList.add('text-white-50');
    } else {
        ref.disabled = false;
        note.classList.remove('text-white-50');
        note.classList.add('text-danger');
    }
}

window.addEventListener('load', () => {
    handlePaymentMethodChange();
});
</script>











</body>
</html>
<?php endif; ?>
