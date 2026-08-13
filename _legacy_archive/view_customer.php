<?php
include 'header.php';
require 'database.php'; // Assumes $pdo is your PDO connection

$id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
if ($id <= 0) {
    header('Location: customers.php');
    exit;
}

// Add 'agent' in the select fields
$stmt = $pdo->prepare("SELECT id, full_name, email, phone, address, status, agent, created_at FROM customers WHERE id = ?");
$stmt->execute([$id]);
$customer = $stmt->fetch(PDO::FETCH_ASSOC);

// Check if the customer is inactive
if ($customer && strtolower((string)$customer['status']) === 'inactive') {
    $customer = null;
}

// Helper function to safely output value or empty string if null
function safe($value) {
    return htmlspecialchars((string)($value ?? ''), ENT_QUOTES, 'UTF-8');
}
?>
<main class="container py-4">
    <h2 class="mb-4">Customer Details</h2>
    <?php if ($customer): ?>
        <div class="row justify-content-center">
            <div class="col-md-7 col-lg-6">
                <div class="card shadow border-0">
                    <div class="card-header bg-primary text-white d-flex align-items-center">
                        <i class="bi bi-person-circle fs-2 me-2"></i>
                        <span class="fs-5 fw-semibold">
                            <?php echo safe($customer['full_name']); ?>
                        </span>
                    </div>
                    <div class="card-body">
                        <table class="table table-borderless mb-0">
                            <tbody>
                                <tr>
                                    <th scope="row" class="w-35">Customer ID</th>
                                    <td><?php echo safe($customer['id']); ?></td>
                                </tr>
                                <tr>
                                    <th scope="row">Email</th>
                                    <td><?php echo safe($customer['email']); ?></td>
                                </tr>
                                <tr>
                                    <th scope="row">Phone</th>
                                    <td><?php echo safe($customer['phone']); ?></td>
                                </tr>
                                <tr>
                                    <th scope="row">Address</th>
                                    <td><?php echo safe($customer['address']); ?></td>
                                </tr>
                                <tr>
                                    <th scope="row">Agent</th>
                                    <td><?php echo safe($customer['agent']); ?></td>
                                </tr>
                                <tr>
                                    <th scope="row">Status</th>
                                    <td>
                                        <?php
                                        $status = strtolower((string)($customer['status'] ?? ''));
                                        switch ($status) {
                                            case 'active':
                                                $badgeClass = 'bg-success';
                                                break;
                                            case 'inactive':
                                                $badgeClass = 'bg-danger';
                                                break;
                                            case 'pending':
                                            default:
                                                $badgeClass = 'bg-secondary';
                                                break;
                                        }
                                        ?>
                                        <span class="badge <?php echo $badgeClass; ?>">
                                            <?php echo safe(ucfirst($status)); ?>
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <th scope="row">Created At</th>
                                    <td><?php echo safe($customer['created_at']); ?></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <div class="card-footer text-end bg-light">
                        <a href="customers.php" class="btn btn-outline-secondary">
                            <i class="bi bi-arrow-left"></i> Back to list
                        </a>
                    </div>
                </div>
            </div>
        </div>
    <?php else: ?>
        <div class="alert alert-warning">No details found for this customer.</div>
        <a href="customers.php" class="btn btn-outline-secondary">Back to list</a>
    <?php endif; ?>
</main>

<?php
include 'footer.php';
?>
