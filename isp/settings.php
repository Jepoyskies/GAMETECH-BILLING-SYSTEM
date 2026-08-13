<?php include 'header.php'; ?>

<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">

<main class="container py-4">
    <h2 class="mb-4 text-center fw-bold">One Stop Shop</h2>
    <div class="row g-4">
        <!-- Customers -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="customers.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-users fa-2x mb-3 text-primary"></i>
                        <h5 class="card-title fw-semibold mb-2">Customers</h5>
                        <p class="card-text text-muted">Manage your customer database, add or edit users.</p>
                        <span class="badge bg-primary">Go</span>
                    </div>
                </div>
            </a>
        </div>

        <!-- Packages -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="serviceplans.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-cube fa-2x mb-3 text-info"></i>
                        <h5 class="card-title fw-semibold mb-2">Packages</h5>
                        <p class="card-text text-muted">View and manage internet plans and pricing.</p>
                        <span class="badge bg-info text-dark">Go</span>
                    </div>
                </div>
            </a>
        </div>

        <!-- Billing -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="subscription_plans.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-file-invoice-dollar fa-2x mb-3 text-success"></i>
                        <h5 class="card-title fw-semibold mb-2">Subscriptions</h5>
                        <p class="card-text text-muted">Generate invoices, view payment history, and more.</p>
                        <span class="badge bg-success">Go</span>
                    </div>
                </div>
            </a>
        </div>







        <!-- Auto Suspended -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="suspend_pppoe_users.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-life-ring fa-2x mb-3 text-danger"></i>
                        <h5 class="card-title fw-semibold mb-2">Auto Suspend</h5>
                        <p class="card-text text-muted">Auto Suspend Due Clients.</p>
                        <span class="badge bg-danger">Go</span>
                    </div>
                </div>
            </a>
        </div>








        <!-- Settings -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="profile.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-cogs fa-2x mb-3 text-secondary"></i>
                        <h5 class="card-title fw-semibold mb-2">Profile Settings</h5>
                        <p class="card-text text-muted">System configuration and preferences.</p>
                        <span class="badge bg-secondary">Go</span>
                    </div>
                </div>
            </a>
        </div>









                <!-- Backup -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="backup_database.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fa fa-undo fa-2x mb-3 text-secondary"></i>
                        <h5 class="card-title fw-semibold mb-2">Backup Database</h5>
                        <p class="card-text text-muted">System Backup and Database Restoration.</p>
                        <span class="badge bg-secondary">Go</span>
                    </div>
                </div>
            </a>
        </div>










                <!-- Reports -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="payment_logs.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-chart-line fa-2x mb-3 text-warning"></i>
                        <h5 class="card-title fw-semibold mb-2">Reports</h5>
                        <p class="card-text text-muted">Access usage, sales, and financial reports.</p>
                        <span class="badge bg-warning text-dark">Go</span>
                    </div>
                </div>
            </a>
        </div>



        <!-- SMS Reminder -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="sms.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-bell fa-2x mb-3 text-warning"></i>
                        <h5 class="card-title fw-semibold mb-2">SMS Text Messaging</h5>
                        <p class="card-text text-muted">View system text alerts, reminders, and announcements.</p>
                        <span class="badge bg-warning text-dark">Go</span>
                    </div>
                </div>
            </a>
        </div>

        <!-- Auto SMS -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="auto_sms.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-network-wired fa-2x mb-3 text-success"></i>
                        <h5 class="card-title fw-semibold mb-2">Auto SMS Reminder</h5>
                        <p class="card-text text-muted">Automatically send sms reminder before user expiration.</p>
                        <span class="badge bg-success">Go</span>
                    </div>
                </div>
            </a>
        </div>

        <!-- Mac Address -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="mac_address.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fas fa-clipboard-list fa-2x mb-3 text-info"></i>
                        <h5 class="card-title fw-semibold mb-2">Mac Address</h5>
                        <p class="card-text text-muted">Track user Mac Addresses and system activities.</p>
                        <span class="badge bg-info text-dark">Go</span>
                    </div>
                </div>
            </a>
        </div>


  <!-- Mac Address -->
        <div class="col-12 col-sm-6 col-lg-4">
            <a href="fbt_plc_calculator.php" class="text-decoration-none">
                <div class="card shadow-sm border-0 h-100 hover-zoom">
                    <div class="card-body text-center">
                        <i class="fa-brands fa-creative-commons-remix fa-2x mb-3 text-info"></i>
                        <h5 class="card-title fw-semibold mb-2">PON Calculator</h5>
                        <p class="card-text text-muted">Build your PON network with unlimited cascading | FBT Tap Couplers & PLC Splitters.</p>
                        <span class="badge bg-info text-dark">Go</span>
                    </div>
                </div>
            </a>
        </div>


    </div>
</main>

<!-- Optional: Add some hover effect -->
<style>
.hover-zoom {
    transition: transform .15s;
}
.hover-zoom:hover {
    transform: translateY(-4px) scale(1.03);
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
}
</style>

<?php include 'footer.php'; ?>
