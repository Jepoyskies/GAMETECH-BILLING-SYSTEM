<?php
// edit_customer_cignalplay.php  (or edit_customer.php)

require 'database.php';
require 'log_system_action.php';

if (session_status() === PHP_SESSION_NONE) session_start();

$success = false;
$error = '';
$notification = $_SESSION['notification'] ?? '';
unset($_SESSION['notification']);

// --- Get customer ID ---
$customer_id = $_GET['id'] ?? $_POST['id'] ?? null;
if (!$customer_id) die("Customer ID missing.");

// --- Fetch old data for logging & form population ---
$stmt = $conn->prepare("SELECT * FROM customers WHERE id = ?");
$stmt->execute([$customer_id]);
$old_data = $stmt->fetch(PDO::FETCH_ASSOC);
if (!$old_data) die("Customer not found.");

// --- Handle POST submission ---
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username      = trim($_POST['username'] ?? '');
    $cignalplay_no = trim($_POST['cignalplay_no'] ?? '');

    // NEW: datetime-local instead of date
    $cignalplay_date_raw = trim($_POST['cignalplay_date'] ?? '');
    $cignalplay_date = null;
    if ($cignalplay_date_raw !== '') {
        // Convert "YYYY-MM-DDTHH:MM" to "YYYY-MM-DD HH:MM:SS"
        $dt = DateTime::createFromFormat('Y-m-d\TH:i', $cignalplay_date_raw);
        if ($dt === false) {
            $error = "Invalid Cignal Play Subscription Date/Time.";
        } else {
            $cignalplay_date = $dt->format('Y-m-d H:i:s');
        }
    }

    $mac_address     = $old_data['mac_address'] ?? '';
    $created_form_by = $old_data['created_form_by'] ?? ($_SESSION['username'] ?? 'system');

    // Save admin username in cignalplay_adjustedby
    $cignalplay_adjustedby = $_SESSION['admin_username'] ?? ($_SESSION['username'] ?? 'admin');

    // Check username uniqueness (excluding current user) if username is not blank
    if (!$error && $username !== '') {
        $stmt = $conn->prepare("SELECT COUNT(*) FROM customers WHERE username = ? AND id != ?");
        $stmt->execute([$username, $customer_id]);
        if ($stmt->fetchColumn() > 0) {
            $error = "Username already exists, please choose another.";
        }
    }

    if (!$error) {
        $stmt = $conn->prepare("
            UPDATE customers
            SET username=?, mac_address=?, created_form_by=?, cignalplay_no=?, cignalplay_date=?, cignalplay_adjustedby=?
            WHERE id=?
        ");
        $stmt->execute([
            $username,
            $mac_address,
            $created_form_by,
            $cignalplay_no,
            $cignalplay_date,
            $cignalplay_adjustedby,
            $customer_id
        ]);

        // --- Logging ---
        $changed_by = $_SESSION['username'] ?? 'system';
        $new_data = [
            'username' => $username,
            'mac_address' => $mac_address,
            'created_form_by' => $created_form_by,
            'cignalplay_no' => $cignalplay_no,
            'cignalplay_date' => $cignalplay_date,
            'cignalplay_adjustedby' => $cignalplay_adjustedby
        ];
        $old_data_log = [
            'username' => $old_data['username'] ?? null,
            'mac_address' => $old_data['mac_address'] ?? null,
            'created_form_by' => $old_data['created_form_by'] ?? null,
            'cignalplay_no' => $old_data['cignalplay_no'] ?? null,
            'cignalplay_date' => $old_data['cignalplay_date'] ?? null,
            'cignalplay_adjustedby' => $old_data['cignalplay_adjustedby'] ?? null
        ];
        log_system_action($conn, 'customers', $customer_id, 'update', $changed_by, $old_data_log, $new_data);

        $_SESSION['notification'] = "Customer updated successfully!";
        header("Location: add_on_payments.php");
        exit();
    } else {
        // Repopulate for error case
        $old_data = array_merge($old_data, [
            'username' => $username,
            'cignalplay_no' => $cignalplay_no,
            'cignalplay_date' => $cignalplay_date
        ]);
    }
}

// --- Fetch available PPPoE usernames for dropdown ---
$current_username = $old_data['username'] ?? '';
$available_usernames = [];

$stmt = $conn->prepare("
    SELECT p.username
    FROM pppoe_users p
    LEFT JOIN customers c ON p.username = c.username
    WHERE (c.username IS NULL OR p.username = ?)
    ORDER BY p.username ASC
");
$stmt->execute([$current_username]);
while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
    $available_usernames[] = $row['username'];
}

// Display adjusted by
$display_adjustedby = $old_data['cignalplay_adjustedby'] ?? ($_SESSION['admin_username'] ?? ($_SESSION['username'] ?? 'admin'));

// Prefill datetime-local value from DB "Y-m-d H:i:s" -> "Y-m-d\TH:i"
$cignalplay_date_value = '';
if (!empty($old_data['cignalplay_date'])) {
    $ts = strtotime($old_data['cignalplay_date']);
    if ($ts) $cignalplay_date_value = date('Y-m-d\TH:i', $ts);
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Edit Customer</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet" />

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>

    <style>
        :root{
            --brand:#0d6efd;
            --soft:#f6f9ff;
            --card:#ffffff;
            --border:#e7eef8;
            --text:#0f172a;
            --muted:#64748b;
        }
        body{
            background: linear-gradient(180deg, var(--soft), #fff);
            color: var(--text);
        }
        .page-wrap{ max-width: 920px; margin: 0 auto; }
        .page-header{
            background: radial-gradient(1200px 300px at 10% 0%, rgba(13,110,253,.18), transparent 60%),
                        radial-gradient(900px 240px at 90% 10%, rgba(25,135,84,.12), transparent 55%),
                        #fff;
            border: 1px solid var(--border);
            border-radius: 16px;
        }
        .icon-pill{
            width:44px;height:44px;border-radius:14px;
            display:inline-flex;align-items:center;justify-content:center;
            background: rgba(13,110,253,.1);
            color: var(--brand);
        }
        .card-form{
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
        }
        .card-form .card-header{
            background:#f8fafc;
            border-bottom:1px solid var(--border);
        }
        .form-control, .form-select{ border-radius: 12px; }
        .btn{ border-radius: 12px; }
        .muted{ color: var(--muted); }
        .select2-container .select2-selection--single{
            height: 42px;
            border-radius: 12px;
            border: 1px solid #dee2e6;
        }
        .select2-container--default .select2-selection--single .select2-selection__rendered{
            line-height: 42px;
            padding-left: 12px;
        }
        .select2-container--default .select2-selection--single .select2-selection__arrow{
            height: 42px;
            right: 10px;
        }
        .field-hint{ font-size: .85rem; color: var(--muted); }
    </style>
</head>
<body>

<main class="container py-4">
    <div class="page-wrap">
        <div class="page-header p-3 p-md-4 mb-3 shadow-sm">
            <div class="d-flex align-items-center gap-3">
                <div class="icon-pill"><i class="fa-solid fa-user-pen"></i></div>
                <div class="flex-grow-1">
                    <h3 class="mb-0 fw-bold text-primary">Edit Customer</h3>
                    <div class="muted">Update PPPoE username and Cignal Play subscription details.</div>
                </div>

            </div>
        </div>

        <?php if ($notification): ?>
            <div class="alert alert-success border-0 shadow-sm alert-dismissible fade show" role="alert">
                <?= htmlspecialchars($notification) ?>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        <?php endif; ?>

        <?php if ($error): ?>
            <div class="alert alert-danger border-0 shadow-sm alert-dismissible fade show" role="alert">
                <?= htmlspecialchars($error) ?>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        <?php endif; ?>

        <form method="POST" class="card card-form shadow-sm">
            <input type="hidden" name="id" value="<?= htmlspecialchars($customer_id) ?>">

            <div class="card-header py-3 px-3 px-md-4">
                <div class="d-flex flex-wrap gap-2 justify-content-between align-items-center">
                    <div>
                        <div class="fw-semibold">Customer ID: #<?= htmlspecialchars($customer_id) ?></div>
                        <div class="field-hint">Make sure details are correct before saving.</div>
                    </div>
                    <div class="d-flex gap-2">
                        <a href="user_cignal_logs.php?customer_id=<?= htmlspecialchars($customer_id) ?>" class="btn btn-outline-dark btn-sm">
                            <i class="fa-solid fa-receipt me-1"></i> Logs
                        </a>
                        <a href="cignalplay_form.php?customer_id=<?= htmlspecialchars($customer_id) ?>" class="btn btn-outline-success btn-sm">
                            <i class="fa-solid fa-money-bill me-1"></i> Payment
                        </a>
                    </div>
                </div>
            </div>

            <div class="card-body p-3 p-md-4">
                <div class="row g-3">
                    <div class="col-12">
                        <label for="username" class="form-label fw-semibold">
                            Username <span class="text-primary">(Mikrotik PPPoE Integrate)</span>
                        </label>
                        <select id="username" name="username" class="form-select select2">
                            <option value="">-- None / Blank --</option>
                            <?php foreach ($available_usernames as $uname): ?>
                                <option value="<?= htmlspecialchars($uname) ?>" <?= (($uname ?? '') == ($old_data['username'] ?? '')) ? 'selected' : '' ?>>
                                    <?= htmlspecialchars($uname) ?>
                                </option>
                            <?php endforeach; ?>
                        </select>
                        <div class="field-hint mt-1">Select a PPPoE username or leave blank.</div>
                    </div>

                    <div class="col-12 col-md-6">
                        <label for="cignalplay_no" class="form-label fw-semibold">
                            <span class="badge bg-warning text-dark me-1">Cignal Play</span> Subscriber No.
                        </label>
                        <input type="text" id="cignalplay_no" name="cignalplay_no"
                               class="form-control border-warning bg-warning-subtle"
                               value="<?= htmlspecialchars($old_data['cignalplay_no'] ?? '') ?>">
                        <div class="field-hint mt-1">Enter Cignal Play Subscriber number if applicable.</div>
                    </div>

                    <div class="col-12 col-md-6">
                        <label for="cignalplay_date" class="form-label fw-semibold">
                            <span class="badge bg-info text-dark me-1">Cignal Play</span> Subscription Date & Time
                        </label>
                        <input type="datetime-local" id="cignalplay_date" name="cignalplay_date"
                               class="form-control border-info bg-info-subtle"
                               value="<?= htmlspecialchars($cignalplay_date_value) ?>">
                        <div class="field-hint mt-1">Now includes time (hour/minute).</div>
                    </div>

                    <div class="col-12">
                        <label for="cignalplay_adjustedby" class="form-label fw-semibold">
                            <span class="badge bg-success text-light me-1">Admin</span> Adjusted By
                        </label>
                        <input type="text" id="cignalplay_adjustedby" class="form-control border-success bg-success-subtle"
                               value="<?= htmlspecialchars($display_adjustedby) ?>" readonly>
                        <div class="field-hint mt-1">Shows the last admin who adjusted this record.</div>
                    </div>
                </div>
            </div>

            <div class="card-footer bg-white border-0 p-3 p-md-4 pt-0">
                <div class="d-flex flex-column flex-sm-row gap-2 justify-content-between">
                    <a href="add_on_payments.php" class="btn btn-outline-secondary">
                        <i class="fa-solid fa-arrow-left me-1"></i> Back
                    </a>
                    <button type="submit" class="btn btn-primary">
                        <i class="fa-solid fa-floppy-disk me-1"></i> Update
                    </button>
                </div>
            </div>
        </form>
    </div>
</main>

<?php include 'footer.php'; ?>

<script>
$(document).ready(function() {
    $('#username').select2({
        placeholder: "-- None / Blank --",
        allowClear: true,
        width: '100%'
    });
});
</script>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
