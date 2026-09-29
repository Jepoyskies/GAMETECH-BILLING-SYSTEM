<?php
// payment_cignal_logs.php  (TABLE: cignal_play)
require 'database.php';
include 'header.php';

if (session_status() === PHP_SESSION_NONE) session_start();

$notification = '';
if (!empty($_SESSION['notification'])) {
    $notification = $_SESSION['notification'];
    unset($_SESSION['notification']);
}

function dt_range_from_preset(string $preset): array {
    $tz = new DateTimeZone(date_default_timezone_get() ?: 'UTC');
    $now = new DateTime('now', $tz);

    $start = null; $end = null;

    switch ($preset) {
        case 'today':
            $start = (clone $now)->setTime(0,0,0);
            $end   = (clone $now)->setTime(23,59,59);
            break;
        case 'yesterday':
            $y = (clone $now)->modify('-1 day');
            $start = (clone $y)->setTime(0,0,0);
            $end   = (clone $y)->setTime(23,59,59);
            break;
        case 'week': // Mon-Sun
            $start = (clone $now)->modify('monday this week')->setTime(0,0,0);
            $end   = (clone $now)->modify('sunday this week')->setTime(23,59,59);
            break;
        case 'month':
            $start = (clone $now)->modify('first day of this month')->setTime(0,0,0);
            $end   = (clone $now)->modify('last day of this month')->setTime(23,59,59);
            break;
        case 'year':
            $start = (clone $now)->setDate((int)$now->format('Y'), 1, 1)->setTime(0,0,0);
            $end   = (clone $now)->setDate((int)$now->format('Y'), 12, 31)->setTime(23,59,59);
            break;
        default:
            return [null, null];
    }
    return [$start->format('Y-m-d H:i:s'), $end->format('Y-m-d H:i:s')];
}

function q(array $add = []): string {
    return http_build_query(array_merge($_GET, $add));
}

$search = isset($_GET['search']) ? trim($_GET['search']) : '';

$preset = $_GET['preset'] ?? ''; // today|yesterday|week|month|year
$start_date = $_GET['start_date'] ?? '';
$end_date   = $_GET['end_date'] ?? '';

if ($preset !== '') {
    [$s, $e] = dt_range_from_preset($preset);
    if ($s && $e) {
        $start_date = substr($s, 0, 10);
        $end_date   = substr($e, 0, 10);
    }
}

$page = (isset($_GET['page']) && ctype_digit((string)$_GET['page']) && (int)$_GET['page'] > 0) ? (int)$_GET['page'] : 1;
$per_page = (isset($_GET['per_page']) && ctype_digit((string)$_GET['per_page'])) ? max(10, min(200, (int)$_GET['per_page'])) : 25;

$sort_by = $_GET['sort_by'] ?? 'created_at';
$sort_order = strtolower($_GET['sort_order'] ?? 'desc') === 'asc' ? 'asc' : 'desc';

$allowed_sort_cols = [
    'id','customer_id','subscriber_no','plan_name','rates','quantity_cignal','created_at',
    'payment_method','admin_username','payment_date','reference_no','amount',
    'start_date','end_date'
];
if (!in_array($sort_by, $allowed_sort_cols, true)) $sort_by = 'created_at';

$conds = [];
$params = [];

// Date filter uses payment_date
if ($start_date !== '') {
    $conds[] = "l.payment_date >= :start_date";
    $params[':start_date'] = $start_date . " 00:00:00";
}
if ($end_date !== '') {
    $conds[] = "l.payment_date <= :end_date";
    $params[':end_date'] = $end_date . " 23:59:59";
}

if ($search !== '') {
    $hay = '%' . strtolower($search) . '%';
    $conds[] = "("
        . "LOWER(COALESCE(l.subscriber_no,'')) LIKE :hay OR "
        . "LOWER(COALESCE(l.plan_name,'')) LIKE :hay OR "
        . "LOWER(COALESCE(l.payment_method,'')) LIKE :hay OR "
        . "LOWER(COALESCE(l.reference_no,'')) LIKE :hay OR "
        . "LOWER(COALESCE(a.username,'')) LIKE :hay OR "
        . "CAST(l.id AS CHAR) LIKE :hay OR "
        . "CAST(l.customer_id AS CHAR) LIKE :hay"
        . ")";
    $params[':hay'] = $hay;
}

$whereSql = $conds ? (" WHERE " . implode(" AND ", $conds)) : "";

// FROM
$fromSql = "
    FROM cignal_play l
    LEFT JOIN admins a ON a.id = l.admin_id
";

$amountExpr = "(COALESCE(l.rates,0) * COALESCE(l.quantity_cignal,0))";

$selectSql = "
    SELECT
        l.id,
        l.customer_id,
        l.subscriber_no,
        l.plan_name,
        l.rates,
        l.quantity_cignal,
        l.created_at,
        l.payment_method,
        l.admin_id,
        COALESCE(a.username,'') AS admin_username,
        l.payment_date,
        l.reference_no,
        l.start_date,
        l.end_date,
        $amountExpr AS amount
    $fromSql
    $whereSql
";

$orderBySql = ($sort_by === 'admin_username')
    ? " ORDER BY admin_username " . strtoupper($sort_order)
    : (($sort_by === 'amount')
        ? " ORDER BY $amountExpr " . strtoupper($sort_order)
        : " ORDER BY l.$sort_by " . strtoupper($sort_order));

$offset = ($page - 1) * $per_page;

// Export Excel (CSV readable by Excel)
if (isset($_GET['export']) && $_GET['export'] === '1') {
    $exportSql = $selectSql . $orderBySql;
    $stmt = $conn->prepare($exportSql);
    foreach ($params as $k => $v) $stmt->bindValue($k, $v, PDO::PARAM_STR);
    $stmt->execute();

    $filename = "cignal_payment_logs_" . date('Y-m-d_H-i-s') . ".csv";
    header('Content-Type: text/csv; charset=utf-8');
    header("Content-Disposition: attachment; filename=\"$filename\"");
    header('Pragma: no-cache');
    header('Expires: 0');

    $out = fopen('php://output', 'w');
    fputcsv($out, [
        'id','customer_id','subscriber_no','plan_name','rates','quantity_cignal',
        'amount','created_at','payment_method','admin_username','payment_date','reference_no',
        'start_date','end_date'
    ]);

    while ($r = $stmt->fetch(PDO::FETCH_ASSOC)) {
        fputcsv($out, [
            $r['id'],
            $r['customer_id'],
            $r['subscriber_no'],
            $r['plan_name'],
            $r['rates'],
            $r['quantity_cignal'],
            $r['amount'],
            $r['created_at'],
            $r['payment_method'],
            $r['admin_username'],
            $r['payment_date'],
            $r['reference_no'],
            $r['start_date'],
            $r['end_date'],
        ]);
    }
    fclose($out);
    exit;
}

// List rows
$listSql = $selectSql . $orderBySql . " LIMIT :limit OFFSET :offset";
$stmt = $conn->prepare($listSql);
foreach ($params as $k => $v) $stmt->bindValue($k, $v, PDO::PARAM_STR);
$stmt->bindValue(':limit', (int)$per_page, PDO::PARAM_INT);
$stmt->bindValue(':offset', (int)$offset, PDO::PARAM_INT);
$stmt->execute();
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

// Count
$countSql = "SELECT COUNT(*) $fromSql $whereSql";
$countStmt = $conn->prepare($countSql);
foreach ($params as $k => $v) $countStmt->bindValue($k, $v, PDO::PARAM_STR);
$countStmt->execute();
$total_rows = (int)$countStmt->fetchColumn();
$total_pages = max(1, (int)ceil($total_rows / $per_page));

// Grand total (filtered)
$totalSql = "SELECT COALESCE(SUM($amountExpr),0) AS grand_total $fromSql $whereSql";
$totalStmt = $conn->prepare($totalSql);
foreach ($params as $k => $v) $totalStmt->bindValue($k, $v, PDO::PARAM_STR);
$totalStmt->execute();
$grand_total_filtered = (float)$totalStmt->fetchColumn();

function quick_total(PDO $conn, string $fromSql, string $amountExpr, string $search, string $preset): float {
    [$s, $e] = dt_range_from_preset($preset);
    $conds = [];
    $params = [];

    if ($s && $e) {
        $conds[] = "l.payment_date >= :s AND l.payment_date <= :e";
        $params[':s'] = $s;
        $params[':e'] = $e;
    }

    if ($search !== '') {
        $hay = '%' . strtolower($search) . '%';
        $conds[] = "("
            . "LOWER(COALESCE(l.subscriber_no,'')) LIKE :hay OR "
            . "LOWER(COALESCE(l.plan_name,'')) LIKE :hay OR "
            . "LOWER(COALESCE(l.payment_method,'')) LIKE :hay OR "
            . "LOWER(COALESCE(l.reference_no,'')) LIKE :hay OR "
            . "LOWER(COALESCE(a.username,'')) LIKE :hay OR "
            . "CAST(l.id AS CHAR) LIKE :hay OR "
            . "CAST(l.customer_id AS CHAR) LIKE :hay"
            . ")";
        $params[':hay'] = $hay;
    }

    $where = $conds ? (" WHERE " . implode(" AND ", $conds)) : "";
    $sql = "SELECT COALESCE(SUM($amountExpr),0) $fromSql $where";
    $st = $conn->prepare($sql);
    foreach ($params as $k => $v) $st->bindValue($k, $v, PDO::PARAM_STR);
    $st->execute();
    return (float)$st->fetchColumn();
}

$tot_today = quick_total($conn, $fromSql, $amountExpr, $search, 'today');
$tot_yesterday = quick_total($conn, $fromSql, $amountExpr, $search, 'yesterday');
$tot_week = quick_total($conn, $fromSql, $amountExpr, $search, 'week');
$tot_month = quick_total($conn, $fromSql, $amountExpr, $search, 'month');
$tot_year = quick_total($conn, $fromSql, $amountExpr, $search, 'year');

/**
 * Last 14 days chart (ALWAYS last 14 days; respects current SEARCH filter only)
 * If you want it to also respect start/end date filter, tell me.
 */
function last14_series(PDO $conn, string $search, string $fromSql, string $amountExpr): array {
    $tz = new DateTimeZone(date_default_timezone_get() ?: 'UTC');
    $today = new DateTime('today', $tz);
    $start = (clone $today)->modify('-13 days')->setTime(0,0,0);
    $end   = (clone $today)->setTime(23,59,59);

    $conds = [];
    $params = [
        ':s' => $start->format('Y-m-d H:i:s'),
        ':e' => $end->format('Y-m-d H:i:s'),
    ];

    // fixed range for last 14 days
    $conds[] = "l.payment_date >= :s AND l.payment_date <= :e";

    if ($search !== '') {
        $hay = '%' . strtolower($search) . '%';
        $conds[] = "("
            . "LOWER(COALESCE(l.subscriber_no,'')) LIKE :hay OR "
            . "LOWER(COALESCE(l.plan_name,'')) LIKE :hay OR "
            . "LOWER(COALESCE(l.payment_method,'')) LIKE :hay OR "
            . "LOWER(COALESCE(l.reference_no,'')) LIKE :hay OR "
            . "LOWER(COALESCE(a.username,'')) LIKE :hay OR "
            . "CAST(l.id AS CHAR) LIKE :hay OR "
            . "CAST(l.customer_id AS CHAR) LIKE :hay"
            . ")";
        $params[':hay'] = $hay;
    }

    $where = " WHERE " . implode(" AND ", $conds);

    // MySQL: DATE(l.payment_date)
    $sql = "
        SELECT DATE(l.payment_date) AS d, COALESCE(SUM($amountExpr),0) AS total
        $fromSql
        $where
        GROUP BY DATE(l.payment_date)
        ORDER BY d ASC
    ";
    $st = $conn->prepare($sql);
    foreach ($params as $k => $v) $st->bindValue($k, $v, PDO::PARAM_STR);
    $st->execute();
    $map = [];
    while ($r = $st->fetch(PDO::FETCH_ASSOC)) {
        $map[$r['d']] = (float)$r['total'];
    }

    $labels = [];
    $values = [];
    for ($i = 0; $i < 14; $i++) {
        $day = (clone $start)->modify("+$i day");
        $key = $day->format('Y-m-d');
        $labels[] = $day->format('M d');
        $values[] = $map[$key] ?? 0.0;
    }
    return [$labels, $values];
}

[$chart_labels, $chart_values] = last14_series($conn, $search, $fromSql, $amountExpr);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>Cignal Payment Logs</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet" />
    <style>
        :root{
            --brand:#0d6efd;
            --soft:#f6f9ff;
            --card:#ffffff;
            --border:#e7eef8;
            --muted:#64748b;
        }
        body{ background: linear-gradient(180deg, var(--soft), #fff); }

        /* Use full width so the table can fit */
        .container{ max-width: 100% !important; }

        .shell{ background:var(--card); border:1px solid var(--border); border-radius:16px; }
        .page-header{
            background: radial-gradient(1200px 300px at 10% 0%, rgba(13,110,253,.18), transparent 60%),
                        radial-gradient(900px 240px at 90% 10%, rgba(25,135,84,.12), transparent 55%),
                        #fff;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px;
        }
        .metric{
            background:#fff;
            border:1px solid var(--border);
            border-radius:16px;
            padding:12px 12px;
            height:100%;
        }
        .metric .label{ color:var(--muted); font-size:.82rem; }
        .metric .value{ font-weight:800; font-size:1.05rem; }
        .metric .icon{
            width:34px;height:34px;border-radius:12px;
            display:flex;align-items:center;justify-content:center;
            background: rgba(13,110,253,.1); color: var(--brand);
        }

        .table-shell{ border:1px solid var(--border); border-radius:16px; overflow:hidden; background:#fff; }

        /* Make wide tables fit: horizontal scroll + tighter cells + sticky header */
        .table-responsive{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .table{
            margin-bottom:0;
            table-layout: auto;
        }
        .table thead th{
            position: sticky;
            top: 0;
            z-index: 2;
            font-size:.78rem; letter-spacing:.02em; text-transform:uppercase;
            background:#f8fafc; color:#334155;
            border-bottom:1px solid var(--border) !important;
            vertical-align: middle;
            white-space: nowrap;
        }
        .table td{
            vertical-align: middle;
            white-space: nowrap;
            padding: .45rem .5rem;
            font-size: .9rem;
        }
        th.sortable { cursor:pointer; }
        th.sorted-asc::after { content:" \25B2"; }
        th.sorted-desc::after { content:" \25BC"; }

        .btn, .form-control, .form-select { border-radius: 12px; }
        .muted{ color:var(--muted); }
        .badge{ border-radius:999px; }
        .card-mobile{ border:1px solid var(--border); border-radius:16px; overflow:hidden; }
        .card-mobile .card-header{ background:#f8fafc; border-bottom:1px solid var(--border); }
        .money{ font-variant-numeric: tabular-nums; }

        /* chart */
        .chart-shell{
            background:#fff;border:1px solid var(--border);
            border-radius:16px;padding:14px;
        }

        /* On very large screens, reduce side padding so more table fits */
        @media (min-width: 992px){
            main.container{ padding-left: 12px; padding-right: 12px; }
        }
    </style>
</head>
<body>
<main class="container py-4">

    <div class="page-header mb-3 shadow-sm">
        <div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-2">
            <div>
                <div class="d-flex align-items-center gap-2">
                    <span class="d-inline-flex align-items-center justify-content-center rounded-3"
                          style="width:40px;height:40px;background:rgba(13,110,253,.1);color:var(--brand);">
                        <i class="fa-solid fa-receipt"></i>
                    </span>
                    <div>
                        <h3 class="mb-0 fw-bold text-primary">Cignal Payment Logs</h3>
                        <div class="muted small">View, filter, and export payment transactions.</div>
                    </div>
                </div>
            </div>
            <div class="d-flex gap-2">
                <a href="cignal_play.php" class="btn btn-outline-secondary">
                    <i class="fa-solid fa-arrow-left me-1"></i>Back
                </a>
                <a href="?<?= q(['export'=>'1','page'=>1]) ?>" class="btn btn-outline-primary">
                    <i class="fa-solid fa-file-export me-1"></i>Export CSV
                </a>
            </div>
        </div>
    </div>

    <?php if ($notification): ?>
        <div class="alert alert-info border-0 shadow-sm"><?= htmlspecialchars($notification) ?></div>
    <?php endif; ?>

    <!-- Graph: Last 14 days (filtered by search) -->
    <div class="chart-shell shadow-sm mb-3">
        <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
            <div class="fw-bold text-primary">
                <i class="fa-solid fa-chart-line me-1"></i>Last 14 Days (filtered)
            </div>
            <div class="small muted">
                Based on payment_date • Search filter: <?= $search !== '' ? '<strong>'.htmlspecialchars($search).'</strong>' : '<span class="badge text-bg-light border">none</span>' ?>
            </div>
        </div>
        <div style="height:240px">
            <canvas id="last14Chart"></canvas>
        </div>
    </div>

    <div class="row g-2 mb-3">
        <div class="col-6 col-lg">
            <div class="metric shadow-sm">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <div class="label">Grand Total (filtered)</div>
                        <div class="value money">₱<?= number_format($grand_total_filtered, 2) ?></div>
                    </div>
                    <div class="icon"><i class="fa-solid fa-coins"></i></div>
                </div>
            </div>
        </div>
        <div class="col-6 col-lg">
            <a class="text-decoration-none text-dark" href="?<?= q(['preset'=>'today','page'=>1]) ?>">
                <div class="metric shadow-sm">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="label">Today</div>
                            <div class="value money">₱<?= number_format($tot_today, 2) ?></div>
                        </div>
                        <div class="icon"><i class="fa-solid fa-calendar-day"></i></div>
                    </div>
                </div>
            </a>
        </div>
        <div class="col-6 col-lg">
            <a class="text-decoration-none text-dark" href="?<?= q(['preset'=>'yesterday','page'=>1]) ?>">
                <div class="metric shadow-sm">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="label">Yesterday</div>
                            <div class="value money">₱<?= number_format($tot_yesterday, 2) ?></div>
                        </div>
                        <div class="icon"><i class="fa-solid fa-calendar-minus"></i></div>
                    </div>
                </div>
            </a>
        </div>
        <div class="col-6 col-lg">
            <a class="text-decoration-none text-dark" href="?<?= q(['preset'=>'week','page'=>1]) ?>">
                <div class="metric shadow-sm">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="label">This Week</div>
                            <div class="value money">₱<?= number_format($tot_week, 2) ?></div>
                        </div>
                        <div class="icon"><i class="fa-solid fa-calendar-week"></i></div>
                    </div>
                </div>
            </a>
        </div>
        <div class="col-6 col-lg">
            <a class="text-decoration-none text-dark" href="?<?= q(['preset'=>'month','page'=>1]) ?>">
                <div class="metric shadow-sm">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="label">This Month</div>
                            <div class="value money">₱<?= number_format($tot_month, 2) ?></div>
                        </div>
                        <div class="icon"><i class="fa-solid fa-calendar"></i></div>
                    </div>
                </div>
            </a>
        </div>
        <div class="col-6 col-lg">
            <a class="text-decoration-none text-dark" href="?<?= q(['preset'=>'year','page'=>1]) ?>">
                <div class="metric shadow-sm">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="label">This Year</div>
                            <div class="value money">₱<?= number_format($tot_year, 2) ?></div>
                        </div>
                        <div class="icon"><i class="fa-solid fa-calendar-check"></i></div>
                    </div>
                </div>
            </a>
        </div>
    </div>

    <div class="shell p-3 mb-3 shadow-sm">
        <form method="get" class="row g-2 align-items-end">
            <input type="hidden" name="sort_by" value="<?= htmlspecialchars($sort_by) ?>">
            <input type="hidden" name="sort_order" value="<?= htmlspecialchars($sort_order) ?>">

            <div class="col-12 col-lg-5">
                <label class="form-label small muted mb-1">Search</label>
                <div class="input-group">
                    <span class="input-group-text bg-white"><i class="fa fa-search text-secondary"></i></span>
                    <input type="text" name="search" class="form-control"
                           placeholder="subscriber, plan, reference, admin, customer id..."
                           value="<?= htmlspecialchars($search) ?>">
                </div>
            </div>

            <div class="col-6 col-lg-2">
                <label class="form-label small muted mb-1">Start date</label>
                <input type="date" name="start_date" class="form-control" value="<?= htmlspecialchars($start_date) ?>">
            </div>
            <div class="col-6 col-lg-2">
                <label class="form-label small muted mb-1">End date</label>
                <input type="date" name="end_date" class="form-control" value="<?= htmlspecialchars($end_date) ?>">
            </div>

            <div class="col-6 col-lg-1">
                <label class="form-label small muted mb-1">Per page</label>
                <select name="per_page" class="form-select" onchange="this.form.submit()">
                    <option value="25"<?= $per_page==25?' selected':'' ?>>25</option>
                    <option value="50"<?= $per_page==50?' selected':'' ?>>50</option>
                    <option value="100"<?= $per_page==100?' selected':'' ?>>100</option>
                    <option value="200"<?= $per_page==200?' selected':'' ?>>200</option>
                </select>
            </div>

            <div class="col-6 col-lg-2 d-flex gap-2">
                <button class="btn btn-primary w-100" type="submit">
                    <i class="fa-solid fa-filter me-1"></i>Filter
                </button>
                <a class="btn btn-outline-secondary w-100" href="payment_cignal_logs.php">Reset</a>
            </div>

            <div class="col-12">
                <div class="small muted">
                    Records: <strong><?= number_format($total_rows) ?></strong>
                    <?php if ($start_date || $end_date): ?>
                        <span class="ms-2 badge text-bg-light border">Date filter active</span>
                    <?php endif; ?>
                </div>
            </div>
        </form>
    </div>

    <div class="table-shell shadow-sm">
        <!-- Desktop table -->
        <div class="table-responsive d-none d-md-block">
            <table class="table table-hover table-bordered mb-0">
                <thead>
                    <tr>
                        <?php
                        $cols = [
                            'id' => 'ID',
                            'customer_id' => 'Customer ID',
                            'subscriber_no' => 'Subscriber No',
                            'plan_name' => 'Plan Name',
                            'rates' => 'Rates',
                            'quantity_cignal' => 'Qty',
                            'amount' => 'Amount',
                            'created_at' => 'Created At',
                            'payment_method' => 'Payment Method',
                            'admin_username' => 'Admin',
                            'payment_date' => 'Payment Date',
                            'reference_no' => 'Reference No',
                            'start_date' => 'Start Date',
                            'end_date' => 'End Date',
                        ];

                        foreach ($cols as $col => $label) {
                            $thClass = "text-nowrap sortable";
                            if ($sort_by === $col) $thClass .= " sorted-" . $sort_order;
                            $nextOrder = ($sort_by === $col && $sort_order === 'asc') ? 'desc' : 'asc';
                            $url = '?' . q(['sort_by'=>$col, 'sort_order'=>$nextOrder, 'page'=>1]);
                            echo "<th class=\"$thClass\"><a href=\"$url\" style=\"text-decoration:none;color:inherit;\">$label</a></th>";
                        }
                        ?>
                    </tr>
                </thead>
                <tbody>
                <?php if ($rows): ?>
                    <?php foreach ($rows as $r): ?>
                        <tr>
                            <td><?= htmlspecialchars($r['id']) ?></td>
                            <td><?= htmlspecialchars($r['customer_id']) ?></td>
                            <td><?= htmlspecialchars($r['subscriber_no']) ?></td>
                            <td><?= htmlspecialchars($r['plan_name']) ?></td>
                            <td class="money">₱<?= number_format((float)$r['rates'], 2) ?></td>
                            <td><?= htmlspecialchars($r['quantity_cignal']) ?></td>
                            <td class="money fw-bold">₱<?= number_format((float)$r['amount'], 2) ?></td>
                            <td><?= htmlspecialchars($r['created_at']) ?></td>
                            <td><?= htmlspecialchars($r['payment_method']) ?></td>
                            <td><?= htmlspecialchars($r['admin_username']) ?></td>
                            <td><?= htmlspecialchars($r['payment_date']) ?></td>
                            <td><?= htmlspecialchars($r['reference_no']) ?></td>
                            <td><?= htmlspecialchars($r['start_date']) ?></td>
                            <td><?= htmlspecialchars($r['end_date']) ?></td>
                        </tr>
                    <?php endforeach; ?>
                <?php else: ?>
                    <tr><td colspan="14" class="text-center py-4 muted">No logs found.</td></tr>
                <?php endif; ?>
                </tbody>
            </table>
        </div>

        <!-- Mobile cards -->
        <div class="d-md-none p-2">
            <?php if ($rows): ?>
                <?php foreach ($rows as $r): ?>
                    <div class="card card-mobile mb-3 shadow-sm">
                        <div class="card-header d-flex justify-content-between align-items-center py-2">
                            <div class="fw-bold">Log #<?= htmlspecialchars($r['id']) ?></div>
                            <span class="badge text-bg-light border money">₱<?= number_format((float)$r['amount'], 2) ?></span>
                        </div>
                        <div class="card-body py-2">
                            <div class="small muted mb-2">
                                <strong>Payment:</strong> <?= htmlspecialchars($r['payment_date']) ?>
                            </div>

                            <div><strong>Customer ID:</strong> <?= htmlspecialchars($r['customer_id']) ?></div>
                            <div><strong>Subscriber No:</strong> <?= htmlspecialchars($r['subscriber_no']) ?></div>
                            <div class="mt-1"><strong>Plan:</strong> <?= htmlspecialchars($r['plan_name']) ?></div>

                            <div class="row g-2 mt-1">
                                <div class="col-6"><strong>Rates:</strong> <span class="money">₱<?= number_format((float)$r['rates'], 2) ?></span></div>
                                <div class="col-6"><strong>Qty:</strong> <?= htmlspecialchars($r['quantity_cignal']) ?></div>
                            </div>

                            <div class="mt-1"><strong>Start Date:</strong> <?= htmlspecialchars($r['start_date']) ?></div>
                            <div class="mt-1"><strong>End Date:</strong> <?= htmlspecialchars($r['end_date']) ?></div>

                            <div class="mt-1"><strong>Method:</strong> <?= htmlspecialchars($r['payment_method']) ?></div>
                            <div class="mt-1"><strong>Admin:</strong> <?= htmlspecialchars($r['admin_username']) ?></div>
                            <div class="mt-1"><strong>Reference:</strong> <?= htmlspecialchars($r['reference_no']) ?></div>
                            <div class="mt-1 small muted"><strong>Created:</strong> <?= htmlspecialchars($r['created_at']) ?></div>
                        </div>
                    </div>
                <?php endforeach; ?>
            <?php else: ?>
                <div class="alert alert-info text-center border-0 shadow-sm">No logs found.</div>
            <?php endif; ?>
        </div>
    </div>

    <?php if ($total_pages > 1): ?>
        <nav class="mt-3" aria-label="Pagination">
            <ul class="pagination justify-content-center flex-wrap gap-1">
                <li class="page-item <?= ($page <= 1) ? 'disabled' : '' ?>">
                    <a class="page-link" href="?<?= q(['page'=>max(1,$page-1)]) ?>">&laquo;</a>
                </li>

                <?php
                $window = 2;
                $start = max(1, $page - $window);
                $end = min($total_pages, $page + $window);

                if ($start > 1) {
                    echo '<li class="page-item"><a class="page-link" href="?' . q(['page'=>1]) . '">1</a></li>';
                    if ($start > 2) echo '<li class="page-item disabled"><span class="page-link">…</span></li>';
                }

                for ($p = $start; $p <= $end; $p++) {
                    $active = ($p === $page) ? 'active' : '';
                    echo '<li class="page-item ' . $active . '"><a class="page-link" href="?' . q(['page'=>$p]) . '">' . $p . '</a></li>';
                }

                if ($end < $total_pages) {
                    if ($end < $total_pages - 1) echo '<li class="page-item disabled"><span class="page-link">…</span></li>';
                    echo '<li class="page-item"><a class="page-link" href="?' . q(['page'=>$total_pages]) . '">' . $total_pages . '</a></li>';
                }
                ?>

                <li class="page-item <?= ($page >= $total_pages) ? 'disabled' : '' ?>">
                    <a class="page-link" href="?<?= q(['page'=>min($total_pages,$page+1)]) ?>">&raquo;</a>
                </li>
            </ul>
        </nav>
    <?php endif; ?>

</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
const labels = <?= json_encode($chart_labels, JSON_UNESCAPED_SLASHES) ?>;
const values = <?= json_encode($chart_values, JSON_UNESCAPED_SLASHES) ?>;

const ctx = document.getElementById('last14Chart');
new Chart(ctx, {
  type: 'line',
  data: {
    labels,
    datasets: [{
      label: 'Total Amount (₱)',
      data: values,
      borderColor: '#0d6efd',
      backgroundColor: 'rgba(13,110,253,.12)',
      fill: true,
      tension: 0.35,
      pointRadius: 3,
      pointHoverRadius: 5
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (c) => ' ₱' + (Number(c.parsed.y || 0)).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})
        }
      }
    },
    scales: {
      y: {
        ticks: {
          callback: (v) => '₱' + Number(v).toLocaleString()
        }
      }
    }
  }
});
</script>
</body>
</html>
