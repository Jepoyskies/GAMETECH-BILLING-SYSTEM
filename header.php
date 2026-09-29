<?php
// header.php
session_start();
if (!isset($_SESSION['admin_logged_in'])) {
    header('Location: login.php');
    exit;
}
if (!isset($_SESSION['login_time'])) {
    $_SESSION['login_time'] = time();
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
    <title>Mikrotik Billing System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:400,600&display=swap" rel="stylesheet">
    

<style>
/* ... [existing styles, unchanged] ... */
.sidebar {
    position: fixed; top: 0; left: 0; bottom: 0;
    width: 250px;
    background: linear-gradient(135deg, #2151A1 0%, #19407A 100%);
    color: #fff;
    transition: width 0.3s, left 0.3s;
    z-index: 1040;
    display: flex; flex-direction: column; min-height: 100vh;
    box-shadow: 2px 0 10px rgba(33,81,161,0.10);
}
.sidebar.collapsed { width: 70px; }
.sidebar-header {
    padding: 1.5rem 1.2rem 1rem 1.2rem; text-align: center;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    background: rgba(0,0,0,0.02);
}
.sidebar-header img { max-width: 150px; transition: max-width 0.3s; }
.sidebar.collapsed .sidebar-header img { max-width: 34px; }
.sidebar .close-btn { position: absolute; top: 18px; right: 18px; background: none; border: none;
                      color: #fff; font-size: 1.6rem; display: none; }
@media (max-width: 991.98px) {
    .sidebar { left: -260px; width: 250px; }
    .sidebar.open { left: 0; }
    .sidebar .close-btn { display: block; }
}
.sidebar nav { flex: 1 1 auto; }
.sidebar ul { list-style: none; margin: 0; padding: 0; }
.sidebar ul li { margin: 0.2rem 0; }
.sidebar ul li a {
    display: flex; align-items: center; color: #fff;
    padding: 0.85rem 1.5rem; transition: background 0.2s, color 0.2s;
    font-weight: 500; border-left: 4px solid transparent; text-decoration: none;
    font-size: 1rem; border-radius: 0 24px 24px 0;
}
.sidebar ul li a .icon {
    display: inline-flex; width: 2rem; justify-content: center;
    margin-right: 1rem; font-size: 1.2rem; transition: margin 0.3s;
    color: #F9B233; /* yellow icon accent */
}
.sidebar.collapsed ul li a .icon { margin-right: 0; }
.sidebar.collapsed ul li a span:not(.icon) { display: none; }
.sidebar ul li a.active, .sidebar ul li a:hover {
    background: linear-gradient(90deg, #F9B23322 0%, #2151A1 90%);
    color: #F9B233;
    border-left: 4px solid #F9B233;
}
.sidebar ul li a.active .icon,
.sidebar ul li a:hover .icon {
    color: #F9B233;
}
.sidebar-footer {
    padding: 1.2rem;
    border-top: 1px solid rgba(255,255,255,0.09);
    text-align: center; font-size: 0.94rem; color: #e8e8e8;
    background: rgba(33,81,161, 0.15);
}
.sidebar-overlay { display: none; position: fixed; inset: 0;
                   background: rgba(33,81,161,0.18); z-index: 1039; transition: opacity 0.2s; }
.sidebar-overlay.active { display: block; }
.main-content { margin-left: 250px; transition: margin 0.3s; min-height: 100vh; }
.main-content.full, .sidebar.collapsed ~ .main-content { margin-left: 70px; }
@media (max-width: 991.98px) { .main-content, .main-content.full { margin-left: 0; } }
.topbar { padding: 0.9rem 1.5rem; background: #fff; border-bottom: 1px solid #f0f0f0;
           display: flex; align-items: center; justify-content: space-between; min-height: 62px;
           position: sticky; top: 0; z-index: 10; }
.menu-btn, .hide-btn, .show-btn {
    background: none; border: none; font-size: 1.45rem; color: #2151A1;
    margin-right: 1rem; cursor: pointer; transition: color 0.2s;
}
.menu-btn:hover, .hide-btn:hover, .show-btn:hover { color: #F9B233; }
.topbar-title { font-weight: 600; color: #2151A1; font-size: 1.2rem; }
.sidebar nav { overflow-y: auto; }
.sidebar nav::-webkit-scrollbar { width: 6px; }
.sidebar nav::-webkit-scrollbar-thumb { background: #19407A; border-radius: 2px; }
</style>

</head>
<body>
<div class="sidebar" id="sidebar">
    <div class="sidebar-header">
        <a href="index.php"><img src="assets/images/logo_white.png" alt="Logo"></a>
        <button class="close-btn" id="closeSidebar" type="button">&times;</button>
    </div>
    <nav>
        <ul>
            <li><a href="index.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='index.php') echo ' active'; ?>"><span class="icon"><i class="fas fa-chart-pie"></i></span> <span>Dashboard</span></a></li>
            <li><a href="customers.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='customers.php') echo ' active'; ?>"><span class="icon"><i class="fas fa-users"></i></span> <span>Customers</span></a></li>
            <li><a href="pppoe_monitoring.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='pppoe_monitoring.php') echo ' active'; ?>"><span class="icon"><i class="fa-brands fa-creative-commons-sampling-plus"></i></span> <span>Live Monitoring</span></a></li>        
            <li><a href="subscription_plans.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='subscription_plans.php') echo ' active'; ?>"><span class="icon"><i class="fa-regular fa-address-book"></i></span> <span>Subscription Plans</span></a></li>        
            <li><a href="add_on_payments.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='add_on_payments.php') echo ' active'; ?>"><span class="icon"><i class="fa-solid fa-cash-register"></i></span> <span>Payments</span></a></li>        
        
            <li><a href="payment_logs.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='payment_logs.php') echo ' active'; ?>"><span class="icon"><i class="fas fa-file-invoice-dollar"></i></span> <span>Payment logs</span></a></li>
            <li><a href="agents.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='agents.php') echo ' active'; ?>"><span class="icon"><i class="fa fa-address-card"></i></span> <span>Agents</span></a></li>
            <li><a href="mikrotik_devices.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='mikrotik_devices.php') echo ' active'; ?>"><span class="icon"><i class="fa fa-mobile"></i></span> <span>Mikrotik Devices</span></a></li>
            <li><a href="mikrotik_active_users.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='mikrotik_active_users.php') echo ' active'; ?>"><span class="icon"><i class="fa-solid fa-computer"></i></span> <span>Mikrotik Active Users</span></a></li>
            <li><a href="geo_user_map.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='geo_user_map.php') echo ' active'; ?>"><span class="icon"><i class="fa-solid fa-map-location"></i></span> <span>GeoMap</span></a></li>
            <li><a href="view_logs.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='view_logs.php') echo ' active'; ?>"><span class="icon"><i class="fa fa-gavel"></i></span> <span>Logs</span></a></li>
            <li><a href="settings.php" class="menu-link<?php if(basename($_SERVER['PHP_SELF'])=='settings.php') echo ' active'; ?>"><span class="icon"><i class="fas fa-cog"></i></span> <span>Settings</span></a></li>
            

            <li><a href="logout.php" class="menu-link"><span class="icon"><i class="fas fa-sign-out-alt me-1"></i></span> <span>Logout</span></a></li>
        </ul>
    </nav>
    <div class="sidebar-footer text-center mt-auto mb-2">
        <small>&copy; <?php echo date('Y'); ?> Mikrotik Billing Systems</small>
    </div>
</div>

<div class="sidebar-overlay" id="sidebarOverlay"></div>
<div class="main-content" id="mainContent">
    <header class="topbar">
        <div>
            <button class="hide-btn d-none d-lg-inline" id="hideSidebar" title="Hide Sidebar" type="button">
                <i class="fas fa-angle-left"></i>
            </button>
            <button class="show-btn d-none d-lg-inline" id="showSidebar" title="Show Sidebar" type="button" style="display: none;">
                <i class="fas fa-angle-right"></i>
            </button>
            <button class="menu-btn d-lg-none" id="openSidebar" type="button">
                <i class="fas fa-bars"></i>
            </button>
        </div>
        <div>
            <!-- ... -->
        </div>
    </header>

<script>
// Sidebar state persistence logic
document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    const hideBtn = document.getElementById('hideSidebar');
    const showBtn = document.getElementById('showSidebar');
    // Restore state
    let collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (collapsed) {
        sidebar.classList.add('collapsed');
        if (mainContent) mainContent.classList.add('full');
        hideBtn.style.display = 'none';
        showBtn.style.display = '';
    } else {
        sidebar.classList.remove('collapsed');
        if (mainContent) mainContent.classList.remove('full');
        hideBtn.style.display = '';
        showBtn.style.display = 'none';
    }
    // Hide button
    hideBtn.addEventListener('click', function () {
        sidebar.classList.add('collapsed');
        if (mainContent) mainContent.classList.add('full');
        hideBtn.style.display = 'none';
        showBtn.style.display = '';
        localStorage.setItem('sidebarCollapsed', 'true');
    });
    // Show button
    showBtn.addEventListener('click', function () {
        sidebar.classList.remove('collapsed');
        if (mainContent) mainContent.classList.remove('full');
        hideBtn.style.display = '';
        showBtn.style.display = 'none';
        localStorage.setItem('sidebarCollapsed', 'false');
    });
    // Mobile sidebar controls
    const openSidebar = document.getElementById('openSidebar');
    const closeSidebar = document.getElementById('closeSidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    openSidebar && openSidebar.addEventListener('click', function () {
        sidebar.classList.add('open');
        sidebarOverlay.classList.add('active');
    });
    closeSidebar && closeSidebar.addEventListener('click', function () {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('active');
    });
    sidebarOverlay && sidebarOverlay.addEventListener('click', function () {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('active');
    });
});
</script>

<script>
function pad(n) { return n < 10 ? '0' + n : n; }
function updateClockAndUptime() {
    // CLOCK
    const now = new Date();
    const clockEl = document.getElementById('live-clock');
    if (clockEl) {
        let h = pad(now.getHours());
        let m = pad(now.getMinutes());
        let s = pad(now.getSeconds());
        clockEl.textContent = `${h}:${m}:${s}`;
    }
    // UPTIME
    const uptimeEl = document.getElementById('user-uptime');
    if (uptimeEl && window.LOGIN_TIME) {
        let diff = Math.floor(Date.now() / 1000) - window.LOGIN_TIME;
        let hours = Math.floor(diff / 3600);
        let minutes = Math.floor((diff % 3600) / 60);
        let seconds = diff % 60;
        let parts = [];
        if (hours > 0) parts.push(hours + "h");
        if (minutes > 0 || hours > 0) parts.push(minutes + "m");
        parts.push(seconds + "s");
        uptimeEl.textContent = "Uptime: " + parts.join(" ");
    }
}
setInterval(updateClockAndUptime, 1000);
updateClockAndUptime();
</script>
</body>
</html>
