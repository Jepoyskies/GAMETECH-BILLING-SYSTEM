<?php
// ---------- CSV EXPORT (must be first, before any output!) ----------
if (isset($_GET['export']) && $_GET['export'] === 'csv') {
    include 'database.php'; // Provides $pdo

    // Collect filters
    $filter_from     = $_GET['from']     ?? '';
    $filter_to       = $_GET['to']       ?? '';
    $filter_search   = trim($_GET['search']   ?? '');
    $filter_method   = $_GET['method']   ?? '';
    $filter_username = trim($_GET['username'] ?? '');
    $filter_adjusted_by = trim($_GET['adjusted_by'] ?? '');
    $quick_range     = $_GET['range']    ?? '';

    $today     = date('Y-m-d');
    $weekStart = date('Y-m-d', strtotime('monday this week'));
    $weekEnd   = date('Y-m-d', strtotime('sunday this week'));
    $monthFirst= date('Y-m-01');
    $monthLast = date('Y-m-t');
    $yearFirst = date('Y-01-01');
    $yearLast  = date('Y-12-31');

    // Apply quick range if provided and no explicit from/to entered
    if ($quick_range && !$filter_from && !$filter_to) {
        if ($quick_range === 'today') {
            $filter_from = $filter_to = $today;
        } elseif ($quick_range === 'week') {
            $filter_from = $weekStart;
            $filter_to   = $weekEnd;
        } elseif ($quick_range === 'month') {
            $filter_from = $monthFirst;
            $filter_to   = $monthLast;
        } elseif ($quick_range === 'year') {
            $filter_from = $yearFirst;
            $filter_to   = $yearLast;
        }
    }

    $where  = [];
    $params = [];
    if ($filter_from) {
        $where[]  = "paid_at >= ?";
        $params[] = $filter_from . ' 00:00:00';
    }
    if ($filter_to) {
        $where[]  = "paid_at <= ?";
        $params[] = $filter_to . ' 23:59:59';
    }
    if ($filter_search) {
        $where[]  = "(username LIKE ? OR reference_no LIKE ?)";
        $params[] = "%$filter_search%";
        $params[] = "%$filter_search%";
    }
    if ($filter_username) {
        $where[]  = "username LIKE ?";
        $params[] = "%$filter_username%";
    }
    if ($filter_method) {
        $where[]  = "payment_method = ?";
        $params[] = $filter_method;
    }
    if ($filter_adjusted_by) {
        $where[]  = "adjusted_by LIKE ?";
        $params[] = "%$filter_adjusted_by%";
    }
    $where_sql = $where ? "WHERE " . implode(' AND ', $where) : "";

    // Fetch all filtered data (no pagination)
    $export_sql = "SELECT * FROM payments $where_sql ORDER BY paid_at DESC";
    $export_stmt = $pdo->prepare($export_sql);
    $export_stmt->execute($params);
    $export_data = $export_stmt->fetchAll(PDO::FETCH_ASSOC);

    // Output headers
    header('Content-Type: text/csv; charset=UTF-8');
    header('Content-Disposition: attachment; filename="payments_export_' . date('Ymd_His') . '.csv"');
    header("Pragma: no-cache");
    header("Expires: 0");

    $output = fopen('php://output', 'w');
    fwrite($output, "\xEF\xBB\xBF"); // UTF-8 BOM for Excel

    // Header row (added Payment Date Received)
    fputcsv($output, [
        'Created', 'Username', 'Plan', 'Amount', 'Amount Adjusted (Reason)',
        'Days', 'Expires At', 'Paid At', 'Payment Date Received', 'Adjusted By', 'Method', 'Reference',
        'Latitude', 'Longitude'
    ]);

    // Data rows
    foreach ($export_data as $row) {
        fputcsv($output, [
            $row['created_at'] ?? '',
            $row['username'] ?? '',
            $row['plan_name'] ?? '',
            $row['amount'] ?? '',
            $row['reason'] ?? '',
            $row['days'] ?? '',
            $row['expires_at'] ?? '',
            $row['paid_at'] ?? '',
            $row['payment_date_received'] ?? '',
            $row['adjusted_by'] ?? '',
            $row['payment_method'] ?? '',
            $row['reference_no'] ?? '',
            $row['latitude'] ?? '',
            $row['longitude'] ?? ''
        ]);
    }
    fclose($output);
    exit;
}
// ---------- END CSV EXPORT ----------

include 'header.php';
include 'database.php'; // Provides $pdo

// --- Filters (GET) ---
$filter_from     = $_GET['from']     ?? '';
$filter_to       = $_GET['to']       ?? '';
$filter_search   = trim($_GET['search']   ?? '');
$filter_method   = $_GET['method']   ?? '';
$filter_username = trim($_GET['username'] ?? '');
$filter_adjusted_by = trim($_GET['adjusted_by'] ?? '');
$quick_range     = $_GET['range']    ?? ''; // today, week, month, year, ''

// --- Date Ranges for quick filters ---
$today     = date('Y-m-d');
$weekStart = date('Y-m-d', strtotime('monday this week'));
$weekEnd   = date('Y-m-d', strtotime('sunday this week'));
$monthFirst= date('Y-m-01');
$monthLast = date('Y-m-t');
$yearFirst = date('Y-01-01');
$yearLast  = date('Y-12-31');

// Apply quick range if provided and no explicit from/to entered
if ($quick_range && !$filter_from && !$filter_to) {
    if ($quick_range === 'today') {
        $filter_from = $filter_to = $today;
    } elseif ($quick_range === 'week') {
        $filter_from = $weekStart;
        $filter_to   = $weekEnd;
    } elseif ($quick_range === 'month') {
        $filter_from = $monthFirst;
        $filter_to   = $monthLast;
    } elseif ($quick_range === 'year') {
        $filter_from = $yearFirst;
        $filter_to   = $yearLast;
    }
}

// --- Build WHERE ---
$where  = [];
$params = [];
if ($filter_from) {
    $where[]  = "paid_at >= ?";
    $params[] = $filter_from . ' 00:00:00';
}
if ($filter_to) {
    $where[]  = "paid_at <= ?";
    $params[] = $filter_to . ' 23:59:59';
}
if ($filter_search) {
    $where[]  = "(username LIKE ? OR reference_no LIKE ?)";
    $params[] = "%$filter_search%";
    $params[] = "%$filter_search%";
}
if ($filter_username) {
    $where[]  = "username LIKE ?";
    $params[] = "%$filter_username%";
}
if ($filter_method) {
    $where[]  = "payment_method = ?";
    $params[] = $filter_method;
}
if ($filter_adjusted_by) {
    $where[]  = "adjusted_by LIKE ?";
    $params[] = "%$filter_adjusted_by%";
}
$where_sql = $where ? "WHERE " . implode(' AND ', $where) : "";

// --- Helper for summary queries ---
function get_sum($pdo, $where_sql, $params) {
    $sql  = "SELECT SUM(amount) AS total FROM payments $where_sql";
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $row  = $stmt->fetch(PDO::FETCH_ASSOC);
    return $row && $row['total'] !== null ? (float)$row['total'] : 0;
}

// --- Grand Total (not filtered) ---
$grand_total = get_sum($pdo, "", []);

// --- Filtered range total (date range & filters) ---
$filtered_range_total = get_sum($pdo, $where_sql, $params);

// --- Filtered summaries based on current filters + date conditions ---
$thisYear  = date('Y');
$thisMonth = date('Y-m');

// Helper to clone where/params
function extend_where($baseWhere, $baseParams, $condition, $value) {
    $w = $baseWhere;
    $p = $baseParams;
    $w[]  = $condition;
    $p[]  = $value;
    return [$w, $p];
}

// Today
list($today_where, $today_params) =
    extend_where($where, $params, "DATE(paid_at) = ?", $today);
$yesterday = date('Y-m-d', strtotime('-1 day'));
list($yesterday_where, $yesterday_params) =
    extend_where($where, $params, "DATE(paid_at) = ?", $yesterday);
// This week
list($week_where, $week_params) =
    extend_where($where, $params, "paid_at >= ?", $weekStart . ' 00:00:00');
list($week_where, $week_params) =
    extend_where($week_where, $week_params, "paid_at <= ?", $weekEnd . ' 23:59:59');
// This month
list($month_where, $month_params) =
    extend_where($where, $params, "DATE_FORMAT(paid_at, '%Y-%m') = ?", $thisMonth);
// This year
list($year_where, $year_params) =
    extend_where($where, $params, "YEAR(paid_at) = ?", $thisYear);

$total_today     = get_sum($pdo, $today_where     ? "WHERE " . implode(' AND ', $today_where)     : "", $today_params);
$total_yesterday = get_sum($pdo, $yesterday_where ? "WHERE " . implode(' AND ', $yesterday_where) : "", $yesterday_params);
$total_week      = get_sum($pdo, $week_where      ? "WHERE " . implode(' AND ', $week_where)      : "", $week_params);
$total_month     = get_sum($pdo, $month_where     ? "WHERE " . implode(' AND ', $month_where)     : "", $month_params);
$total_year      = get_sum($pdo, $year_where      ? "WHERE " . implode(' AND ', $year_where)      : "", $year_params);

// --- Chart (last 14 days, filtered) ---
$chart_where  = $where;
$chart_params = $params;
$chart_where[]  = "paid_at >= ?";
$chart_params[] = date('Y-m-d', strtotime('-13 days')) . ' 00:00:00';
$chart_sql = "SELECT DATE(paid_at) AS d, SUM(amount) AS t
              FROM payments " . (count($chart_where) ? "WHERE " . implode(' AND ', $chart_where) : '') . "
              GROUP BY d
              ORDER BY d";
$stmt = $pdo->prepare($chart_sql);
$stmt->execute($chart_params);
$chart_data = [];
while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
    $chart_data[$row['d']] = $row['t'] ?: 0;
}
$chart_labels = [];
$chart_values = [];
for ($i = 13; $i >= 0; $i--) {
    $d = date('Y-m-d', strtotime("-$i days"));
    $chart_labels[] = $d;
    $chart_values[] = isset($chart_data[$d]) ? (float)$chart_data[$d] : 0;
}

// --- Pagination ---
$page    = max(1, (int)($_GET['page'] ?? 1));
$perPage = 35;
$offset  = ($page - 1) * $perPage;

// --- Total Rows ---
$count_sql  = "SELECT COUNT(*) FROM payments $where_sql";
$count_stmt = $pdo->prepare($count_sql);
$count_stmt->execute($params);
$totalRows  = (int)$count_stmt->fetchColumn();
$totalPages = max(1, (int)ceil($totalRows / $perPage));

// --- Payment Rows ---
$data_sql  = "SELECT * FROM payments $where_sql ORDER BY paid_at DESC LIMIT $perPage OFFSET $offset";
$data_stmt = $pdo->prepare($data_sql);
$data_stmt->execute($params);
$payments  = $data_stmt->fetchAll(PDO::FETCH_ASSOC);

// --- Methods for dropdown ---
$methods = [];
foreach ($pdo->query("SELECT DISTINCT payment_method FROM payments WHERE payment_method IS NOT NULL AND payment_method <> '' ORDER BY payment_method ASC") as $row) {
    $methods[] = $row['payment_method'];
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Payment Logs</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: #f4f6f8; font-size: 0.95rem; }
        main.container { max-width: 1200px; }
        .mini-card { border: 1px solid #e1e4e8; border-radius: 8px; background: #fff; padding: 0.75rem 0.85rem; }
        .mini-card .label { font-size: 0.8rem; color: #6c757d; }
        .mini-card .value { font-size: 1.05rem; font-weight: 600; margin-top: 0.1rem; }
        .mini-card.bg-grand { background: #fff8e1; border-color: #ffe4a3; }
        .mini-card.bg-range  { background: #e1f8e7; border-color: #a3ffb3; }
        .filter-card { border-radius: 8px; border: 1px solid #e1e4e8; background: #ffffff; padding: 0.75rem 0.9rem; }
        .filter-label { font-size: 0.8rem; color: #6c757d; margin-bottom: 0.15rem; }
        .quick-range button { font-size: 0.75rem; padding: 0.2rem 0.5rem; }
        .table-wrapper { border-radius: 8px; border: 1px solid #e1e4e8; background: #ffffff; overflow: hidden; }
        table thead th { background: #f8f9fa; font-size: 0.8rem; white-space: nowrap; }
        table tbody td { font-size: 0.8rem; }
        .sortable { cursor: pointer; }
        .sortable span { font-size: 0.7rem; color: #6c757d; }
        .payment-card { border-radius: 8px; border: 1px solid #e1e4e8; background: #ffffff; }
        .payment-card .label { font-weight: 500; }
        .pagination .page-link { font-size: 0.85rem; }
    </style>
</head>
<body>
<main class="container py-3">
    <h2 class="mb-0 fw-bold text-primary"><i class="fas fa-file-invoice-dollar"></i> Payment Logs</h2> <br>

    <!-- SUMMARY CARDS -->
    <div class="row g-2 mb-3">
        <div class="col-6 col-lg-2">
            <div class="mini-card bg-grand">
                <div class="label">Grand Total</div>
                <div class="value">₱<?= number_format($grand_total, 2) ?></div>
            </div>
        </div>
        <div class="col-6 col-lg-2">
            <div class="mini-card bg-range">
                <div class="label">Sales (date range)</div>
                <div class="value">₱<?= number_format($filtered_range_total, 2) ?></div>
            </div>
        </div>
        <div class="col-6 col-lg-2">
            <div class="mini-card">
                <div class="label">Today (filtered)</div>
                <div class="value">₱<?= number_format($total_today, 2) ?></div>
            </div>
        </div>
        <div class="col-6 col-lg-2">
            <div class="mini-card">
                <div class="label">Yesterday (filtered)</div>
                <div class="value">₱<?= number_format($total_yesterday, 2) ?></div>
            </div>
        </div>
        <div class="col-6 col-lg-2">
            <div class="mini-card">
                <div class="label">This Week (filtered)</div>
                <div class="value">₱<?= number_format($total_week, 2) ?></div>
            </div>
        </div>
        <div class="col-6 col-lg-2">
            <div class="mini-card">
                <div class="label">This Month (filtered)</div>
                <div class="value">₱<?= number_format($total_month, 2) ?></div>
            </div>
        </div>
        <div class="col-6 col-lg-2">
            <div class="mini-card">
                <div class="label">This Year (filtered)</div>
                <div class="value">₱<?= number_format($total_year, 2) ?></div>
            </div>
        </div>
    </div>
    <!-- ... rest of your code is unchanged ... -->





    <!-- FILTERS -->
    <div class="filter-card mb-3">
        <form method="get" class="row g-2 align-items-end">
            <div class="col-12 col-md-2">
                <div class="filter-label">From</div>
                <input type="date" name="from" value="<?= htmlspecialchars($filter_from) ?>" class="form-control form-control-sm">
            </div>
            <div class="col-12 col-md-2">
                <div class="filter-label">To</div>
                <input type="date" name="to" value="<?= htmlspecialchars($filter_to) ?>" class="form-control form-control-sm">
            </div>
            <div class="col-12 col-md-2">
                <div class="filter-label">Search (Username or Reference)</div>
                <input type="text" name="search" value="<?= htmlspecialchars($filter_search) ?>" class="form-control form-control-sm" placeholder="e.g. juan or REF123">
            </div>
            <div class="col-6 col-md-2">
                <div class="filter-label">Username (contains)</div>
                <input type="text" name="username" value="<?= htmlspecialchars($filter_username) ?>" class="form-control form-control-sm">
            </div>
            <div class="col-6 col-md-2">
                <div class="filter-label">Adjusted By (contains)</div>
                <input type="text" name="adjusted_by" value="<?= htmlspecialchars($filter_adjusted_by) ?>" class="form-control form-control-sm">
            </div>
            <div class="col-6 col-md-2">
                <div class="filter-label">Method</div>
                <select name="method" class="form-select form-select-sm">
                    <option value="">All Methods</option>
                    <?php foreach ($methods as $m): ?>
                        <option value="<?= htmlspecialchars($m) ?>" <?= $filter_method === $m ? 'selected' : '' ?>>
                            <?= htmlspecialchars($m) ?>
                        </option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="col-12 col-md-2 d-grid">
                <button type="submit" class="btn btn-primary btn-sm">Apply</button>
            </div>
            <div class="col-12 col-md-2 d-grid">
                <a href="?" class="btn btn-outline-secondary btn-sm">Clear</a>
            </div>
            <div class="col-12 col-md-2 d-grid">
                <a href="<?= htmlspecialchars($_SERVER['PHP_SELF'] . '?' . http_build_query(array_merge($_GET, ['export' => 'csv']))) ?>"
                   class="btn btn-success btn-sm">
                    <i class="bi bi-file-earmark-excel"></i> Export to Excel
                </a>
            </div>
            <div class="col-12 mt-2 d-flex flex-wrap align-items-center justify-content-between">
                <div class="quick-range btn-group btn-group-sm" role="group">
                    <?php
                    $baseParams = [
                        'from'     => $filter_from,
                        'to'       => $filter_to,
                        'search'   => $filter_search,
                        'method'   => $filter_method,
                        'username' => $filter_username,
                        'adjusted_by' => $filter_adjusted_by,
                    ];
                    function quickUrl($range, $baseParams) {
                        $baseParams['range'] = $range;
                        return '?' . http_build_query($baseParams);
                    }
                    ?>
                    <a href="<?= quickUrl('today', $baseParams) ?>" class="btn btn-outline-secondary <?= $quick_range==='today' ? 'active' : '' ?>">Today</a>
                    <a href="<?= quickUrl('week',  $baseParams) ?>" class="btn btn-outline-secondary <?= $quick_range==='week'  ? 'active' : '' ?>">This Week</a>
                    <a href="<?= quickUrl('month', $baseParams) ?>" class="btn btn-outline-secondary <?= $quick_range==='month' ? 'active' : '' ?>">This Month</a>
                    <a href="<?= quickUrl('year',  $baseParams) ?>" class="btn btn-outline-secondary <?= $quick_range==='year'  ? 'active' : '' ?>">This Year</a>
                </div>
                <div class="d-flex gap-1">
                    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="location.reload()">Refresh</button>
                    <a href="rebates_logs.php" class="btn btn-outline-secondary btn-sm" title="Rebates/Re-adjustments logs">
                        <i class="bi bi-cash-coin"></i>
                    </a>
                </div>
            </div>
        </form>
    </div>

    <!-- CHART -->
    <div class="mb-3 p-3 bg-white border border-1 border-light rounded-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="mb-0">Last 14 Days (filtered)</h6>
            <small class="text-muted">Daily total amount</small>
        </div>
        <canvas id="salesChart" height="70"></canvas>
    </div>

    <!-- TABLE + MOBILE CARDS -->
    <div class="mb-2 d-flex justify-content-between align-items-center">
        <h5 class="mb-0">Payment Logs</h5>
        <small class="text-muted"><?= $totalRows ?> records found</small>
    </div>

    <!-- Desktop table -->
    <div class="table-wrapper d-none d-md-block mb-3">
        <div class="table-responsive">
            <table class="table table-sm table-hover mb-0">
                <thead>
                    <tr>
                        <th class="sortable" data-sort="created_at">Created<span> ▲▼</span></th>
                        <th class="sortable" data-sort="username">Username<span> ▲▼</span></th>
                        <th>Plan</th>
                        <th class="sortable" data-sort="amount">Amount<span> ▲▼</span></th>
                        <th>Days</th>
                        <th>Expires At</th>
                        <th class="sortable" data-sort="paid_at">Paid At<span> ▲▼</span></th>
                        <th class="sortable" data-sort="payment_date_received">Payment Date Received<span> ▲▼</span></th>
                        <th>Adjusted By</th>
                        <th>Method</th>
                        <th>Reference</th>
                        <th>Amount Adjusted (Reason)</th>
                    </tr>
                </thead>
                <tbody id="paymentsTableBody">
                    <?php if ($payments): ?>
                        <?php foreach ($payments as $row): ?>
                            <tr>
                                <td data-created_at="<?= htmlspecialchars($row['created_at'] ?? '') ?>">
                                    <?= htmlspecialchars($row['created_at'] ?? '') ?>
                                </td>
                                <td data-username="<?= htmlspecialchars($row['username'] ?? '') ?>">
                                    <span class="fw-semibold text-primary"><?= htmlspecialchars($row['username'] ?? '') ?></span>
                                </td>
                                <td><?= htmlspecialchars($row['plan_name'] ?? '') ?></td>
                                <td data-amount="<?= (float)($row['amount'] ?? 0) ?>">
                                    ₱<?= number_format($row['amount'] ?? 0, 2) ?>
                                </td>
                                <td><?= (int)($row['days'] ?? 0) ?></td>
                                <td><?= htmlspecialchars($row['expires_at'] ?? '') ?></td>
                                <td data-paid_at="<?= htmlspecialchars($row['paid_at'] ?? '') ?>">
                                    <?= htmlspecialchars($row['paid_at'] ?? '') ?>
                                </td>
                                <td data-payment_date_received="<?= htmlspecialchars($row['payment_date_received'] ?? '') ?>">
                                    <?= htmlspecialchars($row['payment_date_received'] ?? '') ?>
                                </td>
                                <td>
                                    <?php if (!empty($row['adjusted_by'])): ?>
                                        <span class="badge text-bg-light"><?= htmlspecialchars($row['adjusted_by'] ?? '') ?></span>
                                    <?php else: ?>
                                        <span class="text-muted">-</span>
                                    <?php endif; ?>
                                </td>
                                <td><?= htmlspecialchars($row['payment_method'] ?? '') ?></td>
                                <td><code><?= htmlspecialchars($row['reference_no'] ?? '') ?></code></td>
                                <td><?= htmlspecialchars($row['reason'] ?? '') ?></td>
                            </tr>
                        <?php endforeach; ?>
                    <?php else: ?>
                        <tr>
                            <td colspan="13" class="text-center text-muted py-3">No payments found.</td>
                        </tr>
                    <?php endif; ?>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Mobile card view -->
    <div class="d-md-none mb-3">
        <?php if ($payments): ?>
            <?php foreach ($payments as $row): ?>
                <div class="payment-card mb-2 p-2">
                    <div><span class="label">Created:</span> <?= htmlspecialchars($row['created_at'] ?? '') ?></div>
                    <div><span class="label">Username:</span> <?= htmlspecialchars($row['username'] ?? '') ?></div>
                    <div><span class="label">Plan:</span> <?= htmlspecialchars($row['plan_name'] ?? '') ?></div>
                    <div><span class="label">Amount:</span> ₱<?= number_format($row['amount'] ?? 0, 2) ?></div>
                    <div><span class="label">Adj. Reason:</span> <?= htmlspecialchars($row['reason'] ?? '') ?></div>
                    <div><span class="label">Days:</span> <?= (int)($row['days'] ?? 0) ?></div>
                    <div><span class="label">Expires:</span> <?= htmlspecialchars($row['expires_at'] ?? '') ?></div>
                    <div><span class="label">Paid At:</span> <?= htmlspecialchars($row['paid_at'] ?? '') ?></div>
                    <div><span class="label">Payment Date Received:</span> <?= htmlspecialchars($row['payment_date_received'] ?? '') ?></div>
                    <div>
                        <span class="label">Adjusted By:</span>
                        <?php if (!empty($row['adjusted_by'])): ?>
                            <?= htmlspecialchars($row['adjusted_by'] ?? '') ?>
                        <?php else: ?>
                            <span class="text-muted">-</span>
                        <?php endif; ?>
                    </div>
                    <div><span class="label">Method:</span> <?= htmlspecialchars($row['payment_method'] ?? '') ?></div>
                    <div><span class="label">Reference:</span> <code><?= htmlspecialchars($row['reference_no'] ?? '') ?></code></div>
                    <?php if (!empty($row['latitude']) && !empty($row['longitude'])): ?>
                        <div class="mt-1">
                            <a href="https://www.google.com/maps?q=<?= urlencode($row['latitude']) ?>,<?= urlencode($row['longitude']) ?>" target="_blank">
                                View on map
                            </a>
                            <br>
                            <small class="text-muted">
                                <?= htmlspecialchars($row['latitude']) ?>, <?= htmlspecialchars($row['longitude']) ?>
                            </small>
                        </div>
                    <?php endif; ?>
                </div>
            <?php endforeach; ?>
        <?php else: ?>
            <div class="alert alert-info text-center">No payments found.</div>
        <?php endif; ?>
    </div>

    <!-- Pagination -->
    <nav aria-label="Payments pagination">
        <ul class="pagination pagination-sm justify-content-center mb-0">
            <?php
            $qs = function($pageNum) use ($filter_from, $filter_to, $filter_search, $filter_method, $filter_username, $filter_adjusted_by, $quick_range) {
                $params = [
                    'page'     => $pageNum,
                    'from'     => $filter_from,
                    'to'       => $filter_to,
                    'search'   => $filter_search,
                    'method'   => $filter_method,
                    'username' => $filter_username,
                    'adjusted_by' => $filter_adjusted_by,
                    'range'    => $quick_range,
                ];
                return '?' . http_build_query(array_filter($params, fn($v) => $v !== ''));
            };
            ?>
            <?php if ($page > 1): ?>
                <li class="page-item">
                    <a class="page-link" href="<?= $qs($page - 1) ?>" aria-label="Previous">&laquo;</a>
                </li>
            <?php endif; ?>
            <?php
            $startPage = max(1, $page - 2);
            $endPage   = min($totalPages, $page + 2);
            for ($i = $startPage; $i <= $endPage; $i++): ?>
                <li class="page-item <?= ($i == $page) ? 'active' : '' ?>">
                    <a class="page-link" href="<?= $qs($i) ?>"><?= $i ?></a>
                </li>
            <?php endfor; ?>
            <?php if ($page < $totalPages): ?>
                <li class="page-item">
                    <a class="page-link" href="<?= $qs($page + 1) ?>" aria-label="Next">&raquo;</a>
                </li>
            <?php endif; ?>
        </ul>
    </nav>
</main>

<script>
// Simple Chart.js line chart
const ctx = document.getElementById('salesChart').getContext('2d');
const chartLabels = <?= json_encode($chart_labels) ?>;
const chartValues = <?= json_encode($chart_values) ?>;
new Chart(ctx, {
    type: 'line',
    data: {
        labels: chartLabels,
        datasets: [{
            label: 'Sales (₱)',
            data: chartValues,
            borderColor: 'rgba(13, 110, 253, 1)',
            backgroundColor: 'rgba(13, 110, 253, 0.05)',
            tension: 0.25,
            pointRadius: 2,
            borderWidth: 1.5
        }]
    },
    options: {
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 7 }
            },
            y: { beginAtZero: true }
        }
    }
});

// Simple client-side sorting on current page (for a few columns)
(function() {
    const tableBody = document.getElementById('paymentsTableBody');
    if (!tableBody) return;

    const getCellValue = (row, sortKey) => {
        const td = row.querySelector(`[data-${sortKey}]`);
        if (!td) return '';
        if (sortKey === 'amount') return parseFloat(td.getAttribute('data-amount') || '0');
        return td.getAttribute(`data-${sortKey}`) || '';
    };

    document.querySelectorAll('th.sortable').forEach(th => {
        let asc = true;
        th.addEventListener('click', () => {
            const sortKey = th.getAttribute('data-sort');
            const rows = Array.from(tableBody.querySelectorAll('tr'));
            rows.sort((a, b) => {
                const va = getCellValue(a, sortKey);
                const vb = getCellValue(b, sortKey);
                if (typeof va === 'number' && typeof vb === 'number') {
                    return asc ? va - vb : vb - va;
                }
                return asc ? va.localeCompare(vb) : vb.localeCompare(va);
            });
            rows.forEach(r => tableBody.appendChild(r));
            asc = !asc;
        });
    });
})();
</script>
<?php include 'footer.php'; ?>
</body>
</html>
