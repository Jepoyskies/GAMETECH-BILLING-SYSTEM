<?php
include 'header.php';

// ==== Database config ====
$host = "localhost";
$user = "root";
$pass = "@Marille2012";
$db   = "gametech";

// ==== Pagination + sorting + search ====
$per_page = isset($_GET['per_page']) ? (int)$_GET['per_page'] : 10;
$allowed_per_page = [10, 25, 50, 100];
if (!in_array($per_page, $allowed_per_page, true)) $per_page = 10;

$page = isset($_GET['page']) && is_numeric($_GET['page']) && (int)$_GET['page'] > 0 ? (int)$_GET['page'] : 1;
$offset = ($page - 1) * $per_page;

$search = isset($_GET['search']) ? trim($_GET['search']) : '';

$allowed_sorts = [
    'created_at' => 'created_at',
    'username' => 'username',
    'plan_name' => 'plan_name',
    'days' => 'days',
    'current_expiry' => 'current_expiry',
    'expires_at' => 'expires_at',
    'paid_at' => 'paid_at',
];

$sort = isset($_GET['sort']) ? $_GET['sort'] : 'paid_at';
$sort = $allowed_sorts[$sort] ?? 'paid_at';

$dir = isset($_GET['dir']) ? strtolower($_GET['dir']) : 'desc';
$dir = ($dir === 'asc') ? 'ASC' : 'DESC';

// Search SQL
$search_sql = '';
$params = [];
if ($search !== '') {
    $search_sql = "WHERE username LIKE :search OR plan_name LIKE :search";
    $params[':search'] = '%' . $search . '%';
}

// columns (labels)
$columns = [
    'Created At'       => 'created_at',
    'Username'         => 'username',
    'Plan Name'        => 'plan_name',
    'Days'             => 'days',
    'Current Expiry'   => 'current_expiry',
    'Expires At'       => 'expires_at',
    'Paid At'          => 'paid_at',
    'Adjusted By'      => 'adjusted_by',
    'Note'             => 'note',
    'Mikrotik Devices' => 'mikrotik_devices'
];

$total = 0;
$rows  = [];

function build_url(array $overrides = []): string {
    $q = $_GET;
    foreach ($overrides as $k => $v) {
        if ($v === null) unset($q[$k]);
        else $q[$k] = $v;
    }
    return '?' . http_build_query($q);
}

// Pagination window
function pagination_window(int $page, int $total_pages, int $radius = 2): array {
    $pages = [];
    $start = max(1, $page - $radius);
    $end   = min($total_pages, $page + $radius);

    if ($start > 1) {
        $pages[] = 1;
        if ($start > 2) $pages[] = '...';
    }

    for ($i = $start; $i <= $end; $i++) $pages[] = $i;

    if ($end < $total_pages) {
        if ($end < $total_pages - 1) $pages[] = '...';
        $pages[] = $total_pages;
    }
    return $pages;
}

try {
    $pdo = new PDO("mysql:host=$host;dbname=$db;charset=utf8mb4", $user, $pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);

    // Count
    $count_sql = "SELECT COUNT(*) FROM rebates $search_sql";
    $count_stmt = $pdo->prepare($count_sql);
    $count_stmt->execute($params);
    $total = (int)$count_stmt->fetchColumn();

    $total_pages = max(1, (int)ceil($total / $per_page));
    if ($page > $total_pages) {
        $page = $total_pages;
        $offset = ($page - 1) * $per_page;
    }

    if ($total > 0) {
        // Data (server-side sorting)
        $sql = "SELECT username, plan_name, days, current_expiry, expires_at, created_at,
                       paid_at, adjusted_by, note, mikrotik_devices
                FROM rebates
                $search_sql
                ORDER BY $sort $dir
                LIMIT :limit OFFSET :offset";
        $stmt = $pdo->prepare($sql);

        if ($search !== '') {
            $stmt->bindValue(':search', '%' . $search . '%', PDO::PARAM_STR);
        }
        $stmt->bindValue(':limit', (int)$per_page, PDO::PARAM_INT);
        $stmt->bindValue(':offset', (int)$offset, PDO::PARAM_INT);

        $stmt->execute();
        $rows = $stmt->fetchAll();
    } else {
        $total_pages = 1;
    }
} catch (PDOException $e) {
    $db_error = $e->getMessage();
    $total_pages = 1;
}

// For header sort links
function sort_link(string $key): string {
    $current_sort = $_GET['sort'] ?? 'paid_at';
    $current_dir  = strtolower($_GET['dir'] ?? 'desc');

    $new_dir = 'asc';
    if ($current_sort === $key) {
        $new_dir = ($current_dir === 'asc') ? 'desc' : 'asc';
    }
    return build_url(['sort' => $key, 'dir' => $new_dir, 'page' => 1]);
}
function sort_icon(string $key): string {
    $current_sort = $_GET['sort'] ?? 'paid_at';
    $current_dir  = strtolower($_GET['dir'] ?? 'desc');
    if ($current_sort !== $key) return '<span class="sort-icon text-muted">↕</span>';
    return $current_dir === 'asc'
        ? '<span class="sort-icon text-primary">↑</span>'
        : '<span class="sort-icon text-primary">↓</span>';
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Rebates / Re-adjustments</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

    <style>
        body{background:#f5f7fb;font-size:.95rem}
        main.container{max-width:1200px}

        .page-shell{
            background:#fff;border:1px solid #e7ebf3;border-radius:14px;
            box-shadow:0 10px 30px rgba(18,38,63,.06);
            overflow:hidden
        }
        .page-shell .topbar{
            padding:14px 16px;border-bottom:1px solid #eef2f7;
            background:linear-gradient(180deg,#ffffff, #fbfcff);
        }
        .title-row{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
        .title-row h5{margin:0;font-weight:700}
        .chip{
            font-size:.8rem;padding:.25rem .6rem;border-radius:999px;
            background:#f1f5ff;border:1px solid #dfe8ff;color:#2b4ed8
        }

        .controls{padding:14px 16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between}
        .controls .left{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
        .controls .right{display:flex;gap:10px;flex-wrap:wrap;align-items:center}

        .search-input{min-width:280px}
        .btn-soft{
            background:#f3f5f9;border:1px solid #e6eaf2;color:#27303f
        }
        .btn-soft:hover{background:#e9edf6}

        .table-wrap{padding:0 16px 10px}
        .rebates-table-container{
            border:1px solid #e7ebf3;border-radius:12px;overflow:hidden;background:#fff
        }
        table.rebates-table thead th{
            background:#f7f9fc;font-size:.82rem;white-space:nowrap;border-bottom:1px solid #e7ebf3;
            position:sticky;top:0;z-index:1
        }
        table.rebates-table tbody td{font-size:.85rem;vertical-align:middle}
        .th-link{
            text-decoration:none;color:inherit;display:inline-flex;gap:6px;align-items:center
        }
        .sort-icon{font-size:.85rem;line-height:1}

        .note-col{
            max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis
        }
        .device-col{
            max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis
        }

        .footerbar{
            padding:12px 16px;border-top:1px solid #eef2f7;display:flex;gap:10px;
            align-items:center;justify-content:space-between;flex-wrap:wrap
        }

        /* Mobile card style */
        @media (max-width: 767.98px) {
            .table-wrap{padding:0 12px 10px}
            .rebates-table thead{display:none}
            .rebates-table tbody tr{
                display:block;margin:0 0 12px 0;background:#fff;border-radius:12px;
                border:1px solid #e7ebf3;padding:10px 12px
            }
            .rebates-table tbody td{
                display:flex;width:100%;align-items:flex-start;gap:10px;
                padding:7px 0;border:none;border-bottom:1px solid #f0f2f7;font-size:.92rem
            }
            .rebates-table tbody td::before{
                content: attr(data-label);
                flex:0 0 42%;
                color:#6b7280;font-weight:700
            }
            .rebates-table tbody td:last-child{border-bottom:none}
            .note-col,.device-col{max-width:none;white-space:normal}
        }
    </style>
</head>
<body>
<main class="container py-3">

    <div class="page-shell">
        <div class="topbar">
            <div class="title-row">
                <div class="d-flex align-items-center gap-2 flex-wrap">
                    <h5>Rebates / Re-adjustments</h5>
                    <span class="chip"><?= (int)$total ?> record(s)</span>
                </div>
                <div class="d-flex gap-2 align-items-center flex-wrap">
                    <span class="text-muted small">
                        Page <?= (int)$page ?> / <?= (int)$total_pages ?>
                    </span>
                </div>
            </div>
        </div>

        <div class="controls">
            <div class="left">
                <form method="get" class="d-flex gap-2 flex-wrap align-items-center">
                    <input type="hidden" name="sort" value="<?= htmlspecialchars($_GET['sort'] ?? 'paid_at') ?>">
                    <input type="hidden" name="dir" value="<?= htmlspecialchars($_GET['dir'] ?? 'desc') ?>">

                    <div class="input-group input-group-sm search-input">
                        <span class="input-group-text">Search</span>
                        <input
                            type="text"
                            name="search"
                            class="form-control"
                            placeholder="Username or plan..."
                            value="<?= htmlspecialchars($search) ?>"
                        >
                        <button type="submit" class="btn btn-primary">Go</button>
                    </div>

                    <div class="input-group input-group-sm" style="width: 170px;">
                        <span class="input-group-text">Rows</span>
                        <select class="form-select" name="per_page" onchange="this.form.submit()">
                            <?php foreach ($allowed_per_page as $n): ?>
                                <option value="<?= $n ?>" <?= $per_page === $n ? 'selected' : '' ?>><?= $n ?></option>
                            <?php endforeach; ?>
                        </select>
                    </div>

                    <a class="btn btn-soft btn-sm" href="<?= htmlspecialchars(strtok($_SERVER['REQUEST_URI'], '?')) ?>">Clear</a>
                    <a class="btn btn-soft btn-sm" href="<?= htmlspecialchars(build_url(['page'=>null])) ?>">Refresh</a>
                    <a class="btn btn-outline-dark btn-sm" href="payment_logs.php">Back to Payments</a>
                </form>
            </div>

            <div class="right">
                <span class="text-muted small">
                    Showing
                    <?= $total ? ($offset + 1) : 0 ?>–<?= min($offset + $per_page, $total) ?>
                    of <?= (int)$total ?>
                </span>
            </div>
        </div>

        <div class="table-wrap">
            <div class="rebates-table-container">
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered align-middle mb-0 rebates-table">
                        <thead>
                            <tr>
                                <th>
                                    <a class="th-link" href="<?= htmlspecialchars(sort_link('created_at')) ?>">
                                        Created At <?= sort_icon('created_at') ?>
                                    </a>
                                </th>
                                <th>
                                    <a class="th-link" href="<?= htmlspecialchars(sort_link('username')) ?>">
                                        Username <?= sort_icon('username') ?>
                                    </a>
                                </th>
                                <th>
                                    <a class="th-link" href="<?= htmlspecialchars(sort_link('plan_name')) ?>">
                                        Plan Name <?= sort_icon('plan_name') ?>
                                    </a>
                                </th>
                                <th>
                                    <a class="th-link" href="<?= htmlspecialchars(sort_link('days')) ?>">
                                        Days <?= sort_icon('days') ?>
                                    </a>
                                </th>
                                <th>
                                    <a class="th-link" href="<?= htmlspecialchars(sort_link('current_expiry')) ?>">
                                        Current Expiry <?= sort_icon('current_expiry') ?>
                                    </a>
                                </th>
                                <th>
                                    <a class="th-link" href="<?= htmlspecialchars(sort_link('expires_at')) ?>">
                                        Expires At <?= sort_icon('expires_at') ?>
                                    </a>
                                </th>
                                <th>
                                    <a class="th-link" href="<?= htmlspecialchars(sort_link('paid_at')) ?>">
                                        Paid At <?= sort_icon('paid_at') ?>
                                    </a>
                                </th>
                                <th>Adjusted By</th>
                                <th>Note</th>
                                <th>Mikrotik Devices</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php if (isset($db_error)): ?>
                                <tr>
                                    <td colspan="10" class="text-danger text-center p-4">
                                        Database error: <?= htmlspecialchars($db_error) ?>
                                    </td>
                                </tr>
                            <?php elseif ($total === 0): ?>
                                <tr>
                                    <td colspan="10" class="text-center text-muted p-4">No rebates found.</td>
                                </tr>
                            <?php else: ?>
                                <?php foreach ($rows as $row): ?>
                                    <tr>
                                        <td data-label="Created At"><?= htmlspecialchars($row['created_at'] ?? '') ?></td>
                                        <td data-label="Username"><?= htmlspecialchars($row['username'] ?? '') ?></td>
                                        <td data-label="Plan Name"><?= htmlspecialchars($row['plan_name'] ?? '') ?></td>
                                        <td data-label="Days"><?= (int)($row['days'] ?? 0) ?></td>
                                        <td data-label="Current Expiry"><?= htmlspecialchars($row['current_expiry'] ?? '') ?></td>
                                        <td data-label="Expires At"><?= htmlspecialchars($row['expires_at'] ?? '') ?></td>
                                        <td data-label="Paid At"><?= htmlspecialchars($row['paid_at'] ?? '') ?></td>
                                        <td data-label="Adjusted By"><?= htmlspecialchars($row['adjusted_by'] ?? '') ?></td>
                                        <td class="note-col" data-label="Note" title="<?= htmlspecialchars($row['note'] ?? '') ?>">
                                            <?= htmlspecialchars($row['note'] ?? '') ?>
                                        </td>
                                        <td class="device-col" data-label="Mikrotik Devices" title="<?= htmlspecialchars($row['mikrotik_devices'] ?? '') ?>">
                                            <?= htmlspecialchars($row['mikrotik_devices'] ?? '') ?>
                                        </td>
                                    </tr>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Pagination -->
        <div class="footerbar">
            <div class="text-muted small">
                <?= $total_pages > 1 ? 'Navigate pages:' : ' ' ?>
            </div>

            <?php if ($total_pages > 1): ?>
                <?php $items = pagination_window($page, $total_pages, 2); ?>
                <nav aria-label="Rebates pagination">
                    <ul class="pagination pagination-sm mb-0">
                        <li class="page-item <?= $page <= 1 ? 'disabled' : '' ?>">
                            <a class="page-link" href="<?= htmlspecialchars(build_url(['page' => 1])) ?>">First</a>
                        </li>
                        <li class="page-item <?= $page <= 1 ? 'disabled' : '' ?>">
                            <a class="page-link" href="<?= htmlspecialchars(build_url(['page' => max(1, $page - 1)])) ?>">Prev</a>
                        </li>

                        <?php foreach ($items as $it): ?>
                            <?php if ($it === '...'): ?>
                                <li class="page-item disabled"><span class="page-link">…</span></li>
                            <?php else: ?>
                                <li class="page-item <?= ((int)$it === (int)$page) ? 'active' : '' ?>">
                                    <a class="page-link" href="<?= htmlspecialchars(build_url(['page' => (int)$it])) ?>">
                                        <?= (int)$it ?>
                                    </a>
                                </li>
                            <?php endif; ?>
                        <?php endforeach; ?>

                        <li class="page-item <?= $page >= $total_pages ? 'disabled' : '' ?>">
                            <a class="page-link" href="<?= htmlspecialchars(build_url(['page' => min($total_pages, $page + 1)])) ?>">Next</a>
                        </li>
                        <li class="page-item <?= $page >= $total_pages ? 'disabled' : '' ?>">
                            <a class="page-link" href="<?= htmlspecialchars(build_url(['page' => $total_pages])) ?>">Last</a>
                        </li>
                    </ul>
                </nav>
            <?php else: ?>
                <div></div>
            <?php endif; ?>

            <form method="get" class="d-flex align-items-center gap-2">
                <?php
                // preserve query, but remove page then re-add
                $q = $_GET;
                ?>
                <?php foreach ($q as $k => $v): ?>
                    <?php if ($k === 'page') continue; ?>
                    <input type="hidden" name="<?= htmlspecialchars($k) ?>" value="<?= htmlspecialchars((string)$v) ?>">
                <?php endforeach; ?>
                <label class="text-muted small" for="jumpPage">Jump:</label>
                <input id="jumpPage" name="page" type="number" min="1" max="<?= (int)$total_pages ?>"
                       class="form-control form-control-sm" style="width: 90px;" value="<?= (int)$page ?>">
                <button class="btn btn-primary btn-sm" type="submit">Go</button>
            </form>
        </div>
    </div>

</main>

<?php include 'footer.php'; ?>
</body>
</html>
