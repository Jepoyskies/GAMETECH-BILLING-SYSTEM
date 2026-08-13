<?php
// Start output buffering to avoid "headers already sent" issues
ob_start();

require 'header.php';
require 'database.php';

$message = '';
$errors = [];

// Detect whether password_hash column exists (optional guard)
$passwordHashColumnExists = false;
try {
    $check = $conn->prepare("SHOW COLUMNS FROM agents LIKE 'password_hash'");
    $check->execute();
    $passwordHashColumnExists = $check->rowCount() > 0;
} catch (PDOException $e) {
    // If this fails, we'll proceed as if the column doesn't exist.
    $passwordHashColumnExists = false;
}

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $name     = isset($_POST['name']) ? trim($_POST['name']) : '';
    $email    = isset($_POST['email']) ? trim($_POST['email']) : '';
    $phone    = isset($_POST['phone']) ? trim($_POST['phone']) : '';
    $password = isset($_POST['password']) ? $_POST['password'] : '';

    // Basic validation
    if ($name === '') $errors[] = 'Name is required.';
    if ($email === '') $errors[] = 'Email is required.';

    // If column exists, require a password
    if ($passwordHashColumnExists && trim($password) === '') {
        $errors[] = 'Password is required.';
    }

    if (empty($errors)) {
        try {
            if ($passwordHashColumnExists) {
                // Include password_hash in the insert
                $passwordHashValue = password_hash($password, PASSWORD_DEFAULT);

                $sql = "INSERT INTO agents (name, email, phone, password_hash)
                        VALUES (:name, :email, :phone, :password_hash)";
                $stmt = $conn->prepare($sql);
                $stmt->bindParam(':name', $name, PDO::PARAM_STR);
                $stmt->bindParam(':email', $email, PDO::PARAM_STR);
                $stmt->bindParam(':phone', $phone, PDO::PARAM_STR);
                $stmt->bindParam(':password_hash', $passwordHashValue, PDO::PARAM_STR);
            } else {
                // Exclude password_hash
                $sql = "INSERT INTO agents (name, email, phone)
                        VALUES (:name, :email, :phone)";
                $stmt = $conn->prepare($sql);
                $stmt->bindParam(':name', $name, PDO::PARAM_STR);
                $stmt->bindParam(':email', $email, PDO::PARAM_STR);
                $stmt->bindParam(':phone', $phone, PDO::PARAM_STR);
            }

            if ($stmt->execute()) {
                $message = 'Agent added successfully.';
                // Redirect to the list with a success message
                header('Location: agents.php?msg=' . urlencode($message));
                exit;
            } else {
                $errors[] = 'Failed to add agent.';
            }
        } catch (PDOException $e) {
            $errors[] = 'Database error: ' . $e->getMessage();
        }
    }
}
?>

<main class="container py-4">
    <h2 class="mb-4">Add Agent</h2>

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
        <div class="toast align-items-center text-white bg-success border-0 position-fixed bottom-0 end-0 p-3" role="alert" aria-live="assertive" aria-atomic="true" id="liveToast">
            <div class="d-flex">
                <div class="toast-body">
                    <?= htmlspecialchars($message, ENT_QUOTES, 'UTF-8') ?>
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    <?php endif; ?>

    <!-- Card-style form -->
    <div class="card border-primary mb-4">
        <div class="card-header bg-primary text-white">
            <strong>New Agent Details</strong>
        </div>
        <div class="card-body">
            <form method="post" action="" class="needs-validation" novalidate>
                <div class="row g-3">
                    <div class="col-md-6">
                        <label class="form-label" for="name">Name</label>
                        <input id="name" name="name" class="form-control" type="text" required
                               value="<?= isset($_POST['name']) ? htmlspecialchars($_POST['name'], ENT_QUOTES, 'UTF-8') : '' ?>">
                        <div class="invalid-feedback">Please provide the agent's name.</div>
                    </div>

                    <div class="col-md-6">
                        <label class="form-label" for="email">Email</label>
                        <input id="email" name="email" class="form-control" type="email" required
                               value="<?= isset($_POST['email']) ? htmlspecialchars($_POST['email'], ENT_QUOTES, 'UTF-8') : '' ?>">
                        <div class="invalid-feedback">Please provide a valid email address.</div>
                    </div>

                    <div class="col-md-6">
                        <label class="form-label" for="phone">Phone</label>
                        <input id="phone" name="phone" class="form-control" type="text"
                               value="<?= isset($_POST['phone']) ? htmlspecialchars($_POST['phone'], ENT_QUOTES, 'UTF-8') : '' ?>">
                    </div>

                    <?php if ($passwordHashColumnExists): ?>
                    <div class="col-md-6">
                        <label class="form-label" for="password">Password</label>
                        <input id="password" name="password" class="form-control" type="password" required
                               placeholder="Enter a password">
                    </div>
                    <?php endif; ?>
                </div>

                <div class="mt-4 d-flex justify-content-end">
                    <a href="agents.php" class="btn btn-outline-secondary me-2">Cancel</a>
                    <button type="submit" class="btn btn-primary">Add Agent</button>
                </div>
            </form>
        </div>
    </div>
</main>

<script>
// Optional Bootstrap validation
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

// Show toast notification if message exists
document.addEventListener('DOMContentLoaded', function () {
  var toastElement = document.getElementById('liveToast');
  if (toastElement) {
    var toast = new bootstrap.Toast(toastElement);
    toast.show();
  }
});
</script>

<?php
ob_end_flush();
include 'footer.php';
?>
