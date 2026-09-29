<?php
// user_cignal_logs.php
require 'database.php';
include 'header.php';

if (session_status() === PHP_SESSION_NONE) session_start();

$customer_id = isset($_GET['customer_id']) && ctype_digit($_GET['customer_id']) ? (int)$_GET['customer_id'] : 0;
if ($customer_id <= 0) {
    http_response_code(400);
    die("Invalid customer_id.");
}

// Customer header info
$cstmt = $conn->prepare("SELECT id, full_name, username, cignalplay_no FROM customers WHERE id = :id");
$cstmt->execute([':id' => $customer_id]);
$customer = $cstmt->fetch(PDO::FETCH_ASSOC);
if (!$customer) {
    http_response_code(404);
    die("Customer not found.");
}

/**
 * Search + Pagination
 */
$q = trim($_GET['q'] ?? '');
$page = isset($_GET['page']) && ctype_digit($_GET['page']) ? (int)$_GET['page'] : 1;
$page = max(1, $page);
$per_page = 10;
$offset = ($page - 1) * $per_page;

$where = " WHERE cp.customer_id = :customer_id ";
$params = [':customer_id' => $customer_id];

if ($q !== '') {
    $where .= " AND (
        cp.plan_name LIKE :q OR
        cp.payment_method LIKE :q OR
        cp.reference_no LIKE :q OR
        a.username LIKE :q OR
        CAST(cp.rates AS CHAR) LIKE :q OR
        CAST(cp.quantity_cignal AS CHAR) LIKE :q OR
        CAST(cp.id AS CHAR) LIKE :q OR
        CAST(cp.payment_date AS CHAR) LIKE :q OR
        CAST(cp.start_date AS CHAR) LIKE :q OR
        CAST(cp.end_date AS CHAR) LIKE :q OR
        CAST(cp.created_at AS CHAR) LIKE :q
    ) ";
    $params[':q'] = "%{$q}%";
}

// Count total rows
$countSql = "
    SELECT COUNT(*)
    FROM cignal_play cp
    LEFT JOIN admins a ON a.id = cp.admin_id
    {$where}
";
$cnt = $conn->prepare($countSql);
$cnt->execute($params);
$total_rows = (int)$cnt->fetchColumn();
$total_pages = max(1, (int)ceil($total_rows / $per_page));

// Logs query
$logsSql = "
    SELECT
        cp.id,
        cp.customer_id,
        cp.plan_name,
        cp.rates,
        cp.quantity_cignal,
        cp.created_at,
        cp.payment_method,
        cp.payment_date,
        cp.reference_no,
        cp.start_date,
        cp.end_date,
        cp.admin_id,
        a.username AS admin_username
    FROM cignal_play cp
    LEFT JOIN admins a ON a.id = cp.admin_id
    {$where}
    ORDER BY cp.created_at DESC
    LIMIT :limit OFFSET :offset
";
$lst = $conn->prepare($logsSql);
foreach ($params as $k => $v) $lst->bindValue($k, $v);
$lst->bindValue(':limit', $per_page, PDO::PARAM_INT);
$lst->bindValue(':offset', $offset, PDO::PARAM_INT);
$lst->execute();
$logs = $lst->fetchAll(PDO::FETCH_ASSOC);

// Latest expiry status per plan_name (for this customer)
$latestPlansSql = "
    SELECT x.plan_name, x.end_date
    FROM cignal_play x
    INNER JOIN (
        SELECT plan_name, MAX(COALESCE(end_date, created_at)) AS max_dt
        FROM cignal_play
        WHERE customer_id = :customer_id
        GROUP BY plan_name
    ) m
        ON m.plan_name = x.plan_name
       AND COALESCE(x.end_date, x.created_at) = m.max_dt
    WHERE x.customer_id = :customer_id
    ORDER BY x.plan_name ASC
";
$lp = $conn->prepare($latestPlansSql);
$lp->execute([':customer_id' => $customer_id]);
$latest_plans = $lp->fetchAll(PDO::FETCH_ASSOC);

function build_page_url(int $customer_id, string $q, int $page): string {
    $query = http_build_query([
        'customer_id' => $customer_id,
        'q' => $q,
        'page' => $page
    ]);
    return "user_cignal_logs.php?{$query}";
}
function h($v) { return htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8'); }

function money_php($v): string {
    if ($v === null || $v === '') return '';
    if (!is_numeric($v)) return h($v);
    return '₱' . number_format((float)$v, 2);
}
function badge_class_pm(?string $pm): string {
    $pm = strtolower(trim((string)$pm));
    return match ($pm) {
        'cash' => 'bg-success-subtle text-success border border-success-subtle',
        'bank transfer' => 'bg-primary-subtle text-primary border border-primary-subtle',
        'e-wallet' => 'bg-warning-subtle text-warning-emphasis border border-warning-subtle',
        'payment center' => 'bg-info-subtle text-info border border-info-subtle',
        'online banking' => 'bg-secondary-subtle text-secondary border border-secondary-subtle',
        default => 'bg-light text-dark border',
    };
}
function parse_dt(?string $v): ?DateTime {
    $v = trim((string)$v);
    if ($v === '') return null;
    try { return new DateTime($v); } catch (Throwable $e) { return null; }
}
function expiry_badge(?string $end_date): array {
    $dt = parse_dt($end_date);
    if (!$dt) return ['label' => 'No end date', 'class' => 'bg-secondary-subtle text-secondary border border-secondary-subtle'];

    $today = new DateTime('today');
    $end = new DateTime($dt->format('Y-m-d')); // normalize date-only compare

    if ($end < $today)  return ['label' => 'Expired', 'class' => 'bg-danger-subtle text-danger border border-danger-subtle'];
    if ($end == $today) return ['label' => 'Expires today', 'class' => 'bg-warning-subtle text-warning-emphasis border border-warning-subtle'];
    return ['label' => 'Active', 'class' => 'bg-success-subtle text-success border border-success-subtle'];
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>User Cignal Logs</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet" />
    <style>
        body { background: #f6f7fb; }
        .page-title { letter-spacing: .2px; }
        .card-soft {
            border: 1px solid rgba(0,0,0,.06);
            box-shadow: 0 10px 25px rgba(16,24,40,.06);
            border-radius: 14px;
        }
        .chip {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            padding: .25rem .6rem;
            border-radius: 999px;
            font-size: .85rem;
            white-space: nowrap;
        }
        .chip i { opacity: .85; }
        .table thead th { white-space: nowrap; }

        @media (max-width: 576px) {
            .container { padding-left: 14px; padding-right: 14px; }
            .top-actions { width: 100%; }
            .search-actions .btn { flex: 1 1 auto; }

            .table-responsive { overflow: visible; }

            .log-card {
                background: #fff;
                border: 1px solid rgba(0,0,0,.06);
                box-shadow: 0 10px 22px rgba(16,24,40,.08);
                border-radius: 16px;
                overflow: hidden;
            }
            .log-card .head {
                padding: 12px 14px;
                background: linear-gradient(135deg, rgba(13,110,253,.10), rgba(25,135,84,.10));
                border-bottom: 1px solid rgba(0,0,0,.06);
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 10px;
            }
            .log-card .head .left { min-width: 0; }
            .log-card .idline {
                font-weight: 700;
                color: #111827;
                line-height: 1.1;
            }
            .log-card .subline {
                font-size: .85rem;
                color: #6b7280;
                margin-top: 3px;
            }
            .log-card .body { padding: 12px 14px 14px; }
            .kv { display: grid; grid-template-columns: 1fr; gap: 10px; }
            .kv .rowkv {
                display: flex;
                justify-content: space-between;
                gap: 10px;
                border: 1px solid rgba(0,0,0,.06);
                border-radius: 12px;
                padding: 10px 12px;
                background: #fbfbfd;
            }
            .kv .k { color: #6b7280; font-size: .82rem; white-space: nowrap; }
            .kv .v { color: #111827; font-weight: 600; text-align: right; word-break: break-word; }

            .pagination { justify-content: center; }
        }
    </style>
</head>
<body>
<main class="container py-4">
    <div class="card card-soft mb-3">
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-start gap-3 flex-wrap">
                <div>
                    <h3 class="mb-1 page-title">
                        <i class="fa-solid fa-receipt me-1"></i> User Transaction Logs
                    </h3>
                    <div class="text-muted">
                        Customer: <strong><?= h($customer['full_name'] ?? '') ?></strong>
                        <span class="ms-1">(ID: <?= h($customer['id']) ?>)</span>
                    </div>

                    <div class="d-flex gap-2 flex-wrap mt-2">
                        <?php if (!empty($customer['username'])): ?>
                            <span class="chip bg-light border">
                                <i class="fa-regular fa-user"></i> <?= h($customer['username']) ?>
                            </span>
                        <?php endif; ?>
                        <?php if (!empty($customer['cignalplay_no'])): ?>
                            <span class="chip bg-light border">
                                <i class="fa-solid fa-satellite-dish"></i> <?= h($customer['cignalplay_no']) ?>
                            </span>
                        <?php endif; ?>
                        <span class="chip bg-light border">
                            <i class="fa-regular fa-list-ul"></i>
                            <?= $total_rows ? ($offset + 1) : 0 ?>-<?= min($offset + $per_page, $total_rows) ?> of <?= $total_rows ?>
                        </span>
                    </div>
                </div>

                <div class="top-actions d-flex gap-2 flex-wrap">
                    <a href="add_on_payments.php" class="btn btn-outline-secondary">
                        <i class="fa-solid fa-arrow-left"></i> Back
                    </a>
                </div>
            </div>



            <!-- Search -->
            <form class="row g-2 align-items-center mt-3" method="get">
                <input type="hidden" name="customer_id" value="<?= h($customer_id) ?>">
                <div class="col-12 col-md-8">
                    <div class="input-group">
                        <span class="input-group-text"><i class="fa-solid fa-magnifying-glass"></i></span>
                        <input type="text" name="q" value="<?= h($q) ?>" class="form-control"
                               placeholder="Search plan, method, reference, dates, admin username, rates, qty...">
                    </div>
                </div>
                <div class="col-12 col-md-4 d-flex gap-2 search-actions">
                    <button type="submit" class="btn btn-primary">Search</button>
                    <a class="btn btn-outline-secondary" href="<?= h(build_page_url($customer_id, '', 1)) ?>">Clear</a>
                </div>
            </form>
        </div>
    </div>

    <!-- Desktop/tablet table -->
    <div class="table-responsive d-none d-sm-block">
        <table class="table table-striped table-bordered align-middle table-sm bg-white">
            <thead class="table-light">
            <tr>
                <th>ID</th>
                <th>Plan</th>
                <th>Rates</th>
                <th>Qty</th>
                <th>Payment Method</th>
                <th>Reference No</th>
                <th>Last Expiration Date:</th>
                <th>New Expiration Date:</th>
                <th>Expiry</th>
                <th>Payment Date</th>
                <th>Created At</th>
                <th>Adjusted by</th>
            </tr>
            </thead>
            <tbody>
            <?php if ($logs): ?>
                <?php foreach ($logs as $log): ?>
                    <?php $ex = expiry_badge($log['end_date'] ?? null); ?>
                    <tr>
                        <td class="text-nowrap"><?= h($log['id']) ?></td>
                        <td><?= h($log['plan_name'] ?? '') ?></td>
                        <td class="text-nowrap"><?= money_php($log['rates'] ?? '') ?></td>
                        <td class="text-nowrap"><?= h($log['quantity_cignal'] ?? '') ?></td>
                        <td class="text-nowrap">
                            <span class="badge rounded-pill <?= h(badge_class_pm($log['payment_method'] ?? '')) ?>">
                                <?= h($log['payment_method'] ?? '') ?>
                            </span>
                        </td>
                        <td class="text-nowrap"><?= h($log['reference_no'] ?? '') ?></td>
                        <td class="text-nowrap"><?= h($log['start_date'] ?? '') ?></td>
                        <td class="text-nowrap"><?= h($log['end_date'] ?? '') ?></td>
                        <td class="text-nowrap">
                            <span class="badge rounded-pill <?= h($ex['class']) ?>"><?= h($ex['label']) ?></span>
                        </td>
                        <td class="text-nowrap"><?= h($log['payment_date'] ?? '') ?></td>
                        <td class="text-nowrap"><?= h($log['created_at'] ?? '') ?></td>
                        <td class="text-nowrap"><?= h($log['admin_username'] ?? ('ID: ' . ($log['admin_id'] ?? ''))) ?></td>
                    </tr>
                <?php endforeach; ?>
            <?php else: ?>
                <tr>
                    <td colspan="12" class="text-center py-4">No transactions found for this user.</td>
                </tr>
            <?php endif; ?>
            </tbody>
        </table>
    </div>

    <!-- Mobile cards -->
    <div class="d-block d-sm-none">
        <?php if ($logs): ?>
            <?php foreach ($logs as $log): ?>
                <?php $ex = expiry_badge($log['end_date'] ?? null); ?>
                <div class="log-card mb-3">
                    <div class="head">
                        <div class="left">
                            <div class="idline">#<?= h($log['id']) ?> • <?= h($log['plan_name'] ?? '') ?></div>
                            <div class="subline">
                                Start: <?= h($log['start_date'] ?? '') ?> • End: <?= h($log['end_date'] ?? '') ?>
                            </div>
                        </div>
                        <div class="right text-end d-flex flex-column gap-1 align-items-end">
                            <div class="chip <?= h(badge_class_pm($log['payment_method'] ?? '')) ?>">
                                <i class="fa-solid fa-credit-card"></i>
                                <?= h($log['payment_method'] ?? '') ?>
                            </div>
                            <span class="badge rounded-pill <?= h($ex['class']) ?>"><?= h($ex['label']) ?></span>
                        </div>
                    </div>

                    <div class="body">
                        <div class="kv">
                            <div class="rowkv">
                                <div class="k">Total Rates</div>
                                <div class="v"><?= money_php($log['rates'] ?? '') ?></div>
                            </div>
                            <div class="rowkv">
                                <div class="k">Quantity</div>
                                <div class="v"><?= h($log['quantity_cignal'] ?? '') ?></div>
                            </div>
                            <div class="rowkv">
                                <div class="k">Reference No</div>
                                <div class="v"><?= (h($log['reference_no'] ?? '') !== '' ? h($log['reference_no']) : '-') ?></div>
                            </div>
                            <div class="rowkv">
                                <div class="k">Payment Date</div>
                                <div class="v"><?= h($log['payment_date'] ?? '') ?></div>
                            </div>
                            <div class="rowkv">
                                <div class="k">Created At</div>
                                <div class="v"><?= h($log['created_at'] ?? '') ?></div>
                            </div>
                            <div class="rowkv">
                                <div class="k">Adjusted by</div>
                                <div class="v"><?= h($log['admin_username'] ?? ('ID: ' . ($log['admin_id'] ?? ''))) ?></div>
                            </div>
                        </div>
                    </div>
                </div>
            <?php endforeach; ?>
        <?php else: ?>
            <div class="card card-soft">
                <div class="card-body text-center py-4">
                    No transactions found for this user.
                </div>
            </div>
        <?php endif; ?>
    </div>

    <!-- Pagination -->
    <?php if ($total_pages > 1): ?>
        <?php
        $prev_page = max(1, $page - 1);
        $next_page = min($total_pages, $page + 1);
        $window = 2;
        $start = max(1, $page - $window);
        $end = min($total_pages, $page + $window);
        ?>
        <nav aria-label="Logs pagination" class="mt-3">
            <ul class="pagination flex-wrap">
                <li class="page-item <?= $page <= 1 ? 'disabled' : '' ?>">
                    <a class="page-link" href="<?= h(build_page_url($customer_id, $q, 1)) ?>">First</a>
                </li>
                <li class="page-item <?= $page <= 1 ? 'disabled' : '' ?>">
                    <a class="page-link" href="<?= h(build_page_url($customer_id, $q, $prev_page)) ?>">Prev</a>
                </li>

                <?php if ($start > 1): ?>
                    <li class="page-item disabled"><span class="page-link">...</span></li>
                <?php endif; ?>

                <?php for ($p = $start; $p <= $end; $p++): ?>
                    <li class="page-item <?= $p === $page ? 'active' : '' ?>">
                        <a class="page-link" href="<?= h(build_page_url($customer_id, $q, $p)) ?>"><?= $p ?></a>
                    </li>
                <?php endfor; ?>

                <?php if ($end < $total_pages): ?>
                    <li class="page-item disabled"><span class="page-link">...</span></li>
                <?php endif; ?>

                <li class="page-item <?= $page >= $total_pages ? 'disabled' : '' ?>">
                    <a class="page-link" href="<?= h(build_page_url($customer_id, $q, $next_page)) ?>">Next</a>
                </li>
                <li class="page-item <?= $page >= $total_pages ? 'disabled' : '' ?>">
                    <a class="page-link" href="<?= h(build_page_url($customer_id, $q, $total_pages)) ?>">Last</a>
                </li>
            </ul>
        </nav>
    <?php endif; ?>
</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
