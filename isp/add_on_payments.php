<?php
require 'database.php';
include 'header.php';

if (session_status() === PHP_SESSION_NONE) session_start();

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}
$csrf_token = $_SESSION['csrf_token'];

$notification = '';
if (!empty($_SESSION['notification'])) {
    $notification = $_SESSION['notification'];
    unset($_SESSION['notification']);
}

$search = isset($_GET['search']) ? trim($_GET['search']) : '';
$status_filter = $_GET['status'] ?? 'all'; // all | active | expired | no_plan

$sort_by = $_GET['sort_by'] ?? 'created_at';
$sort_order = strtolower($_GET['sort_order'] ?? 'desc') === 'asc' ? 'asc' : 'desc';
$page = isset($_GET['page']) && is_numeric($_GET['page']) && $_GET['page'] > 0 ? (int)$_GET['page'] : 1;
$per_page = isset($_GET['per_page']) && is_numeric($_GET['per_page']) && $_GET['per_page'] > 0 ? (int)$_GET['per_page'] : 25;

/**
 * ONE ROW PER CUSTOMER:
 * - Plans are merged into a single comma-separated field (no duplicate plan names).
 * - Start/End show overall MIN(start_date) / MAX(end_date) across that customer's plans.
 * - Status is based on "latest end_date":
 *    - No Plan: no plan rows
 *    - Active: latest end_date is NULL OR >= today
 *    - Expired: latest end_date < today
 *
 * NOTE: Requires MySQL (GROUP_CONCAT).
 */

$allowed_status = ['all','active','expired','no_plan'];
if (!in_array($status_filter, $allowed_status, true)) $status_filter = 'all';

$allowed_sort_cols = [
    'created_at','username','cignalplay_no','full_name','account_type','address','cignalplay_adjustedby',
    'plan_name','start_date','end_date','plan_status',
];
if (!in_array($sort_by, $allowed_sort_cols, true)) $sort_by = 'created_at';

$conds = [];
$params = [];

if ($search !== '') {
    $hay = '%' . strtolower($search) . '%';
    $conds[] = "(LOWER(c.full_name) LIKE :hay
            OR LOWER(c.email) LIKE :hay
            OR LOWER(c.phone) LIKE :hay
            OR LOWER(c.username) LIKE :hay
            OR LOWER(c.address) LIKE :hay
            OR LOWER(c.account_type) LIKE :hay
            OR LOWER(c.cignalplay_no) LIKE :hay
            OR LOWER(c.cignalplay_adjustedby) LIKE :hay
            OR LOWER(COALESCE(p.plan_name,'')) LIKE :hay)";
    $params[':hay'] = $hay;
}

/** Base FROM/JOIN */
$fromJoin = "
FROM customers c
LEFT JOIN cignal_play p
  ON p.customer_id = c.id
";

/** Build WHERE string (search only; status handled via HAVING after grouping) */
$whereSql = !empty($conds) ? (" WHERE " . implode(" AND ", $conds)) : "";

/** Status filter after aggregation */
$havingSql = "";
if ($status_filter === 'no_plan') {
    $havingSql = " HAVING plan_count = 0";
} elseif ($status_filter === 'expired') {
    $havingSql = " HAVING plan_count > 0 AND latest_end_date IS NOT NULL AND DATE(latest_end_date) < CURDATE()";
} elseif ($status_filter === 'active') {
    $havingSql = " HAVING plan_count > 0 AND (latest_end_date IS NULL OR DATE(latest_end_date) >= CURDATE())";
}

/** Main data query (GROUP BY customer) */
$sql = "
SELECT
    c.id,
    c.username,
    c.cignalplay_no,
    c.created_at,
    c.full_name,
    c.email,
    c.phone,
    c.address,
    c.account_type,
    c.cignalplay_adjustedby,

    COUNT(p.id) AS plan_count,
    GROUP_CONCAT(DISTINCT p.plan_name ORDER BY p.plan_name SEPARATOR ', ') AS plan_name,
    MIN(p.start_date) AS start_date,
    MAX(p.end_date) AS end_date,
    MAX(p.end_date) AS latest_end_date,
    CASE
        WHEN COUNT(p.id) = 0 THEN 'No Plan'
        WHEN MAX(p.end_date) IS NOT NULL AND DATE(MAX(p.end_date)) < CURDATE() THEN 'Expired'
        ELSE 'Active'
    END AS plan_status
$fromJoin
$whereSql
GROUP BY
    c.id, c.username, c.cignalplay_no, c.created_at, c.full_name, c.email, c.phone, c.address, c.account_type, c.cignalplay_adjustedby
$havingSql
";

/** Safe ORDER BY mapping */
$orderMap = [
    'created_at' => 'c.created_at',
    'username' => 'c.username',
    'cignalplay_no' => 'c.cignalplay_no',
    'full_name' => 'c.full_name',
    'account_type' => 'c.account_type',
    'address' => 'c.address',
    'cignalplay_adjustedby' => 'c.cignalplay_adjustedby',

    'plan_name' => 'plan_name',
    'start_date' => 'start_date',

];

$sortExpr = $orderMap[$sort_by] ?? 'c.created_at';
$sql .= " ORDER BY {$sortExpr} " . ($sort_order === 'asc' ? 'ASC' : 'DESC') . ", c.id DESC";

$offset = ($page - 1) * $per_page;
$sql .= " LIMIT :limit OFFSET :offset";

/** Prepare params for list */
$listParams = $params;
$listParams[':limit'] = (int)$per_page;
$listParams[':offset'] = (int)$offset;

$stmt = $conn->prepare($sql);
foreach ($listParams as $k => $v) {
    if ($k === ':limit' || $k === ':offset') $stmt->bindValue($k, (int)$v, PDO::PARAM_INT);
    else $stmt->bindValue($k, $v, PDO::PARAM_STR);
}
$stmt->execute();
$display_rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

/** Total rows for pagination (respects filters/search) */
$countSql = "
SELECT COUNT(*) FROM (
    SELECT c.id
    $fromJoin
    $whereSql
    GROUP BY c.id
    $havingSql
) t
";
$countStmt = $conn->prepare($countSql);
foreach ($params as $k => $v) $countStmt->bindValue($k, $v, PDO::PARAM_STR);
$countStmt->execute();
$total_rows = (int)$countStmt->fetchColumn();
$total_pages = max(1, (int)ceil($total_rows / $per_page));

/**
 * Counters shown above:
 * - Respect SEARCH, but NOT the status dropdown
 * - Based on per-customer aggregated status
 */
$statsSql = "
SELECT
    SUM(CASE WHEN plan_count = 0 THEN 1 ELSE 0 END) AS no_plan_count,
    SUM(CASE WHEN plan_count > 0 AND latest_end_date IS NOT NULL AND DATE(latest_end_date) < CURDATE() THEN 1 ELSE 0 END) AS expired_count,
    SUM(CASE WHEN plan_count > 0 AND (latest_end_date IS NULL OR DATE(latest_end_date) >= CURDATE()) THEN 1 ELSE 0 END) AS active_count
FROM (
    SELECT
        c.id,
        COUNT(p.id) AS plan_count,
        MAX(p.end_date) AS latest_end_date
    $fromJoin
    $whereSql
    GROUP BY c.id
) x
";
$statsStmt = $conn->prepare($statsSql);
foreach ($params as $k => $v) $statsStmt->bindValue($k, $v, PDO::PARAM_STR);
$statsStmt->execute();
$stats = $statsStmt->fetch(PDO::FETCH_ASSOC) ?: ['no_plan_count'=>0,'expired_count'=>0,'active_count'=>0];

$no_plan_count = (int)($stats['no_plan_count'] ?? 0);
$expired_count = (int)($stats['expired_count'] ?? 0);
$active_count = (int)($stats['active_count'] ?? 0);

function fmtDate($d) {
    if (!$d) return '';
    $ts = strtotime($d);
    return $ts ? date('Y-m-d', $ts) : htmlspecialchars($d);
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>Payments</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet" />
    <style>
        :root{
            --brand:#0d6efd;
            --soft:#f6f9ff;
            --card:#ffffff;
            --border:#e7eef8;
            --text:#0f172a;
            --muted:#64748b;
        }
        body{ background: linear-gradient(180deg, var(--soft), #fff); color:var(--text); }
        .page-header{
            background: radial-gradient(1200px 300px at 10% 0%, rgba(13,110,253,.18), transparent 60%),
                        radial-gradient(900px 240px at 90% 10%, rgba(25,135,84,.12), transparent 55%),
                        #fff;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px 18px;
        }
        .page-title{ display:flex; align-items:center; gap:10px; }
        .page-title i{
            width:38px; height:38px; display:inline-flex; align-items:center; justify-content:center;
            background: rgba(13,110,253,.1); color: var(--brand);
            border-radius: 12px;
        }
        .page-sub{ color: var(--muted); font-size:.92rem; }
        .toolbar{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 14px;
        }
        .table-shell{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
        }
        .table thead th{
            font-size: .78rem;
            letter-spacing:.02em;
            text-transform: uppercase;
            color:#334155;
            background: #f8fafc;
            border-bottom: 1px solid var(--border) !important;
            vertical-align: middle;
        }
        th.sortable { cursor: pointer; }
        th.sorted-asc::after { content: " \25B2"; }
        th.sorted-desc::after { content: " \25BC"; }
        .table-sm-custom > :not(caption) > * > * { padding: 0.45rem 0.55rem; font-size: 0.85rem; }
        .form-control, .form-select { font-size: 0.95rem; padding: 0.5rem 0.7rem; border-radius: 12px; }
        .btn{ border-radius: 12px; }
        .btn-group-xs > .btn, .btn-xs { padding: .25rem .45rem; font-size: .8rem; line-height: .9; border-radius: .6rem; }
        .table th, .table td { white-space: normal !important; word-break: break-word; vertical-align: middle; }
        .col-id { max-width: 52px; min-width:40px; }
        .col-username, .col-cignalplay { max-width: 110px; min-width:90px; }
        .col-cignalplay-adjustedby { max-width: 120px; min-width:90px; }
        .col-address { max-width: 170px; min-width:100px; }
        .col-fullname { max-width: 140px; min-width:90px; }
        .col-createdat { max-width: 110px; min-width:90px; }
        .col-plan { max-width: 160px; min-width: 120px; }
        .col-date { max-width: 120px; min-width: 100px; }
        .col-status { max-width: 90px; min-width: 80px; }
        .highlight-cignal{
            background: #fff3bf;
            font-weight: 700;
            border-radius: 0.6rem;
            padding: 3px 8px;
            border: 1px solid rgba(240,180,0,.25);
        }
        .badge{ border-radius: 999px; }
        .card-mobile{ border: 1px solid var(--border); border-radius: 16px; overflow: hidden; }
        .card-mobile .card-header{ background: #f8fafc; border-bottom: 1px solid var(--border); }
        .pagination .page-link{ border-radius: 12px; }
        .pagination .page-item.active .page-link{ background: var(--brand); border-color: var(--brand); }
        .muted{ color: var(--muted); }
        a.header-link{ text-decoration:none; color:inherit; }
    </style>
</head>
<body>
<br>

<?php if (isset($_GET['success']) && $_GET['success'] == 1): ?>
    <div class="container">
        <div class="alert alert-success border-0 shadow-sm">Payment recorded successfully!</div>
    </div>
<?php endif; ?>

<main class="container py-4">
    <div class="page-header mb-3 shadow-sm">
        <div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-2">
            <div>
                <div class="page-title">
                    <i class="fa-solid fa-award"></i>
                    <div>
                        <h2 class="mb-0 fw-bold text-primary">Payment Add-ons</h2>
                        <div class="page-sub">Search + filter by plan status (Active / Expired / No Plan).</div>
                    </div>
                </div>


            </div>

            <div class="d-flex align-items-center gap-2">
                <span class="badge text-bg-light border" title="Total results">
                    <i class="fa-solid fa-users me-1"></i><?= number_format($total_rows) ?> records
                </span>
                <button type="button" class="btn btn-outline-info" onclick="location.reload();" title="Refresh Page">
                    <i class="fa-solid fa-arrows-rotate"></i>
                </button>
                <a href="payment_addon_logs.php" class="btn btn-link p-0" style="text-decoration:none;">
                    <i class="fa-solid fa-angles-down me-1"></i>Payment add_on logs
                </a>
            </div>
        </div>
    </div>

    <?php if ($notification): ?>
        <div class="alert alert-info border-0 shadow-sm" role="alert"><?= htmlspecialchars($notification) ?></div>
    <?php endif; ?>

    <div class="toolbar mb-3 shadow-sm">
        <form method="get" id="searchForm" class="row g-2 align-items-center">
            <div class="col-12 col-lg-6">
                <div class="input-group">
                    <span class="input-group-text bg-white border-end-0" style="border-radius:12px 0 0 12px;">
                        <i class="fa fa-search text-secondary"></i>
                    </span>
                    <input
                        type="text"
                        id="searchInput"
                        name="search"
                        class="form-control border-start-0"
                        placeholder="Search name, email, phone, username, address, account type, cignalplay no, adjusted by, plan..."
                        value="<?= htmlspecialchars($search) ?>"
                        style="border-radius:0;"
                    >
                    <button type="submit" class="btn btn-primary" id="searchBtn" style="border-radius:0 12px 12px 0;">
                        Search
                    </button>
                </div>
                <div class="mt-2 small muted">Tip: Click column headers to sort.</div>
            </div>



            <div class="col-6 col-lg-2">
                <select id="perPageSelect" name="per_page" class="form-select" onchange="document.getElementById('searchForm').submit();">
                    <option value="25"<?= $per_page == 25 ? ' selected' : '' ?>>Show 25</option>
                    <option value="50"<?= $per_page == 50 ? ' selected' : '' ?>>Show 50</option>
                    <option value="100"<?= $per_page == 100 ? ' selected' : '' ?>>Show 100</option>
                </select>
            </div>

            <div class="col-12 col-lg-2 d-flex gap-2 justify-content-lg-end">
                <button type="button" id="resetBtn" class="btn btn-outline-secondary w-100" title="Reset"
                        onclick="window.location='customers.php'">
                    <i class="fa-solid fa-eraser me-1"></i>Reset
                </button>
            </div>
        </form>
    </div>

    <div class="table-shell shadow-sm">
        <div class="table-responsive d-none d-md-block">
            <table class="table table-hover table-bordered align-middle table-sm-custom mb-0">
                <thead>
                <tr>
                    <th class="text-nowrap text-center col-action">Actions</th>
                    <th class="text-nowrap text-center col-id">ID</th>
                    <?php
                    $columns = [
                        'created_at'    => 'Created at',
                        'username'      => 'Username',
                        'cignalplay_no' => 'CignalPlay No',
                        'cignalplay_adjustedby' => 'Adjusted By',
                        'full_name'     => 'Full Name',
                        'account_type'  => 'Account Type',
                        'address'       => 'Address',
                        'plan_name'     => 'Item',
                        'start_date'    => 'Payment Date Received',


             
                    ];
                    $col_classes = [
                        'created_at' => 'col-createdat',
                        'username' => 'col-username',
                        'cignalplay_no' => 'col-cignalplay',
                        'cignalplay_adjustedby' => 'col-cignalplay-adjustedby',
                        'full_name' => 'col-fullname',
                        'address' => 'col-address',
                        'plan_name' => 'col-plan',
                        'start_date' => 'col-date',
                        'end_date' => 'col-date',
                        'plan_status' => 'col-status',
                    ];

                    foreach ($columns as $col => $disp) {
                        $sortable = in_array($col, $allowed_sort_cols, true);
                        $th_class = $col_classes[$col] ?? '';
                        if ($sortable) {
                            if ($sort_by === $col) $th_class .= ' sorted-' . $sort_order;
                            $query = $_GET;
                            $query['sort_by'] = $col;
                            $query['sort_order'] = ($sort_by === $col && $sort_order === 'asc') ? 'desc' : 'asc';
                            $url = '?' . http_build_query($query);
                            echo "<th class=\"text-nowrap sortable $th_class\"><a class=\"header-link\" href=\"$url\">$disp</a></th>";
                        } else {
                            echo "<th class=\"text-nowrap $th_class\">$disp</th>";
                        }
                    }
                    ?>
                </tr>
                </thead>
                <tbody>
                <?php if ($display_rows): ?>
                    <?php foreach ($display_rows as $row): ?>
                        <?php
                        $status = $row['plan_status'] ?? 'No Plan';
                        $badge = 'text-bg-secondary';
                        if ($status === 'Active') $badge = 'text-bg-success';
                        elseif ($status === 'Expired') $badge = 'text-bg-danger';
                        ?>
                        <tr>
                            <td class="text-center col-action">
                                <div class="btn-group btn-group-xs" role="group" aria-label="Actions">
                                    <a href="edit_customer_cignalplay.php?id=<?= htmlspecialchars($row['id']); ?>"
                                       class="btn btn-outline-info btn-xs" title="Edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    <a href="cignalplay_form.php?customer_id=<?= htmlspecialchars($row['id']); ?>"
                                       class="btn btn-outline-success btn-xs" title="Payment">
                                        <i class="fas fa-money-bill"></i>
                                    </a>
                                    <a href="user_cignal_logs.php?customer_id=<?= htmlspecialchars($row['id']); ?>"
                                       class="btn btn-outline-dark btn-xs" title="Transaction Logs">
                                        <i class="fas fa-receipt"></i>
                                    </a>
                                </div>
                            </td>
                            <td class="text-center col-id"><?= htmlspecialchars($row['id']); ?></td>
                            <td class="col-createdat"><?= htmlspecialchars($row['created_at'] ?? ''); ?></td>
                            <td class="col-username">
                                <?php if (!empty($row['username'])): ?>
                                    <?= htmlspecialchars($row['username']); ?>
                                <?php else: ?>
                                    <span class="badge bg-danger">Not Connected</span>
                                <?php endif; ?>
                            </td>
                            <td class="col-cignalplay">
                                <?php if (!empty($row['cignalplay_no'])): ?>
                                    <span class="highlight-cignal"><?= htmlspecialchars($row['cignalplay_no']); ?></span>
                                <?php endif; ?>
                            </td>
                            <td class="col-cignalplay-adjustedby"><?= htmlspecialchars($row['cignalplay_adjustedby'] ?? ''); ?></td>
                            <td class="col-fullname"><?= htmlspecialchars($row['full_name'] ?? ''); ?></td>
                            <td><?= htmlspecialchars($row['account_type'] ?? ''); ?></td>
                            <td class="col-address"><?= htmlspecialchars($row['address'] ?? ''); ?></td>

                            <td class="col-plan"><?= htmlspecialchars($row['plan_name'] ?? ''); ?></td>
                            <td class="col-date"><?= htmlspecialchars(fmtDate($row['start_date'] ?? '')); ?></td>
   

                        </tr>
                    <?php endforeach; ?>
                <?php else: ?>
                    <tr><td colspan="20" class="text-center py-4 muted">No customers found.</td></tr>
                <?php endif; ?>
                </tbody>
            </table>
        </div>

        <!-- MOBILE VIEW -->
        <div class="d-md-none p-2">
            <?php if ($display_rows): ?>
                <?php foreach ($display_rows as $row): ?>
                    <?php
                    $status = $row['plan_status'] ?? 'No Plan';
                    $badge = 'text-bg-secondary';
                    if ($status === 'Active') $badge = 'text-bg-success';
                    elseif ($status === 'Expired') $badge = 'text-bg-danger';
                    ?>
                    <div class="card card-mobile mb-3 shadow-sm">
                        <div class="card-header d-flex justify-content-between align-items-center py-2">
                            <div class="btn-group btn-group-xs" role="group" aria-label="Actions">
                                <a href="edit_customer_cignalplay.php?id=<?= htmlspecialchars($row['id']); ?>" class="btn btn-outline-info btn-xs" title="Edit">
                                    <i class="fas fa-edit"></i>
                                </a>
                                <a href="cignalplay_form.php?customer_id=<?= htmlspecialchars($row['id']); ?>" class="btn btn-outline-success btn-xs" title="Payment">
                                    <i class="fas fa-money-bill"></i>
                                </a>
                                <a href="user_cignal_logs.php?customer_id=<?= htmlspecialchars($row['id']); ?>" class="btn btn-outline-dark btn-xs" title="Transaction Logs">
                                    <i class="fas fa-receipt"></i>
                                </a>
                            </div>
                  
                        </div>

                        <div class="card-body py-2">
                            <div class="small muted mb-2"><strong>ID:</strong> <?= htmlspecialchars($row['id']); ?></div>
                            <div><strong>Created at:</strong> <?= htmlspecialchars($row['created_at'] ?? ''); ?></div>
                            <div class="mt-1"><strong>Username:</strong>
                                <?= !empty($row['username']) ? htmlspecialchars($row['username']) : '<span class="badge bg-danger">Not Connected</span>'; ?>
                            </div>
                            <div class="mt-1"><strong>CignalPlay No:</strong>
                                <?php if (!empty($row['cignalplay_no'])): ?>
                                    <span class="highlight-cignal"><?= htmlspecialchars($row['cignalplay_no']); ?></span>
                                <?php endif; ?>
                            </div>
                            <div class="mt-1"><strong>Adjusted By:</strong> <?= htmlspecialchars($row['cignalplay_adjustedby'] ?? ''); ?></div>
                            <div class="mt-1"><strong>Full Name:</strong> <?= htmlspecialchars($row['full_name'] ?? ''); ?></div>
                            <div class="mt-1"><strong>Account Type:</strong> <?= htmlspecialchars($row['account_type'] ?? ''); ?></div>
                            <div class="mt-1"><strong>Address:</strong> <?= htmlspecialchars($row['address'] ?? ''); ?></div>

                            <hr class="my-2">
                            <div class="mt-1"><strong>Item:</strong> <?= htmlspecialchars($row['plan_name'] ?? ''); ?></div>
                            <div class="mt-1"><strong>Payment Date Received:</strong> <?= htmlspecialchars(fmtDate($row['start_date'] ?? '')); ?></div>
                         
                        </div>
                    </div>
                <?php endforeach; ?>
            <?php else: ?>
                <div class="alert alert-info text-center border-0 shadow-sm">No customers found.</div>
            <?php endif; ?>
        </div>
    </div>

    <?php if ($total_pages > 1): ?>
        <nav aria-label="Page navigation" class="mt-3">
            <ul class="pagination justify-content-center flex-wrap gap-1">
                <li class="page-item <?= ($page <= 1) ? 'disabled' : '' ?>">
                    <a class="page-link" href="?<?= http_build_query(array_merge($_GET, ['page'=>max(1, $page-1)])) ?>" aria-label="Previous">&laquo;</a>
                </li>
                <?php
                $window = 2;
                $start = max(1, $page - $window);
                $end = min($total_pages, $page + $window);

                if ($start > 1) {
                    echo '<li class="page-item"><a class="page-link" href="?' . http_build_query(array_merge($_GET, ['page'=>1])) . '">1</a></li>';
                    if ($start > 2) echo '<li class="page-item disabled"><span class="page-link">…</span></li>';
                }

                for ($p = $start; $p <= $end; $p++):
                    ?>
                    <li class="page-item <?= ($p == $page) ? 'active' : '' ?>">
                        <a class="page-link" href="?<?= http_build_query(array_merge($_GET, ['page'=>$p])) ?>"><?= $p; ?></a>
                    </li>
                <?php endfor;

                if ($end < $total_pages) {
                    if ($end < $total_pages - 1) echo '<li class="page-item disabled"><span class="page-link">…</span></li>';
                    echo '<li class="page-item"><a class="page-link" href="?' . http_build_query(array_merge($_GET, ['page'=>$total_pages])) . '">' . $total_pages . '</a></li>';
                }
                ?>
                <li class="page-item <?= ($page >= $total_pages) ? 'disabled' : '' ?>">
                    <a class="page-link" href="?<?= http_build_query(array_merge($_GET, ['page'=>min($total_pages, $page+1)])) ?>" aria-label="Next">&raquo;</a>
                </li>
            </ul>
        </nav>
    <?php endif; ?>

    <input type="hidden" id="csrf_token" value="<?= htmlspecialchars($csrf_token) ?>">
</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
