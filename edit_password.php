<!-- change_password.php -->
<?php
include 'header.php'; 

// Optional: Flash messaging display
if (isset($_SESSION['flash_msg'])) {
    $type = $_SESSION['flash_type'] ?? 'info';
    echo "<div style='color:" . ($type === 'success' ? 'green' : 'red') . ";margin-bottom:10px;'>" . htmlspecialchars($_SESSION['flash_msg']) . "</div>";
    unset($_SESSION['flash_msg'], $_SESSION['flash_type']);
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Change Password</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root{
            --bg: #f8f9fa;
            --card: #ffffff;
            --border: #e2e8f0;
            --text: #1f2937;
            --muted: #6b7280;
            --primary: #2563eb;
            --radius: 12px;
        }
        * {box-sizing: border-box;}
        body {
            margin: 0;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial;
            background: var(--bg);
            color: var(--text);
        }
        .form-container {
            max-width: 520px;
            margin: 40px auto;
            padding: 20px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: 0 4px 14px rgba(0,0,0,.05);
        }
        h2 {
            margin-top: 0;
            margin-bottom: 16px;
            font-size: 1.25rem;
            font-weight: 600;
        }
        form {
            display: grid;
            gap: 12px;
        }
        label {
            font-size: 0.9rem;
            color: var(--muted);
        }
        input[type="password"] {
            width: 100%;
            padding: 12px 14px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: #fff;
            font-size: 1rem;
            outline: none;
        }
        input[type="password"]:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37,99,235,.15);
        }
        button[type="submit"] {
            padding: 12px 16px;
            font-size: 1rem;
            border: none;
            border-radius: 8px;
            background: var(--primary);
            color: #fff;
            cursor: pointer;
        }
        button[type="submit"]:hover {
            background: #1d4ed8;
        }

        /* Back button container styling to align nicely on mobile */
        .card-footer {
            text-align: right;
            padding-top: 6px;
        }
        .btn-outline-secondary {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 12px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            text-decoration: none;
            color: #374151;
            background: #fff;
        }

        /* Responsive tweaks for very small screens */
        @media (max-width: 420px) {
            .form-container {
                margin: 12px;
                padding: 16px;
                border-radius: 10px;
            }
            h2 { font-size: 1.1rem; }
        }
    </style>
</head>
<body>
    <div class="form-container">
        <h2>Change Password</h2>
        <form method="POST" action="change_password.php" autocomplete="off">
            <div>
                <label for="current_password">Current Password</label>
                <input type="password" name="current_password" id="current_password" required autocomplete="current-password">
            </div>

            <div>
                <label for="new_password">New Password</label>
                <input type="password" name="new_password" id="new_password" required minlength="6" autocomplete="new-password">
            </div>

            <div>
                <label for="confirm_new_password">Confirm New Password</label>
                <input type="password" name="confirm_new_password" id="confirm_new_password" required minlength="6" autocomplete="new-password">
            </div>

            <button type="submit">Change Password</button>

            <div class="card-footer text-end bg-light" style="margin-top:14px;">
                <a href="settings.php" class="btn-outline-secondary" aria-label="Back to list">
                    <span aria-hidden="true">&larr;</span> Back to list
                </a>
            </div>
        </form>
    </div>
</body>
</html>
