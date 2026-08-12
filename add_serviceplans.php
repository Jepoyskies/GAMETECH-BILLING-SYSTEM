<?php
require 'database.php';

$error = '';
$success = false;

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $plan_name    = trim($_POST['name']);
    $speed_up      = trim($_POST['speed_up']);
    $speed_down    = trim($_POST['speed_down']);
    $price         = trim($_POST['price']);
    $validity_days = trim($_POST['validity_days']);
    $description   = trim($_POST['description']);

    // Minimal validation
    if ($plan_name === '' || $speed_up === '' || $speed_down === '' || $price === '' || $validity_days === '') {
        $error = 'Please fill in all required fields.';
    } else {
        $sql = "INSERT INTO service_plans 
                (plan_name, speed_up, speed_down, price, validity_days, description)
                VALUES (:plan_name, :speed_up, :speed_down, :price, :validity_days, :description)";
        $stmt = $pdo->prepare($sql);
        $result = $stmt->execute([
            ':plan_name'    => $plan_name,
            ':speed_up'     => $speed_up,
            ':speed_down'   => $speed_down,
            ':price'        => $price,
            ':validity_days'=> $validity_days,
            ':description'  => $description
        ]);
        if ($result) {
            $success = true;
            // Clear fields after successful add
            $plan = [
                'plan_name'     => '',
                'speed_up'      => '',
                'speed_down'    => '',
                'price'         => '',
                'validity_days' => '',
                'description'   => ''
            ];
        } else {
            $error = 'Failed to add service plan.';
            // Repopulate fields if failed
            $plan = [
                'plan_name'     => $plan_name,
                'speed_up'      => $speed_up,
                'speed_down'    => $speed_down,
                'price'         => $price,
                'validity_days' => $validity_days,
                'description'   => $description
            ];
        }
    }
} else {
    // Default blank form
    $plan = [
        'plan_name'     => '',
        'speed_up'      => '',
        'speed_down'    => '',
        'price'         => '',
        'validity_days' => '',
        'description'   => ''
    ];
}

include 'header.php';
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Add Service Plan</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- Bootstrap 5 CSS CDN -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
<!-- Bootstrap 5 Modal for Success Notification -->
<div class="modal fade" id="successModal" tabindex="-1" aria-labelledby="successModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content border-success">
      <div class="modal-header bg-success text-white">
        <h5 class="modal-title" id="successModalLabel">Success!</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body text-center">
        Service plan was added successfully.
      </div>
      <div class="modal-footer">
        <a href="serviceplans.php" class="btn btn-success">Back to Service Plans</a>
        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Add Another</button>
      </div>
    </div>
  </div>
</div>

<main class="container py-4">
    <h2 class="mb-4 text-center">Add Service Plan</h2>
    <div class="row justify-content-center">
        <div class="col-12 col-md-8 col-lg-6">
            <div class="card shadow-sm p-4">
                <?php if ($error): ?>
                    <div class="alert alert-danger"><?php echo htmlspecialchars($error); ?></div>
                <?php endif; ?>
                <form method="post" autocomplete="off">
                    <div class="mb-3">
                        <label class="form-label">Name <span class="text-danger">*</span></label>
                        <input type="text" name="name" class="form-control" required value="<?php echo htmlspecialchars($plan['plan_name']); ?>">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Upload Speed <span class="text-danger">*</span></label>
                        <input type="text" name="speed_up" class="form-control" required value="<?php echo htmlspecialchars($plan['speed_up']); ?>">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Download Speed <span class="text-danger">*</span></label>
                        <input type="text" name="speed_down" class="form-control" required value="<?php echo htmlspecialchars($plan['speed_down']); ?>">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Price (₱) <span class="text-danger">*</span></label>
                        <input type="number" name="price" class="form-control" required min="0" step="0.01" value="<?php echo htmlspecialchars($plan['price']); ?>">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Validity Days <span class="text-danger">*</span></label>
                        <input type="number" name="validity_days" class="form-control" required min="1" value="<?php echo htmlspecialchars($plan['validity_days']); ?>">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Description</label>
                        <textarea name="description" class="form-control" rows="2"><?php echo htmlspecialchars($plan['description']); ?></textarea>
                    </div>
                    <div class="d-flex justify-content-between">
                        <a href="serviceplans.php" class="btn btn-secondary">Cancel</a>
                        <button type="submit" class="btn btn-primary">Add Plan</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</main>

<?php if ($success): ?>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
    // Show the Bootstrap modal after successful update
    document.addEventListener("DOMContentLoaded", function() {
        var successModal = new bootstrap.Modal(document.getElementById('successModal'));
        successModal.show();
    });
</script>
<?php endif; ?>

<?php include 'footer.php'; ?>
</body>
</html>
