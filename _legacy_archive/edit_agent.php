<?php
require 'header.php';
require 'database.php';

$agent = null;
$errors = [];
$message = '';

if (!isset($_GET['id'])) {
    // No ID provided
    header('Location: agents.php');
    exit;
}

$agentId = (int) $_GET['id'];

// Load existing agent
$stmt = $conn->prepare("SELECT id, name, email, phone FROM agents WHERE id = :id");
$stmt->bindParam(':id', $agentId, PDO::PARAM_INT);
$stmt->execute();
$agent = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$agent) {
    header('Location: agents.php');
    exit;
}

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $name  = isset($_POST['name']) ? trim($_POST['name']) : '';
    $email = isset($_POST['email']) ? trim($_POST['email']) : '';
    $phone = isset($_POST['phone']) ? trim($_POST['phone']) : '';

    if ($name === '') $errors[] = 'Name is required.';
    if ($email === '') $errors[] = 'Email is required.';

    if (empty($errors)) {
        try {
            $upd = $conn->prepare("UPDATE agents SET name = :name, email = :email, phone = :phone WHERE id = :id");
            $upd->bindParam(':name', $name, PDO::PARAM_STR);
            $upd->bindParam(':email', $email, PDO::PARAM_STR);
            $upd->bindParam(':phone', $phone, PDO::PARAM_STR);
            $upd->bindParam(':id', $agentId, PDO::PARAM_INT);

            if ($upd->execute()) {
                $message = 'Agent updated successfully.';
                // Refresh the agent data
                $stmt = $conn->prepare("SELECT id, name, email, phone FROM agents WHERE id = :id");
                $stmt->bindParam(':id', $agentId, PDO::PARAM_INT);
                $stmt->execute();
                $agent = $stmt->fetch(PDO::FETCH_ASSOC);
            } else {
                $errors[] = 'Failed to update agent.';
            }
        } catch (PDOException $e) {
            $errors[] = 'Database error: ' . $e->getMessage();
        }
    }
}
?>

<main class="container py-4">
    <h2 class="mb-4">Edit Agent</h2>

    <?php if (!empty($errors)): ?>
        <div class="alert alert-danger" role="alert">
            <ul class="mb-0">
                <?php foreach ($errors as $err): ?>
                    <li><?= htmlspecialchars($err, ENT_QUOTES, 'UTF-8') ?></li>
                <?php endforeach; ?>
            </ul>
        </div>
    <?php endif; ?>

    <?php if ($message): ?>
        <div class="alert alert-success" role="alert"><?= htmlspecialchars($message, ENT_QUOTES, 'UTF-8') ?></div>
    <?php endif; ?>

    <!-- Card-form layout -->
    <div class="card border-primary mb-4">
        <div class="card-header bg-primary text-white">
            <strong>Edit Agent Details</strong>
        </div>
        <div class="card-body">
            <form method="post" action="" class="needs-validation" novalidate>
                <div class="row g-3">
                    <div class="col-md-6">
                        <label class="form-label" for="name">Name</label>
                        <input id="name" name="name" class="form-control" type="text" required value="<?= htmlspecialchars($agent['name'], ENT_QUOTES, 'UTF-8') ?>">
                        <div class="invalid-feedback">Please provide the agent's name.</div>
                    </div>

                    <div class="col-md-6">
                        <label class="form-label" for="email">Email</label>
                        <input id="email" name="email" class="form-control" type="email" required value="<?= htmlspecialchars($agent['email'], ENT_QUOTES, 'UTF-8') ?>">
                        <div class="invalid-feedback">Please provide a valid email address.</div>
                    </div>

                    <div class="col-md-6">
                        <label class="form-label" for="phone">Phone</label>
                        <input id="phone" name="phone" class="form-control" type="text" value="<?= htmlspecialchars($agent['phone'], ENT_QUOTES, 'UTF-8') ?>">
                    </div>
                </div>

                <div class="mt-4 d-flex justify-content-end">
                    <a href="agents.php" class="btn btn-outline-secondary me-2">Cancel</a>
                    <button type="submit" class="btn btn-primary">Save Changes</button>
                </div>
            </form>
        </div>
    </div>
</main>

<script>
// Optional: Bootstrap form validation feedback
(function () {
  'use strict'
  var forms = document.querySelectorAll('.needs-validation')
  Array.prototype.slice.call(forms)
    .forEach(function (form) {
      form.addEventListener('submit', function (event) {
        if (!form.checkValidity()) {
          event.preventDefault()
          event.stopPropagation()
        }
        form.classList.add('was-validated')
      }, false)
    })
})()
</script>

<?php include 'footer.php'; ?>
