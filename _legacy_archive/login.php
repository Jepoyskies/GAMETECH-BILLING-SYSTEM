<?php
declare(strict_types=1);

require_once 'database.php';
require_once 'logindatabase.php';

session_start([
    'cookie_httponly' => true,
    'cookie_secure'   => isset($_SERVER['HTTPS']),
    'cookie_samesite' => 'Lax',
]);

$error = '';
$username = '';

$db = new BillingDB($pdo);

// CSRF token generation
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = trim($_POST['username'] ?? '');
    $password = $_POST['password'] ?? '';
    $csrf_token = $_POST['csrf_token'] ?? '';

    if (!hash_equals($_SESSION['csrf_token'], $csrf_token)) {
        $error = "Invalid CSRF token.";
    } elseif ($username === '' || $password === '') {
        $error = "Please enter both username and password.";
    } else {
        $user = $db->getAdminByUsername($username);
        if ($user && password_verify($password, $user['password'])) {
            // Log the login event
            $ip = $_SERVER['REMOTE_ADDR'] ?? '';
            $agent = $_SERVER['HTTP_USER_AGENT'] ?? '';
            $db->logAdminLogin((int)$user['id'], $user['username'], $ip, $agent);

            session_regenerate_id(true);
            $_SESSION['admin_logged_in'] = true;
            $_SESSION['username'] = $user['username'];
            $_SESSION['admin_id'] = $user['id'];

            header('Location: index.php');
            exit;
        } else {
            $error = "Invalid username or password.";
        }
    }
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Admin Login - Mikrotik Billing System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- Bootstrap 5.3 & Bootstrap Icons -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.2/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body, html {
            min-height: 100vh;
            font-family: 'Inter', Arial, sans-serif;
            background: linear-gradient(120deg, #ddefff 0%, #d4e3fc 40%, #b9e7ff 100%);
        }
        .login-bg {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(ellipse at 80% 20%, #b9e7ff 0%, transparent 70%), 
                        radial-gradient(ellipse at 40% 90%, #7db7ff33 0%, transparent 70%);
            padding: 1.5rem 0;
        }
        .glass-card {
            background: rgba(255,255,255,0.92);
            border-radius: 24px;
            border: 1px solid rgba(255,255,255,0.45);
            backdrop-filter: blur(10px) saturate(1.22);
            box-shadow: 0 6px 24px rgba(44, 62, 80, 0.13);
            overflow: hidden;
            max-width: 860px;
            width: 100%;
            display: flex;
            flex-direction: row;
            margin: 0 auto;
        }
        .login-form-section {
            flex: 1.2;
            padding: 2.7rem 2.2rem 2.4rem 2.2rem;
            background: rgba(245,250,255,0.92);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .login-logo-section {
            flex: 1;
            background: linear-gradient(135deg, #155ab6 0%, #122ebb 100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-width: 0;
            padding: 2.2rem 1.2rem;
        }
        .login-logo-section img {
            width: 220px;
            max-width: 95%;
            height: auto;
            margin-bottom: 2.2rem;
            border-radius: 16px;
            /* No shadow */
        }
        .login-logo-text {
            color: #fff;
            font-size: 1.15rem;
            text-align: center;
            opacity: 0.92;
            letter-spacing: 0.03em;
        }
        .login-form-section h2 {
            text-align: center;
            color: #155ab6;
            font-weight: 700;
            margin-bottom: 0.7rem;
        }
        .welcome-message {
            text-align: center;
            color: #5779b9;
            font-size: 1.04rem;
            margin-bottom: 1.2rem;
            opacity: 0.88;
        }
        .form-label {
            font-weight: 600;
            color: #155ab6;
        }
        .input-group-text {
            background: none;
            border: none;
        }
        .form-control:focus {
            border-color: #155ab6;
            box-shadow: 0 0 0 0.11rem #155ab63a;
            background: #f2f9ff;
        }
        .show-pw-btn {
            border: none;
            background: none;
            color: #3070c2;
            cursor: pointer;
        }
        .show-pw-btn:focus { outline: none; }
        .remember-me label {
            font-weight: 400;
            color: #3772af;
        }
        .btn-primary {
            background: linear-gradient(90deg, #155ab6 0%, #1b73e8 100%);
            border: none;
            font-weight: 600;
            font-size: 1.13rem;
            padding: 0.7rem 0;
            transition: background 0.2s;
        }
        .btn-primary:hover {
            background: linear-gradient(90deg, #1b73e8 0%, #155ab6 100%);
        }
        .login-footer {
            margin-top: 2.1rem;
            text-align: center;
            color: #aaa;
            font-size: 0.99rem;
        }
        .help-link {
            color: #1b73e8;
            text-decoration: underline;
            font-size: 0.94rem;
            display: inline-block;
            margin-top: 0.8rem;
        }
        .login-error {
            color: #e74c3c;
            background: #ffeaea;
            border-radius: 8px;
            padding: 0.5rem 0.7rem;
            text-align: center;
            font-weight: 600;
            margin-bottom: 1.1rem;
            font-size: 1.05rem;
        }
        @media (max-width: 900px) {
            .glass-card { max-width: 98vw; }
        }
        @media (max-width: 815px) {
            .glass-card {
                flex-direction: column-reverse;
                width: 98vw;
            }
            .login-logo-section {
                padding: 2.2rem 1.2rem 2rem 1.2rem;
            }
            .login-logo-section img { width: 155px; margin-bottom: 1.2rem; }
            .login-form-section { padding: 2rem 1.1rem 2.5rem 1.1rem; }
        }
        @media (max-width: 600px) {
            .glass-card { border-radius: 10px; }
            .login-logo-section img { width: 120px; }
            .login-footer { font-size: 0.87rem; }
        }
    </style>
</head>
<body>
<div class="login-bg">
    <div class="glass-card shadow-none">
        <!-- Left: Login Form -->
        <div class="login-form-section">
            <h2><i class="bi bi-person-circle"></i> Welcome Back!</h2>
            <div class="welcome-message">Sign in to your Mikrotik Billing Portal</div>
            <?php if($error): ?>
                <div class="login-error"><i class="bi bi-exclamation-circle"></i> <?= htmlspecialchars($error) ?></div>
            <?php endif; ?>
            <form method="post" autocomplete="off" novalidate id="loginForm">
                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                <div class="mb-3">
                    <label for="username" class="form-label">Username</label>
                    <div class="input-group">
                        <span class="input-group-text"><i class="bi bi-person"></i></span>
                        <input type="text" class="form-control" id="username" name="username" required autofocus autocomplete="username" value="<?= htmlspecialchars($username) ?>">
                    </div>
                </div>
                <div class="mb-3">
                    <label for="password" class="form-label">Password</label>
                    <div class="input-group">
                        <span class="input-group-text"><i class="bi bi-shield-lock"></i></span>
                        <input type="password" class="form-control" id="password" name="password" required autocomplete="current-password">
                        <button type="button" class="input-group-text show-pw-btn" tabindex="-1" onclick="togglePassword(this)">
                            <i class="bi bi-eye-slash" id="eyeIcon"></i>
                        </button>
                    </div>
                </div>
                <div class="mb-3 form-check remember-me">
                    <input type="checkbox" class="form-check-input" id="rememberMe" name="remember_me" value="1">
                    <label class="form-check-label" for="rememberMe">Remember Me</label>
                </div>
                <button type="submit" class="btn btn-primary w-100" id="loginBtn">
                    <span>Login</span>
                    <span class="spinner-border spinner-border-sm ms-2 d-none" role="status" id="spinner" aria-hidden="true"></span>
                </button>
            </form>
            <a href="https://www.facebook.com/gametechunlifiberph" class="help-link"><i class="bi bi-question-circle"></i> Need Help?</a>
            <div class="login-footer">
                &copy; 2025 Mikrotik Billing Systems<br>
                Powered by Medrozo IT Solutions
            </div>
        </div>
        <!-- Right: Logo and Info -->
        <div class="login-logo-section">
            <img src="assets/images/logo_white.png" alt="Logo">
            <div class="login-logo-text">
                <strong>Mikrotik Billing<br>ISP Management Suite</strong>
                <br>
                <span style="font-weight:400;font-size:0.96rem;opacity:0.72;">
                    Fast. Secure. Reliable.
                </span>
            </div>
        </div>
    </div>
</div>
<script>
function togglePassword(btn) {
    var pw = document.getElementById('password');
    var icon = document.getElementById('eyeIcon');
    if (pw.type === "password") {
        pw.type = "text";
        icon.classList.remove('bi-eye-slash');
        icon.classList.add('bi-eye');
    } else {
        pw.type = "password";
        icon.classList.remove('bi-eye');
        icon.classList.add('bi-eye-slash');
    }
}
document.getElementById('loginForm').addEventListener('submit', function(){
    document.getElementById('spinner').classList.remove('d-none');
    document.getElementById('loginBtn').setAttribute('disabled','disabled');
});
</script>
<!-- Bootstrap JS -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
