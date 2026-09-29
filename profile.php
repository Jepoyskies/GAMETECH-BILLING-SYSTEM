<?php
declare(strict_types=1);

include 'header.php';
include 'database.php'; // Ensure $pdo is available

if (empty($_SESSION['admin_logged_in'])) {
    header('Location: login.php');
    exit;
}

$admin_id = $_SESSION['admin_id'] ?? 0;
$admin_username = $_SESSION['admin_username'] ?? 'Unknown';

// Fetch admin data
$stmt = $pdo->prepare("SELECT full_name, email, role, status FROM admins WHERE id = ?");
$stmt->execute([$admin_id]);
$admin = $stmt->fetch(PDO::FETCH_ASSOC);

$full_name = $admin['full_name'] ?? 'Unknown';
$email     = $admin['email'] ?? 'Unknown';
$role      = $admin['role'] ?? 'Unknown';
$status    = $admin['status'] ?? 'Unknown';
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Admin Profile</title>
<style>
:root {
  --bg: #f5f7fb;
  --card: #ffffff;
  --text: #1f2937;
  --muted: #6b7280;
  --shadow: 0 6px 16px rgba(0,0,0,.08);
  --radius: 12px;
}
html, body { height: 100%; }
body {
  margin: 0;
  background: var(--bg);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  color: var(--text);
}
.container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
  padding: 40px 16px;
}
.card {
  width: 100%;
  max-width: 680px;
  background: var(--card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 20px 20px 18px;
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 20px;
  position: relative;
}
.avatar {
  width: 110px; height: 110px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 40px;
  color: #374151;
  background: #eef2f7;
  box-shadow: 0 6px 16px rgba(0,0,0,.08);
  user-select: none;
}
.field {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 8px 12px;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}
.field:last-child { border-bottom: none; }
.label {
  font-size: 0.92rem;
  color: var(--muted);
  font-weight: 600;
}
.value { font-size: 1.02rem; font-weight: 700; }
.actions {
  margin-top: 10px;
  display: flex; gap: 12px; align-items: center;
}
.btn {
  padding: 10px 16px;
  border-radius: 8px;
  border: none;
  font-weight: 700;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #e5e7eb;
  color: #111827;
}
.btn.primary {
  background: #1f2937;
  color: #fff;
}
@media (max-width: 720px) {
  .card {
    grid-template-columns: 1fr;
    padding: 16px;
  }
  .avatar { width: 84px; height: 84px; font-size: 34px; }
  .field { grid-template-columns: 130px 1fr; }
}
</style>
</head>
<body>
<div class="container">
  <div class="card" aria-label="Admin profile details">
    <div class="avatar" aria-label="Admin initials">
      <?= htmlspecialchars(substr($full_name, 0, 1)) ?>
    </div>

    <div class="info">
      <div class="field">
        <div class="label">Full Name</div>
        <div class="value"><?= htmlspecialchars($full_name) ?></div>
      </div>
      <div class="field">
        <div class="label">Email</div>
        <div class="value"><?= htmlspecialchars($email) ?></div>
      </div>
      <div class="field">
        <div class="label">Role</div>
        <div class="value"><?= htmlspecialchars($role) ?></div>
      </div>
      <div class="field">
        <div class="label">Status</div>
        <div class="value"><?= htmlspecialchars($status) ?></div>
      </div>
      <div class="field">
        <div class="label">User ID / Username</div>
        <div class="value"><?= htmlspecialchars($admin_username) ?> (ID: <?= htmlspecialchars((string)$admin_id) ?>)</div>
      </div>
      <div class="actions" aria-label="Actions">
        <a href="edit_password.php" class="btn secondary" role="button">Change Password</a>
      </div>
    </div>
  </div>
</div>
</body>
</html>
