<?php
// Database connection settings
$host = 'localhost';
$db   = 'gametech';
$user = 'root';
$pass = '';
$charset = 'utf8mb4';

// Create PDO instance
$dsn = "mysql:host=$host;dbname=$db;charset=$charset";
$options = [
    PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    PDO::ATTR_EMULATE_PREPARES   => false,
];

$notification = '';
$notifType = '';

try {
    $pdo = new PDO($dsn, $user, $pass, $options);
} catch (\PDOException $e) {
    die("Database connection failed: " . $e->getMessage());
}

// Handle form submission
if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $username  = trim($_POST['username'] ?? '');
    $full_name = trim($_POST['full_name'] ?? '');
    $email     = trim($_POST['email'] ?? '');
    $role      = $_POST['role'] ?? 'Admin';
    $status    = $_POST['status'] ?? 'Active';
    $password  = $_POST['password'] ?? '';

    // Basic validation
    if (empty($username) || empty($full_name) || empty($email) || empty($password)) {
        $notification = "All fields are required.";
        $notifType = "danger";
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $notification = "Invalid email address.";
        $notifType = "danger";
    } else {
        // Hash the password using bcrypt
        $passwordHash = password_hash($password, PASSWORD_BCRYPT);

        // Insert into admin table
        $stmt = $pdo->prepare("INSERT INTO admins (username, full_name, email, role, status, password) VALUES (?, ?, ?, ?, ?, ?)");
        try {
            $stmt->execute([$username, $full_name, $email, $role, $status, $passwordHash]);
            $notification = "Admin user added successfully!";
            $notifType = "success";
        } catch (\PDOException $e) {
            if ($e->getCode() == 23000) { // Duplicate entry
                $notification = "Username or email already exists.";
                $notifType = "warning";
            } else {
                $notification = "Error: " . $e->getMessage();
                $notifType = "danger";
            }
        }
    }
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <title>Add Admin</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- Bootstrap 5 CDN -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        html, body {height: 100%;}
        body {min-height: 100vh; background: #f8f9fa;}
        .main-center-container {
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
        }
        .notification-toast {
            position: fixed;
            bottom: 32px;
            right: 32px;
            z-index: 1080;
            min-width: 280px; opacity: 0.98; transition: opacity 0.5s;
        }
        @media (max-width: 575.98px) {
            .main-center-container {padding: 1rem;}
            .notification-toast {right: 10px; left: 10px; bottom: 10px;}
        }
    </style>
</head>
<body>
    <div class="main-center-container">
        <div class="card shadow-sm w-100" style="max-width: 400px;">
            <div class="card-body">
                <h3 class="card-title text-center mb-4">
                    <i class="bi bi-person-plus"></i> Add Admin User
                </h3>
                <form method="POST" action="" autocomplete="off">
                    <div class="mb-3">
                        <label for="username" class="form-label">Username *</label>
                        <input type="text" name="username" id="username" class="form-control" required autofocus value="<?= htmlspecialchars($_POST['username'] ?? '') ?>">
                    </div>
                    <div class="mb-3">
                        <label for="full_name" class="form-label">Full Name *</label>
                        <input type="text" name="full_name" id="full_name" class="form-control" required value="<?= htmlspecialchars($_POST['full_name'] ?? '') ?>">
                    </div>
                    <div class="mb-3">
                        <label for="email" class="form-label">Email *</label>
                        <input type="email" name="email" id="email" class="form-control" required value="<?= htmlspecialchars($_POST['email'] ?? '') ?>">
                    </div>
                    <div class="mb-3">
                        <label for="role" class="form-label">Role *</label>
                        <select name="role" id="role" class="form-select" required>
                            <?php
                            $roles = ['Admin', 'Editor', 'Viewer'];
                            $selectedRole = $_POST['role'] ?? 'Admin';
                            foreach ($roles as $r) {
                                echo "<option value=\"$r\"" . ($selectedRole == $r ? ' selected' : '') . ">$r</option>";
                            }
                            ?>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="status" class="form-label">Status *</label>
                        <select name="status" id="status" class="form-select" required>
                            <option value="Active" <?= (($_POST['status'] ?? 'Active') == 'Active' ? 'selected' : '') ?>>Active</option>
                            <option value="Inactive" <?= (($_POST['status'] ?? '') == 'Inactive' ? 'selected' : '') ?>>Inactive</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="password" class="form-label">Password *</label>
                        <input type="password" name="password" id="password" class="form-control" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Add Admin</button>
                </form>
            </div>
        </div>
    </div>

    <?php if (!empty($notification)): ?>
        <div class="notification-toast toast align-items-center text-bg-<?= $notifType ?> border-0 show" id="notifToast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <?= htmlspecialchars($notification) ?>
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    <?php endif; ?>

    <!-- Bootstrap JS (for Toast) -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    // Auto-hide toast after 4 seconds
    window.addEventListener('DOMContentLoaded', function() {
        var notif = document.getElementById('notifToast');
        if (notif) {
            var toast = new bootstrap.Toast(notif, { delay: 4000 });
            toast.show();
        }
    });
    </script>
    <!-- Bootstrap Icons CDN (for the icon) -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
</body>
</html>
