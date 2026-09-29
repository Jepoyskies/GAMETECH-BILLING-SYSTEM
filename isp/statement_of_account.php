<?php
require 'database.php';

if (!isset($_GET['username']) || trim($_GET['username']) === '') {
    die("Username is required.");
}

$username = $_GET['username'];

// Optional date filter
$from = $_GET['from'] ?? null;
$to   = $_GET['to'] ?? null;

$query = "SELECT * FROM payments WHERE username = ?";
$params = [$username];

if ($from && $to) {
    $query .= " AND DATE(paid_at) BETWEEN ? AND ?";
    $params[] = $from;
    $params[] = $to;
}

$query .= " ORDER BY paid_at DESC";

$stmt = $pdo->prepare($query);
$stmt->execute($params);
$payments = $stmt->fetchAll(PDO::FETCH_ASSOC);

// Compute total
$total = 0;
foreach ($payments as $p) {
    $total += $p['amount'];
}
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Statement of Account</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            font-size: 12px;
            color: #000;
        }
        .container {
            width: 800px;
            margin: auto;
        }
        .header {
            text-align: center;
        }
        .header img {
            max-height: 70px;
        }
        .title {
            text-align: center;
            font-size: 18px;
            margin: 10px 0;
            font-weight: bold;
        }
        .info {
            margin-bottom: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        table th, table td {
            border: 1px solid #000;
            padding: 6px;
            text-align: left;
        }
        table th {
            background: #f0f0f0;
        }
        .total {
            text-align: right;
            font-weight: bold;
            margin-top: 10px;
        }
        .footer {
            margin-top: 20px;
            font-size: 11px;
            text-align: center;
        }
        @media print {
            .no-print {
                display: none;
            }
        }
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <img src="assets/images/logo_black.png">
        <div><strong>GameTech UnliFiber</strong></div>
        <div>043 St. Therese, Patag, CDO</div>
        <div>Phone: 0936-274-2712</div>
    </div>

    <div class="title">STATEMENT OF ACCOUNT</div>

    <div class="info">
        <strong>Username:</strong> <?php echo htmlspecialchars($username); ?><br>
        <strong>Date Generated:</strong> <?php echo date('Y-m-d H:i'); ?><br>
        <?php if ($from && $to): ?>
            <strong>Period:</strong> <?php echo $from . " to " . $to; ?>
        <?php endif; ?>
    </div>

    <table>
        <thead>
            <tr>
                <th>Date Paid</th>
                <th>Plan</th>
                <th>Days</th>
                <th>Amount</th>
                <th>Processed By</th>
            </tr>
        </thead>
        <tbody>
            <?php if ($payments): ?>
                <?php foreach ($payments as $p): ?>
                    <tr>
                        <td><?php echo $p['paid_at']; ?></td>
                        <td><?php echo htmlspecialchars($p['plan_name']); ?></td>
                        <td><?php echo $p['days']; ?></td>
                        <td>₱<?php echo number_format($p['amount'], 2); ?></td>
                        <td><?php echo htmlspecialchars($p['adjusted_by']); ?></td>
                    </tr>
                <?php endforeach; ?>
            <?php else: ?>
                <tr>
                    <td colspan="5">No records found.</td>
                </tr>
            <?php endif; ?>
        </tbody>
    </table>

    <div class="total">
        TOTAL PAID: ₱<?php echo number_format($total, 2); ?>
    </div>

    <div class="footer">
        This is a system-generated Statement of Account.
    </div>

    <div class="no-print" style="text-align:center;margin-top:20px;">
        <button onclick="window.print()">Download / Print</button>
    </div>
</div>

<script>
    // auto open print dialog
    window.onload = function() {
        window.print();
    }
</script>

</body>
</html>
