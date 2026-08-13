<?php
include 'header.php';
include 'database.php';

$agent = null;
$customers = [];
$updateMessage = '';
$loggedInUser = $_SESSION['username'] ?? 'unknown';

// Handle referral status update
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_referral']) && isset($_POST['cust_username'])) {
    $username = $_POST['cust_username'];
    $newValue = $_POST['referral_value'] ?? '0';
    $newValueInt = ($newValue === '1' || strtolower($newValue) === 'true' || $newValue === 'paid') ? 1 : 0;
    $adjustedBy = $loggedInUser; // Always record who made the adjustment

    $upd = $conn->prepare("UPDATE customers SET referral_received = :val, adjusted_by_referral = :adjustedBy WHERE username = :uname");
    $upd->bindParam(':val', $newValueInt, PDO::PARAM_INT);
    $upd->bindParam(':uname', $username, PDO::PARAM_STR);
    $upd->bindParam(':adjustedBy', $adjustedBy, PDO::PARAM_STR);
    if ($upd->execute()) {
        $updateMessage = 'Referral status updated for ' . htmlspecialchars($username, ENT_QUOTES, 'UTF-8') . '.';
    } else {
        $updateMessage = 'Failed to update referral status for ' . htmlspecialchars($username, ENT_QUOTES, 'UTF-8') . '.';
    }
}

// Fetch agent and customers
if (isset($_GET['id'])) {
    $id = (int) $_GET['id'];

    $stmt = $conn->prepare("SELECT id, name, email, phone FROM agents WHERE id = :id");
    $stmt->bindParam(':id', $id, PDO::PARAM_INT);
    $stmt->execute();
    $agent = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($agent && isset($agent['name']) && $agent['name'] !== '') {
        $customerStmt = $conn->prepare("
            SELECT 
                username, email, account_type, plan_name, full_name, referral_received, adjusted_by_referral, created_at
            FROM customers
            WHERE agent = :agentName
        ");
        $customerStmt->bindParam(':agentName', $agent['name'], PDO::PARAM_STR);
        $customerStmt->execute();
        $customers = $customerStmt->fetchAll(PDO::FETCH_ASSOC);
    } else {
        $agent = null;
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Details</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.min.css">
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/5.3.0/css/bootstrap.min.css">
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
    <style>
        @media (max-width: 768px) {
            .table-responsive {
                display: none;
            }
            .card-view {
                display: block;
            }
        }
        @media (min-width: 769px) {
            .card-view {
                display: none;
            }
        }
        #customersTable {
            font-size: 0.875rem;
        }
        #customersTable td, #customersTable th {
            padding: 0.5rem;
        }
    </style>
</head>
<body>
<main class="container py-4">
    <?php if ($agent): ?>
        <div class="card mb-4">
            <div class="card-body">
                <h2 class="card-title mb-0"><?php echo htmlspecialchars($agent['name'], ENT_QUOTES, 'UTF-8'); ?></h2>
                <ul class="list-unstyled mb-0 mt-2">
                    <li><strong>Email:</strong> <?php echo htmlspecialchars($agent['email'], ENT_QUOTES, 'UTF-8'); ?></li>
                    <li><strong>Phone:</strong> <?php echo htmlspecialchars($agent['phone'], ENT_QUOTES, 'UTF-8'); ?></li>
                </ul>
            </div>
        </div>

        <?php if ($updateMessage): ?>
            <div class="alert alert-info"><?php echo htmlspecialchars($updateMessage, ENT_QUOTES, 'UTF-8'); ?></div>
        <?php endif; ?>

        <?php if (!empty($customers)): ?>
            <h4 class="mt-2 mb-2">Customers handled by this agent</h4>

            <div class="table-responsive">
                <table id="customersTable" class="table table-bordered table-striped">
                    <thead>
                        <tr>
                            <th>Created At</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Account Type</th>
                            <th>Plan Name</th>
                            <th>Full Name</th>
                            <th>Referral</th>
                            <th>Adjusted By</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($customers as $cust): ?>
                            <?php
                                $fullName = trim(($cust['full_name'] ?? '') . ' ' . ($cust['last_name'] ?? ''));
                                $username   = $cust['username'] ?? '';
                                $createdAt  = $cust['created_at'] ?? '';
                                $email      = $cust['email'] ?? '';
                                $acctType   = $cust['account_type'] ?? '';
                                $planName   = $cust['plan_name'] ?? '';
                                $refPaid    = !empty($cust['referral_received']) && filter_var($cust['referral_received'], FILTER_VALIDATE_BOOLEAN);
                            ?>
                            <tr>
                                <td><?php echo htmlspecialchars($createdAt, ENT_QUOTES, 'UTF-8'); ?></td>
                                <td><?php echo htmlspecialchars($username, ENT_QUOTES, 'UTF-8'); ?></td>
                                <td><?php echo htmlspecialchars($email, ENT_QUOTES, 'UTF-8'); ?></td>
                                <td><?php echo htmlspecialchars($acctType, ENT_QUOTES, 'UTF-8'); ?></td>
                                <td><?php echo htmlspecialchars($planName, ENT_QUOTES, 'UTF-8'); ?></td>
                                <td><?php echo htmlspecialchars($fullName, ENT_QUOTES, 'UTF-8'); ?></td>
                                <td>
                                    <?php if ($refPaid): ?>
                                        <span class="badge bg-success" aria-label="Referral paid">✓ Paid</span>
                                    <?php else: ?>
                                        <span class="badge bg-secondary" aria-label="Referral not paid">Pending</span>
                                    <?php endif; ?>
                                </td>
                                <td><?php echo htmlspecialchars($cust['adjusted_by_referral'] ?? 'N/A', ENT_QUOTES, 'UTF-8'); ?></td>
                                <td>
                                    <form method="post" style="display:inline;">
                                        <input type="hidden" name="cust_username" value="<?php echo htmlspecialchars($username, ENT_QUOTES, 'UTF-8'); ?>">
                                        <select name="referral_value" class="form-select" onchange="this.form.submit()">
                                            <option value="0" <?php echo $refPaid ? '' : 'selected'; ?>>Pending</option>
                                            <option value="1" <?php echo $refPaid ? 'selected' : ''; ?>>Paid</option>
                                        </select>
                                        <input type="hidden" name="update_referral" value="1">
                                    </form>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>

            <!-- Card View for Mobile -->
            <div class="card-view">
                <?php foreach ($customers as $cust): ?>
                    <?php
                        $fullName = trim(($cust['full_name'] ?? '') . ' ' . ($cust['last_name'] ?? ''));
                        $username   = $cust['username'] ?? '';
                        $createdAt  = $cust['created_at'] ?? '';
                        $email      = $cust['email'] ?? '';
                        $acctType   = $cust['account_type'] ?? '';
                        $planName   = $cust['plan_name'] ?? '';
                        $refPaid    = !empty($cust['referral_received']) && filter_var($cust['referral_received'], FILTER_VALIDATE_BOOLEAN);
                    ?>
                    <div class="card mb-3">
                        <div class="card-body">
                            <p class="card-text"><strong>Created At:</strong> <?php echo htmlspecialchars($createdAt, ENT_QUOTES, 'UTF-8'); ?></p>
                            <h5 class="card-title"><strong>Username:</strong> <?php echo htmlspecialchars($username, ENT_QUOTES, 'UTF-8'); ?></h5>
                            <p class="card-text"><strong>Email:</strong> <?php echo htmlspecialchars($email, ENT_QUOTES, 'UTF-8'); ?></p>
                            <p class="card-text"><strong>Account Type:</strong> <?php echo htmlspecialchars($acctType, ENT_QUOTES, 'UTF-8'); ?></p>
                            <p class="card-text"><strong>Plan Name:</strong> <?php echo htmlspecialchars($planName, ENT_QUOTES, 'UTF-8'); ?></p>
                            <p class="card-text"><strong>Full Name:</strong> <?php echo htmlspecialchars($fullName, ENT_QUOTES, 'UTF-8'); ?></p>
                            <p class="card-text"><strong>Referral:</strong> 
                                <?php if ($refPaid): ?>
                                    <span class="badge bg-success">✓ Paid</span>
                                <?php else: ?>
                                    <span class="badge bg-secondary">Pending</span>
                                <?php endif; ?>
                            </p>
                            <p class="card-text"><strong>Adjusted By:</strong> <?php echo htmlspecialchars($cust['adjusted_by_referral'] ?? 'N/A', ENT_QUOTES, 'UTF-8'); ?></p>
                            <form method="post">
                                <input type="hidden" name="cust_username" value="<?php echo htmlspecialchars($username, ENT_QUOTES, 'UTF-8'); ?>">
                                <div class="mb-2">
                                    <select name="referral_value" class="form-select" onchange="this.form.submit()">
                                        <option value="0" <?php echo $refPaid ? '' : 'selected'; ?>>Pending</option>
                                        <option value="1" <?php echo $refPaid ? 'selected' : ''; ?>>Paid</option>
                                    </select>
                                </div>
                                <input type="hidden" name="update_referral" value="1">
                            </form>
                        </div>
                    </div>
                <?php endforeach; ?>
            </div>

        <?php else: ?>
            <p class="text-muted mt-2">No customers found for this agent.</p>
        <?php endif; ?>
    <?php else: ?>
        <div class="alert alert-warning">Agent not found.</div>
    <?php endif; ?>
</main>

<script>
$(document).ready(function() {
    $('#customersTable').DataTable({
        "paging": true,
        "searching": true,
        "ordering": true,
        "info": true
    });
});
</script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/5.3.0/js/bootstrap.bundle.min.js"></script>
</body>
</html>
<?php include 'footer.php'; ?>
