<?php
include 'header.php';
include 'database.php';
date_default_timezone_set('Asia/Manila');

/* -------------------- Admin logins -------------------- */
$recentAdminLogins = [];
$adminLoginsSql = "SELECT username, event_type, login_time FROM admin_logins ORDER BY login_time DESC LIMIT 12";
$stmt = $pdo->query($adminLoginsSql);
if ($stmt) $recentAdminLogins = $stmt->fetchAll(PDO::FETCH_ASSOC);

/* -------------------- Revenue totals -------------------- */
$totals = ['today'=>0,'yesterday'=>0,'week'=>0,'month'=>0,'year'=>0];
$query = "
    SELECT
        SUM(CASE WHEN DATE(paid_at) = CURDATE() THEN amount ELSE 0 END) as today,
        SUM(CASE WHEN DATE(paid_at) = CURDATE() - INTERVAL 1 DAY THEN amount ELSE 0 END) as yesterday,
        SUM(CASE WHEN YEARWEEK(paid_at, 1) = YEARWEEK(CURDATE(), 1) THEN amount ELSE 0 END) as week,
        SUM(CASE WHEN YEAR(paid_at) = YEAR(CURDATE()) AND MONTH(paid_at) = MONTH(CURDATE()) THEN amount ELSE 0 END) as month,
        SUM(CASE WHEN YEAR(paid_at) = YEAR(CURDATE()) THEN amount ELSE 0 END) as year
    FROM payments";
$res = $pdo->query($query);
if($row = $res->fetch()) $totals = array_map('floatval', $row);

/* -------------------- Growth -------------------- */
$growthQuery = "
    SELECT
        SUM(CASE WHEN YEAR(paid_at) = YEAR(CURDATE()) AND MONTH(paid_at) = MONTH(CURDATE()) THEN amount ELSE 0 END) as current_month,
        SUM(CASE WHEN YEAR(paid_at) = YEAR(CURDATE() - INTERVAL 1 MONTH) AND MONTH(paid_at) = MONTH(CURDATE() - INTERVAL 1 MONTH) THEN amount ELSE 0 END) as last_month
    FROM payments";
$growthResult = $pdo->query($growthQuery);
$currentMonth = $lastMonth = 0;
if($growthRow = $growthResult->fetch()){
    $currentMonth = (float)($growthRow['current_month'] ?? 0);
    $lastMonth    = (float)($growthRow['last_month'] ?? 0);
}
if($lastMonth == 0) $growthPercent = $currentMonth > 0 ? 100 : 0;
else $growthPercent = (($currentMonth - $lastMonth) / $lastMonth) * 100;
$growthPercentFormatted = number_format($growthPercent,2);
$growthIcon = $growthPercent >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
$growthColor = $growthPercent >= 0 ? 'text-success' : 'text-danger';

/* -------------------- Charts data -------------------- */
$months = []; $salesByMonth = [];
for ($i=11;$i>=0;$i--) {
    $month = date('M Y', strtotime("-$i months"));
    $months[] = $month;
    $salesByMonth[$month] = 0;
}
$monthsSql = "SELECT DATE_FORMAT(paid_at, '%b %Y') as m, SUM(amount) as total
              FROM payments
              WHERE paid_at >= DATE_FORMAT(CURDATE() - INTERVAL 11 MONTH, '%Y-%m-01')
              GROUP BY m ORDER BY MIN(paid_at)";
$res = $pdo->query($monthsSql);
while($row = $res->fetch()){
    $salesByMonth[$row['m']] = (float)$row['total'];
}

$days = []; $salesByDay = [];
for ($i=6;$i>=0;$i--) {
    $day = date('D', strtotime("-$i days"));
    $days[] = $day;
    $salesByDay[$day] = 0;
}
$daysSql = "SELECT DATE_FORMAT(paid_at, '%a') as d, SUM(amount) as total
            FROM payments
            WHERE paid_at >= CURDATE() - INTERVAL 6 DAY
            GROUP BY d";
$res = $pdo->query($daysSql);
while($row = $res->fetch()){
    $salesByDay[$row['d']] = (float)$row['total'];
}

$pieLabels = [];
$pieData = [];
$paymentMethodSql = "
    SELECT payment_method, SUM(amount) as total
    FROM payments
    WHERE payment_method IS NOT NULL AND payment_method <> ''
    GROUP BY payment_method
    ORDER BY total DESC
";
$res = $pdo->query($paymentMethodSql);
while ($row = $res->fetch()) {
    $pieLabels[] = $row['payment_method'];
    $pieData[] = (float)$row['total'];
}

/* -------------------- Recently paid users -------------------- */
$recentPaidUsers = [];
$recentStmt = $pdo->prepare("
    SELECT username, plan_name, amount, paid_at, adjusted_by
    FROM payments
    WHERE paid_at IS NOT NULL
      AND paid_at >= DATE_SUB(CONVERT_TZ(NOW(), '+00:00', '+08:00'), INTERVAL 1 MONTH)
    ORDER BY paid_at DESC
    LIMIT 1000
");
$recentStmt->execute();
$recentPaidUsers = $recentStmt->fetchAll(PDO::FETCH_ASSOC);

/* -------------------- Top clients -------------------- */
$topClients = [];
$topClientsSql = "
    SELECT username, SUM(amount) as total_paid, MAX(paid_at) as last_payment
    FROM payments
    WHERE username IS NOT NULL AND TRIM(username) != ''
    GROUP BY username
    ORDER BY total_paid DESC
    LIMIT 10
";
$res = $pdo->query($topClientsSql);
$topClients = $res->fetchAll(PDO::FETCH_ASSOC);

/* -------------------- Expiring users today -------------------- */
$expiringUsers = [];
$expiringStmt = $pdo->prepare("
    SELECT username, plan_name, expires_at
    FROM customers
    WHERE
        username IS NOT NULL
        AND TRIM(username) <> ''
        AND expires_at IS NOT NULL
        AND DATE(expires_at) = CURDATE()
    ORDER BY expires_at ASC
");
$expiringStmt->execute();
$expiringUsers = $expiringStmt->fetchAll(PDO::FETCH_ASSOC);

/* -------------------- NEW: New Customers (This Month) -------------------- */
/*
  Assumption: customers table has a created_at (or registered_at) datetime column.
  If yours is different, change created_at below to your actual column name.
*/
$newCustomersThisMonth = 0;
try {
    $newCustomersSql = "
        SELECT COUNT(*) AS cnt
        FROM customers
        WHERE YEAR(created_at) = YEAR(CURDATE())
          AND MONTH(created_at) = MONTH(CURDATE())
    ";
    $stmt = $pdo->query($newCustomersSql);
    if ($stmt) $newCustomersThisMonth = (int)$stmt->fetchColumn();
} catch (Throwable $e) {
    // If created_at doesn't exist, keep it 0 (or you can change to another column)
    $newCustomersThisMonth = 0;
}

/* -------------------- NEW: Collection Rate (This Month) -------------------- */
/*
  Definition used:
  collection_rate = (# of distinct users who paid this month) / (# of customers) * 100

  If you have a better denominator (e.g., "active customers this month" or "due invoices"),
  tell me and I'll adjust it.
*/
$totalCustomers = 0;
$distinctPayersThisMonth = 0;

$stmt = $pdo->query("SELECT COUNT(*) FROM customers WHERE username IS NOT NULL AND TRIM(username) <> ''");
if ($stmt) $totalCustomers = (int)$stmt->fetchColumn();

$stmt = $pdo->query("
    SELECT COUNT(DISTINCT username)
    FROM payments
    WHERE paid_at IS NOT NULL
      AND YEAR(paid_at) = YEAR(CURDATE())
      AND MONTH(paid_at) = MONTH(CURDATE())
      AND username IS NOT NULL AND TRIM(username) <> ''
");
if ($stmt) $distinctPayersThisMonth = (int)$stmt->fetchColumn();

$collectionRate = $totalCustomers > 0 ? ($distinctPayersThisMonth / $totalCustomers) * 100 : 0;
$collectionRateFormatted = number_format($collectionRate, 2);

/* -------------------- NEW: Top Service Plans (from customers.plan_name) -------------------- */
$topPlans = [];
$topPlansStmt = $pdo->query("
    SELECT plan_name, COUNT(*) AS cnt
    FROM customers
    WHERE plan_name IS NOT NULL AND TRIM(plan_name) <> ''
    GROUP BY plan_name
    ORDER BY cnt DESC
    LIMIT 8
");
if ($topPlansStmt) $topPlans = $topPlansStmt->fetchAll(PDO::FETCH_ASSOC);

/* -------------------- JS data -------------------- */
$monthsJs = json_encode(array_values($months));
$salesByMonthJs = json_encode(array_values($salesByMonth));
$daysJs = json_encode(array_values($days));
$salesByDayJs = json_encode(array_values($salesByDay));
$pieLabelsJs = json_encode($pieLabels);
$pieDataJs = json_encode($pieData);
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sales Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">

  <style>
    body { background: #f7fafd; }
    .dashboard-card{
      border-radius: 12px;
      background: #fff;
      box-shadow: 0 2px 14px rgba(60,72,100,0.08);
      padding: 1.1rem 1rem;
      margin-bottom: 18px;
    }
    .card-header{
      background: transparent;
      font-weight: 700;
      font-size: 1.02rem;
      border-bottom: 1px solid #f1f1f1;
      padding-bottom: .5rem;
      margin-bottom: .75rem;
    }
    .table th, .table td { vertical-align: middle; }
    .mini-table th, .mini-table td { font-size: .95rem; padding: .45rem .55rem; }
    .mini-table th { background: #fafafa; }
    .avatar{
      width: 28px; height: 28px; border-radius: 50%;
      display: inline-flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 1.05rem;
      color: #fff; margin-right: 7px;
    }

    /* KPI cards */
    .kpi-card{
      display:flex; align-items:center; gap: 1rem;
      padding: 1.1rem 1rem;
      border-radius: 1rem;
      background:#fff;
      box-shadow: 0 2px 14px rgba(60,72,100,0.08);
      min-height: 96px;
    }
    .kpi-icon{
      width: 52px; height: 52px; border-radius: 14px;
      display:flex; align-items:center; justify-content:center;
      font-size: 1.6rem;
    }
    .kpi-label{ font-size:.95rem; color:#6c757d; font-weight:600; }
    .kpi-value{ font-size:1.35rem; font-weight:800; letter-spacing:.2px; }
    .kpi-sub{ font-size:.82rem; color:#8892a0; }

    .icon-blue{ background:#e7f1ff; color:#0d6efd; }
    .icon-green{ background:#dcfce7; color:#198754; }
    .icon-purple{ background:#f1e7ff; color:#6f42c1; }
    .icon-orange{ background:#fff7e6; color:#fd7e14; }
    .icon-red{ background:#ffe6e6; color:#dc3545; }
    .icon-gray{ background:#eef1f5; color:#495057; }

    /* Clock tile */
    .clock-tile{
      background: linear-gradient(135deg, #f8fafc 70%, #e7f1ff 100%);
      border-radius: 1rem;
      box-shadow: 0 2px 12px rgba(13,110,253,0.07);
      min-width: 210px;
      display:flex; flex-direction:column; align-items:center; justify-content:center;
      padding: .75rem 1rem;
    }
    .clock-display{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 1.05rem;
      color: #0d6efd;
      background: #eaf3ff;
      border-radius: .6rem;
      padding: .35rem .65rem;
      letter-spacing: .5px;
      white-space: nowrap;
    }

    /* Charts */
    .chart-container{ position:relative; width:100%; min-height:270px; }
    canvas{ width:100% !important; height:250px !important; }

    @media (max-width: 576px){
      .clock-tile{ min-width: 100%; align-items:flex-start; }
      .clock-display{ width:100%; overflow:hidden; text-overflow: ellipsis; }
      .chart-container{ min-height: 170px;}
      canvas{ height: 140px !important; }
      .mini-table th, .mini-table td{ font-size:.88rem; }
    }
  </style>
</head>

<body>
<div class="container py-3">

  <?php if (!empty($_SESSION['username'])): ?>
    <div class="alert alert-primary d-flex align-items-center mb-3" style="font-size:1.05rem;">
      <i class="fas fa-hand-sparkles me-2"></i>
      Welcome, <strong><?= htmlspecialchars($_SESSION['username']); ?></strong>!
    </div>
  <?php endif; ?>

  <!-- Header -->
  <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
    <h2 class="fw-bold mb-0 text-primary">
      <i class="fas fa-chart-pie"></i> Dashboard
    </h2>

    <div class="clock-tile">
      <div class="small text-muted mb-1" style="letter-spacing:1px;">Manila Time</div>
      <div class="clock-display fw-bold" id="live-clock-square">--:--:--</div>
    </div>
  </div>

  <!-- KPI Row 1 -->
  <div class="row g-3 mb-2">

  <div class="col-12 col-md-6 col-xl-4">

      <div class="kpi-card h-100">
        <div class="kpi-icon icon-gray" style="color:<?= $growthPercent>=0?'#198754':'#dc3545' ?>;">
          <i class="fas <?= $growthIcon ?>"></i>
        </div>
        <div>
          <div class="kpi-label">Revenue Growth</div>
          <div class="kpi-value <?= $growthColor ?>"><?= $growthPercentFormatted ?>%</div>
          <div class="kpi-sub">vs last month</div>
        </div>
      </div>
    </div>



    <div class="col-12 col-md-6 col-xl-3">
      <div class="kpi-card h-100">
        <div class="kpi-icon icon-blue"><i class="fas fa-user-plus"></i></div>
        <div>
          <div class="kpi-label">New Customers</div>
          <div class="kpi-value"><?= number_format($newCustomersThisMonth) ?></div>
          <div class="kpi-sub">This month</div>
        </div>
      </div>
    </div>

    <div class="col-12 col-md-6 col-xl-3">
      <div class="kpi-card h-100">
        <div class="kpi-icon icon-purple"><i class="fas fa-coins"></i></div>
        <div>
          <div class="kpi-label">Collection Rate</div>
          <div class="kpi-value"><?= $collectionRateFormatted ?>%</div>
          <div class="kpi-sub">This month (<?= number_format($distinctPayersThisMonth) ?>/<?= number_format($totalCustomers) ?>)</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Revenue Summary -->
  <div class="row g-3 mb-3">
    <div class="col-6 col-md-2">
      <div class="kpi-card h-100">
        <div class="kpi-icon icon-blue"><i class="fas fa-calendar-day"></i></div>
        <div>
          <div class="kpi-label">Today</div>
          <div class="kpi-value">₱<?= number_format($totals['today'] ?? 0,2) ?></div>
        </div>
      </div>
    </div>
    <div class="col-6 col-md-2">
      <div class="kpi-card h-100">
        <div class="kpi-icon icon-purple"><i class="fas fa-calendar-minus"></i></div>
        <div>
          <div class="kpi-label">Yesterday</div>
          <div class="kpi-value">₱<?= number_format($totals['yesterday'] ?? 0,2) ?></div>
        </div>
      </div>
    </div>
    <div class="col-6 col-md-2">
      <div class="kpi-card h-100">
        <div class="kpi-icon icon-green"><i class="fas fa-calendar-week"></i></div>
        <div>
          <div class="kpi-label">This Week</div>
          <div class="kpi-value">₱<?= number_format($totals['week'] ?? 0,2) ?></div>
        </div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="kpi-card h-100">
        <div class="kpi-icon icon-orange"><i class="fas fa-calendar-alt"></i></div>
        <div>
          <div class="kpi-label">This Month</div>
          <div class="kpi-value">₱<?= number_format($totals['month'] ?? 0,2) ?></div>
        </div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="kpi-card h-100">
        <div class="kpi-icon icon-red"><i class="fas fa-calendar"></i></div>
        <div>
          <div class="kpi-label">This Year</div>
          <div class="kpi-value">₱<?= number_format($totals['year'] ?? 0,2) ?></div>
        </div>
      </div>
    </div>
  </div>


<!-- Charts (full width / whole page) -->
<div class="row g-3 mb-3 align-items-stretch">
  <div class="col-12 d-flex">
    <div class="dashboard-card flex-fill d-flex flex-column w-100">
      <div class="card-header text-center">Sales (Last 12 Months)</div>
      <div class="chart-container flex-grow-1">
        <canvas id="salesMonthChart"></canvas>
      </div>
    </div>
  </div>
</div>

  
 

  <!-- Charts + Admin logins -->
  <div class="row g-3 mb-3 align-items-stretch">
    <div class="col-12 col-lg-8 d-flex flex-column gap-3">
      <div class="dashboard-card flex-fill d-flex flex-column">
        <div class="card-header text-center">Sales (Last 7 Days)</div>
        <div class="chart-container flex-grow-1">
          <canvas id="salesWeekChart"></canvas>
        </div>
      </div>

      <div class="dashboard-card flex-fill d-flex flex-column">
       <div class="card-header d-flex align-items-center justify-content-center gap-2">
  <i class="fas fa-credit-card text-primary"></i>
  Sales by Payment Method
</div>

        <div class="chart-container flex-grow-1">
          <canvas id="salesPieChart"></canvas>
        </div>
      </div>
    </div>

    <div class="col-12 col-lg-4 d-flex">
      <div class="dashboard-card flex-fill d-flex flex-column">
        <div class="card-header d-flex align-items-center gap-2">
          <i class="fas fa-user-shield text-primary"></i> Recent Admin Logins
        </div>

        <div class="table-responsive">
          <table class="table mini-table table-hover mb-0">
            <thead>
              <tr>
                <th>User</th>
                <th>Event</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              <?php if (!empty($recentAdminLogins)): foreach ($recentAdminLogins as $row):
                $colors = ['#0d6efd', '#198754', '#fd7e14', '#dc3545', '#ffc107', '#6c757d', '#20c997'];
                $color = $colors[ord(strtoupper($row['username'][0] ?? 'A')) % count($colors)];
              ?>
                <tr>
                  <td>
                    <span class="avatar" style="background:<?= $color ?>;">
                      <?= strtoupper(substr(htmlspecialchars($row['username']),0,1)); ?>
                    </span>
                    <?= htmlspecialchars($row['username']) ?>
                  </td>
                  <td>
                    <span class="badge bg-<?= $row['event_type'] == 'login' ? 'success':'warning' ?> text-uppercase fw-semibold" style="font-size:.87em;">
                      <?= htmlspecialchars($row['event_type']) ?>
                    </span>
                  </td>
                  <td>
                    <span title="<?= date('l, F j, Y, g:i A', strtotime($row['login_time'])) ?>">
                      <?= date('Y-m-d H:i', strtotime($row['login_time'])) ?>
                    </span>
                  </td>
                </tr>
              <?php endforeach; else: ?>
                <tr><td colspan="3" class="text-center text-muted py-3">No login records found.</td></tr>
              <?php endif; ?>
            </tbody>
          </table>
        </div>

        <div class="mt-3 pt-2 border-top d-flex align-items-center justify-content-between">
          <div>
            <div class="kpi-label mb-1">System Uptime</div>
            <div class="kpi-value" id="uptime-display">00:00:00</div>
            <div class="kpi-sub" id="uptime-sub"></div>
          </div>
          <button class="btn btn-outline-secondary btn-sm" id="uptime-reset" title="Reset Uptime">
            <i class="fas fa-redo"></i>
          </button>
        </div>

      </div>
    </div>
  </div>

  <!-- Bottom row: Top paying clients + Top service plans -->
  <div class="row g-3 mb-4 align-items-stretch">
    <div class="col-12 col-lg-6 d-flex">
      <div class="dashboard-card flex-fill d-flex flex-column">
        <div class="card-header d-flex align-items-center gap-2">
          <i class="fas fa-crown text-warning"></i> Top Paying Clients
        </div>
        <div class="table-responsive">
          <table class="table mini-table table-hover mb-0">
            <thead>
              <tr>
                <th>User</th>
                <th>Total Paid</th>
                <th>Last Payment</th>
              </tr>
            </thead>
            <tbody>
              <?php if (!empty($topClients)):
                $rank = 1;
                foreach ($topClients as $c):
                  $colors = ['#0d6efd', '#198754', '#fd7e14', '#dc3545', '#ffc107', '#6c757d', '#20c997'];
                  $color = $colors[ord(strtoupper($c['username'][0] ?? 'A')) % count($colors)];
              ?>
                <tr>
                  <td>
                    <?php if($rank === 1): ?><i class="fas fa-crown text-warning me-1" title="Top Client"></i><?php endif; ?>
                    <span class="avatar" style="background:<?= $color ?>;">
                      <?= strtoupper(substr(htmlspecialchars($c['username']),0,1)); ?>
                    </span>
                    <?= htmlspecialchars($c['username']); ?>
                  </td>
                  <td><span class="badge bg-primary">₱<?= number_format((float)$c['total_paid'],2) ?></span></td>
                  <td>
                    <?php if (!empty($c['last_payment'])): ?>
                      <span title="<?= date('l, F j, Y, g:i A', strtotime($c['last_payment'])) ?>">
                        <?= date('Y-m-d', strtotime($c['last_payment'])) ?>
                      </span>
                    <?php else: ?>
                      <span class="text-muted">N/A</span>
                    <?php endif; ?>
                  </td>
                </tr>
              <?php $rank++; endforeach; else: ?>
                <tr><td colspan="3" class="text-center text-muted py-3">No paying clients found.</td></tr>
              <?php endif; ?>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="col-12 col-lg-6 d-flex">
      <div class="dashboard-card flex-fill d-flex flex-column">
        <div class="card-header d-flex align-items-center gap-2">
          <i class="fas fa-wifi text-success"></i> Top Service Plans
        </div>
        <div class="table-responsive">
          <table class="table mini-table table-hover mb-0">
            <thead>
              <tr>
                <th>Plan</th>
                <th class="text-end">Customers</th>
              </tr>
            </thead>
            <tbody>
              <?php if (!empty($topPlans)): foreach ($topPlans as $p): ?>
                <tr>
                  <td><span class="badge bg-success-subtle text-success border border-success-subtle"><?= htmlspecialchars($p['plan_name']) ?></span></td>
                  <td class="text-end fw-semibold"><?= number_format((int)$p['cnt']) ?></td>
                </tr>
              <?php endforeach; else: ?>
                <tr><td colspan="2" class="text-center text-muted py-3">No plans found.</td></tr>
              <?php endif; ?>
            </tbody>
          </table>
        </div>
        <div class="kpi-sub mt-2">
          Based on customers.plan_name
        </div>
      </div>
    </div>
  </div>










<!-- Expiring Users (full width / whole page) -->
<div class="row g-3 mb-3 align-items-stretch">
  <div class="col-12 d-flex">
    <div class="dashboard-card flex-fill d-flex flex-column w-100">
      <div class="card-header d-flex align-items-center gap-2">
        <i class="fas fa-clock text-danger"></i> Expiring Users (Today)
      </div>

      <div class="table-responsive">
        <table class="table mini-table table-hover mb-0">
          <thead>
            <tr>
              <th>User</th>
              <th>Plan</th>
              <th>Expires At</th>
              <th>Left</th>
            </tr>
          </thead>
          <tbody>
            <?php if (!empty($expiringUsers)): foreach ($expiringUsers as $u): ?>
              <tr>
                <td><?= htmlspecialchars($u['username']); ?></td>
                <td><span class="badge bg-warning text-dark"><?= htmlspecialchars($u['plan_name']); ?></span></td>
                <td><?= htmlspecialchars($u['expires_at']); ?></td>
                <td>
                  <?php
                    if ($u['expires_at']) {
                      $now = new DateTime('now', new DateTimeZone('Asia/Manila'));
                      $expires = new DateTime($u['expires_at'], new DateTimeZone('Asia/Manila'));
                      $expires_ts = $expires->getTimestamp();
                      $now_ts = $now->getTimestamp();
                      if ($expires_ts > $now_ts) {
                        $diff = $now->diff($expires);
                        echo '<span class="countdown" data-expire="' . $expires_ts . '">';
                        echo ($diff->d > 0 ? $diff->d . 'd ' : '');
                        echo ($diff->h > 0 ? $diff->h . 'h ' : '');
                        echo ($diff->i > 0 ? $diff->i . 'm ' : '');
                        echo $diff->s . 's';
                        echo '</span>';
                      } else echo '<span class="text-danger">Expired</span>';
                    } else echo '<span class="text-muted">N/A</span>';
                  ?>
                </td>
              </tr>
            <?php endforeach; else: ?>
              <tr><td colspan="4" class="text-center text-muted py-3">No expiring users today.</td></tr>
            <?php endif; ?>
          </tbody>
        </table>
      </div>

    </div>
  </div>
</div>











  <!-- JS -->
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    const months = <?= $monthsJs ?>;
    const salesByMonth = <?= $salesByMonthJs ?>;
    const days = <?= $daysJs ?>;
    const salesByDay = <?= $salesByDayJs ?>;
    const pieLabels = <?= $pieLabelsJs ?>;
    const pieData = <?= $pieDataJs ?>;

    new Chart(document.getElementById('salesMonthChart').getContext('2d'), {
      type: 'bar',
      data: { labels: months, datasets: [{ label: '₱ Sales', data: salesByMonth, backgroundColor: '#0d6efd' }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }},
        scales: { y: { beginAtZero: true } }
      }
    });

    new Chart(document.getElementById('salesWeekChart').getContext('2d'), {
      type: 'line',
      data: {
        labels: days,
        datasets: [{
          label: '₱ Sales',
          data: salesByDay,
          fill: false,
          borderColor: '#198754',
          tension: 0.3,
          pointBackgroundColor: '#198754',
          pointRadius: 4
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }},
        scales: { y: { beginAtZero: true } }
      }
    });

new Chart(document.getElementById('salesPieChart').getContext('2d'), {
  type: 'bar',
  data: {
    labels: pieLabels,
    datasets: [{
      label: '₱ Sales',
      data: pieData,
      backgroundColor: [
        '#0d6efd',
        '#198754',
        '#0dcaf0',
        '#6f42c1',
        '#ffc107',
        '#fd7e14',
        '#dc3545',
        '#20c997'
      ],
      borderRadius: 8,
      barThickness: 18
    }]
  },
  options: {
    indexAxis: 'y', // makes it horizontal
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: function(context) {
            let total = context.dataset.data.reduce((a, b) => a + b, 0);
            let value = context.raw;
            let percent = ((value / total) * 100).toFixed(1);
            return `₱${value.toLocaleString()} (${percent}%)`;
          }
        }
      }
    },
    scales: {
      x: {
        beginAtZero: true,
        grid: {
          color: '#eef2f7'
        },
        ticks: {
          callback: function(value) {
            return '₱' + value.toLocaleString();
          }
        }
      },
      y: {
        grid: { display: false },
        ticks: {
          font: {
            weight: '600'
          }
        }
      }
    }
  }
});


    // Countdown timers (uses epoch provided by server; display is consistent)
    function updateCountdowns() {
      const now = Math.floor(Date.now() / 1000);
      document.querySelectorAll('.countdown').forEach(function(el) {
        const expire = parseInt(el.getAttribute('data-expire'), 10);
        const diff = expire - now;
        if (diff > 0) {
          const d = Math.floor(diff / 86400);
          const h = Math.floor((diff % 86400) / 3600);
          const m = Math.floor((diff % 3600) / 60);
          const s = diff % 60;
          el.textContent = (d>0 ? d+'d ' : '') + (h>0 ? h+'h ' : '') + (m>0 ? m+'m ' : '') + s + 's';
          el.classList.remove('text-danger');
        } else {
          el.textContent = 'Expired';
          el.classList.add('text-danger');
        }
      });
    }
    setInterval(updateCountdowns, 1000);
    updateCountdowns();

    // Digital Clock (Manila)
    function updateDigitalClock() {
      const now = new Date();
      const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
      const manila = new Date(utc + (3600000 * 8));
      const pad = n => (n < 10 ? '0' + n : n);
      const clockEl = document.getElementById('live-clock-square');
      if (clockEl) {
        const h = pad(manila.getHours());
        const m = pad(manila.getMinutes());
        const s = pad(manila.getSeconds());
        const date = manila.toLocaleDateString('en-PH', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
        clockEl.textContent = `${date} ${h}:${m}:${s}`;
      }
    }
    setInterval(updateDigitalClock, 1000);
    updateDigitalClock();

    // Uptime
    (function() {
      function pad(n) { return n < 10 ? '0' + n : n; }
      function formatHMS(totalSec) {
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        return pad(h) + ':' + pad(m) + ':' + pad(s);
      }
      const uptimeEl = document.getElementById('uptime-display');
      const resetBtn = document.getElementById('uptime-reset');
      const uptimeSub = document.getElementById('uptime-sub');
      const STORAGE_KEY = 'dashboard_uptime_start';

      let startEpoch = parseInt(localStorage.getItem(STORAGE_KEY), 10);
      if (!startEpoch) {
        startEpoch = Math.floor(Date.now() / 1000);
        localStorage.setItem(STORAGE_KEY, String(startEpoch));
      }

      function updateUptime() {
        const nowSecs = Math.floor(Date.now() / 1000);
        const diff = Math.max(0, nowSecs - startEpoch);
        if (uptimeEl) uptimeEl.textContent = formatHMS(diff);
        if (uptimeSub) uptimeSub.textContent = 'Uptime since ' + new Date(startEpoch * 1000).toLocaleString();
      }

      function resetUptime() {
        startEpoch = Math.floor(Date.now() / 1000);
        localStorage.setItem(STORAGE_KEY, String(startEpoch));
        updateUptime();
      }

      if (resetBtn) resetBtn.addEventListener('click', function(e){
        e.preventDefault();
        resetUptime();
      });

      setInterval(updateUptime, 1000);
      updateUptime();
    })();
  </script>

</div>
</body>
</html>
