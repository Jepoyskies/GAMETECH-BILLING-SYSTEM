<?php
require 'database.php';
include 'header.php';

/*
 * CONFIG
 */
$perPage = 10; // rows per page

// Helper: get allowed order by column
$allowedSortColumns = [
    'changed_at' => 'changed_at',
    'table_name' => 'table_name',
    'record_id'  => 'record_id',
    'action'     => 'action',
    'changed_by' => 'changed_by',
];

// Read query params (for filters, sorting, pagination)
$page        = isset($_GET['page']) ? max(1, (int)$_GET['page']) : 1;
$sort        = $_GET['sort'] ?? 'changed_at';
$dir         = strtolower($_GET['dir'] ?? 'desc') === 'asc' ? 'asc' : 'desc';
$dateFrom    = $_GET['date_from'] ?? '';
$dateTo      = $_GET['date_to'] ?? '';
$search      = $_GET['search'] ?? '';
$actionFilter = $_GET['action_filter'] ?? ''; // ADD / UPDATE / DELETE

// Validate sort column
$orderBy = $allowedSortColumns[$sort] ?? 'changed_at';

// Build WHERE conditions
$where  = [];
$params = [];

// Date filter
if ($dateFrom !== '') {
    $where[] = "changed_at >= :date_from";
    $params[':date_from'] = $dateFrom . ' 00:00:00';
}
if ($dateTo !== '') {
    $where[] = "changed_at <= :date_to";
    $params[':date_to'] = $dateTo . ' 23:59:59';
}

// Action-type dropdown filter (ADD / UPDATE / DELETE)
if ($actionFilter !== '') {
    // Map UI labels to actual DB values
    switch (strtoupper($actionFilter)) {
        case 'ADD':
            // treat any of these as ADD
            $where[] = "LOWER(action) IN ('insert','create','add')";
            break;
        case 'UPDATE':
            $where[] = "LOWER(action) IN ('update','edit')";
            break;
        case 'DELETE':
            $where[] = "LOWER(action) IN ('delete','remove')";
            break;
    }
}

// Search filter (table, user, action, data)
if ($search !== '') {
    $where[] = "
        (
            table_name           LIKE :search OR
            changed_by           LIKE :search OR
            LOWER(action)        LIKE LOWER(:search) OR
            old_data             LIKE :search OR
            new_data             LIKE :search
        )
    ";
    $params[':search'] = '%' . $search . '%';
}

$whereSql = '';
if (!empty($where)) {
    $whereSql = 'WHERE ' . implode(' AND ', $where);
}

// Count total records for pagination
$countSql = "SELECT COUNT(*) FROM system_logs $whereSql";
$countStmt = $conn->prepare($countSql);
$countStmt->execute($params);
$totalRows = (int)$countStmt->fetchColumn();
$totalPages = max(1, (int)ceil($totalRows / $perPage));

// Pagination offsets
$offset = ($page - 1) * $perPage;

// Fetch logs (with filters, sorting, pagination)
$sql = "
    SELECT *
    FROM system_logs
    $whereSql
    ORDER BY $orderBy $dir
    LIMIT :limit OFFSET :offset
";
$stmt = $conn->prepare($sql);

// bind normal params
foreach ($params as $key => $val) {
    $stmt->bindValue($key, $val);
}
// bind limit/offset as int
$stmt->bindValue(':limit', $perPage, PDO::PARAM_INT);
$stmt->bindValue(':offset', $offset, PDO::PARAM_INT);

$stmt->execute();
$logs = $stmt->fetchAll(PDO::FETCH_ASSOC);

// Helper to keep existing query params while changing some
function buildQuery(array $overrides = []): string {
    $params = $_GET;
    foreach ($overrides as $k => $v) {
        if ($v === null) {
            unset($params[$k]);
        } else {
            $params[$k] = $v;
        }
    }
    return http_build_query($params);
}

// Helper to build sortable column header link
function sortLink(string $label, string $column, string $currentSort, string $currentDir): string {
    $newDir = 'asc';
    $icon   = '';
    if ($currentSort === $column) {
        if ($currentDir === 'asc') {
            $newDir = 'desc';
            $icon   = ' ▲';
        } else {
            $newDir = 'asc';
            $icon   = ' ▼';
        }
    }
    $q = buildQuery(['sort' => $column, 'dir' => $newDir, 'page' => 1]);
    return '<a href="?' . htmlspecialchars($q) . '" class="text-decoration-none text-nowrap">'
         . htmlspecialchars($label . $icon)
         . '</a>';
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>System Logs</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- Bootstrap 5 CSS (CDN) -->
    <link 
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" 
        rel="stylesheet" 
        integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" 
        crossorigin="anonymous"
    >

    <style>
        body {
            background: #f5f7fb;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .page-wrapper {
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .logs-card {
            border: none;
            border-radius: 1rem;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.1);
            overflow: hidden;
        }

        .card-header {
            background: linear-gradient(135deg, #2563eb, #4f46e5);
            color: #fff;
            border-bottom: none;
            padding: 1rem 1.5rem;
        }

        .card-header h1 {
            font-size: 1.35rem;
            margin: 0;
        }

        .card-header small {
            opacity: 0.85;
        }

        .table-responsive {
            max-height: 70vh;
        }

        table thead th {
            position: sticky;
            top: 0;
            z-index: 2;
            background: #f9fafb;
            border-bottom: 1px solid #e5e7eb;
            white-space: nowrap;
        }

        .table {
            margin-bottom: 0;
            font-size: 0.875rem;
        }

        .table tbody tr:nth-child(even) {
            background-color: #f9fafb;
        }

        .table tbody tr:hover {
            background-color: #eef2ff;
        }

        .badge-action {
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 0.03em;
        }

        .badge-action-insert {
            background-color: #22c55e1a;
            color: #15803d;
        }

        .badge-action-update {
            background-color: #f973161a;
            color: #c2410c;
        }

        .badge-action-delete {
            background-color: #ef44441a;
            color: #b91c1c;
        }

        .log-json {
            max-height: 180px;
            overflow: auto;
            background: #0f172a;
            color: #e5e7eb;
            border-radius: 0.5rem;
            padding: 0.5rem 0.75rem;
            font-size: 0.75rem;
            line-height: 1.4;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .log-json.empty {
            font-style: italic;
            color: #9ca3af;
            background: #f3f4f6;
        }

        .log-meta {
            font-size: 0.75rem;
            color: #6b7280;
        }

        .search-input {
            max-width: 260px;
        }

        .date-filter-input {
            max-width: 170px;
        }

        @media (max-width: 991.98px) {
            .card-header h1 {
                font-size: 1.1rem;
            }

            .table-responsive {
                max-height: none;
            }

            .search-input,
            .date-filter-input {
                width: 100%;
                max-width: none;
            }

            table thead {
                display: none;
            }

            table tbody tr {
                display: block;
                margin-bottom: 0.85rem;
                border-radius: 0.75rem;
                border: 1px solid #e5e7eb;
                padding: 0.5rem 0.75rem;
                background: #fff;
            }

            table tbody td {
                display: flex;
                justify-content: space-between;
                padding: 0.25rem 0;
                border: none;
                font-size: 0.8rem;
            }

            table tbody td::before {
                content: attr(data-label);
                font-weight: 600;
                color: #4b5563;
                margin-right: 0.75rem;
            }

            .log-json {
                width: 100%;
            }
        }
    </style>
</head>
<body>
<div class="page-wrapper">
    <main class="container my-4 my-md-5 flex-fill">
        <div class="card logs-card">
            <div class="card-header d-flex flex-column flex-md-row align-items-md-center gap-2">
                <div>
                    <h1>System Logs</h1>
                    <small>
                        Showing 
                        <?= $totalRows === 0 ? 0 : (($offset + 1) . '–' . min($offset + $perPage, $totalRows)) ?>
                        of <?= $totalRows ?> records
                    </small>
                </div>

                <form method="get" class="ms-md-auto d-flex flex-wrap gap-2 align-items-center">
                    <input
                        type="text"
                        name="search"
                        value="<?= htmlspecialchars($search) ?>"
                        class="form-control form-control-sm search-input"
                        placeholder="Search table / user / action / data..."
                        autocomplete="off"
                    >

                    <!-- Action dropdown filter -->
                    <select
                        name="action_filter"
                        class="form-select form-select-sm"
                        style="max-width: 150px;"
                    >
                        <option value="">All Actions</option>
                        <option value="ADD" <?= strtoupper($actionFilter) === 'ADD' ? 'selected' : '' ?>>ADD</option>
                        <option value="UPDATE" <?= strtoupper($actionFilter) === 'UPDATE' ? 'selected' : '' ?>>UPDATE</option>
                        <option value="DELETE" <?= strtoupper($actionFilter) === 'DELETE' ? 'selected' : '' ?>>DELETE</option>
                    </select>

                    <input
                        type="date"
                        name="date_from"
                        value="<?= htmlspecialchars($dateFrom) ?>"
                        class="form-control form-control-sm date-filter-input"
                        placeholder="From"
                    >

                    <input
                        type="date"
                        name="date_to"
                        value="<?= htmlspecialchars($dateTo) ?>"
                        class="form-control form-control-sm date-filter-input"
                        placeholder="To"
                    >

                    <!-- keep sort & dir when filtering -->
                    <input type="hidden" name="sort" value="<?= htmlspecialchars($sort) ?>">
                    <input type="hidden" name="dir" value="<?= htmlspecialchars($dir) ?>">

                    <button type="submit" class="btn btn-light btn-sm border">Filter</button>
                    <a href="?" class="btn btn-outline-light btn-sm text-white border-0">Reset</a>

                    <span class="badge bg-light text-muted border">
                        Page <?= $page ?> / <?= $totalPages ?>
                    </span>
                </form>
            </div>

            <div class="card-body p-0">
                <?php if (empty($logs)): ?>
                    <div class="p-4 text-center text-muted">
                        No logs available for current filters.
                    </div>
                <?php else: ?>
                    <div class="table-responsive">
                        <table class="table align-middle mb-0" id="logsTable">
                            <thead>
                                <tr>
                                    <th>
                                        <?= sortLink('Date', 'changed_at', $sort, $dir) ?>
                                    </th>
                                    <th>
                                        <?= sortLink('Table', 'table_name', $sort, $dir) ?>
                                    </th>
                                    <th>
                                        <?= sortLink('Record ID', 'record_id', $sort, $dir) ?>
                                    </th>
                                    <th>
                                        <?= sortLink('Action', 'action', $sort, $dir) ?>
                                    </th>
                                    <th>
                                        <?= sortLink('User', 'changed_by', $sort, $dir) ?>
                                    </th>
                                    <th style="min-width: 200px;">Old Data</th>
                                    <th style="min-width: 200px;">New Data</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($logs as $log): ?>
                                    <?php
                                        $action = strtolower($log['action'] ?? '');
                                        $badgeClass = 'badge-action-update';
                                        if ($action === 'insert' || $action === 'create' || $action === 'add') {
                                            $badgeClass = 'badge-action-insert';
                                        } elseif ($action === 'delete' || $action === 'remove') {
                                            $badgeClass = 'badge-action-delete';
                                        }

                                        $old = trim((string)($log['old_data'] ?? ''));
                                        $new = trim((string)($log['new_data'] ?? ''));

                                        $prettyOld = $old;
                                        $prettyNew = $new;

                                        $decodedOld = json_decode($old, true);
                                        if (json_last_error() === JSON_ERROR_NONE && is_array($decodedOld)) {
                                            $prettyOld = json_encode($decodedOld, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
                                        }

                                        $decodedNew = json_decode($new, true);
                                        if (json_last_error() === JSON_ERROR_NONE && is_array($decodedNew)) {
                                            $prettyNew = json_encode($decodedNew, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
                                        }
                                    ?>
                                    <tr>
                                        <td data-label="Date">
                                            <div class="fw-semibold">
                                                <?= htmlspecialchars($log['changed_at'] ?? '') ?>
                                            </div>
                                            <div class="log-meta">
                                                ID: <?= htmlspecialchars((string)($log['id'] ?? '')) ?>
                                            </div>
                                        </td>
                                        <td data-label="Table">
                                            <span class="fw-semibold">
                                                <?= htmlspecialchars($log['table_name'] ?? '') ?>
                                            </span>
                                        </td>
                                        <td data-label="Record ID">
                                            <?= htmlspecialchars((string)($log['record_id'] ?? '')) ?>
                                        </td>
                                        <td data-label="Action">
                                            <span class="badge badge-action <?= $badgeClass ?>">
                                                <?= htmlspecialchars(strtoupper($log['action'] ?? '')) ?>
                                            </span>
                                        </td>
                                        <td data-label="User">
                                            <?= htmlspecialchars($log['changed_by'] ?? '') ?>
                                        </td>
                                        <td data-label="Old Data">
                                            <?php if ($prettyOld === '' || strtolower($prettyOld) === 'null'): ?>
                                                <div class="log-json empty">No previous data</div>
                                            <?php else: ?>
                                                <pre class="log-json mb-0"><?= htmlspecialchars($prettyOld) ?></pre>
                                            <?php endif; ?>
                                        </td>
                                        <td data-label="New Data">
                                            <?php if ($prettyNew === '' || strtolower($prettyNew) === 'null'): ?>
                                                <div class="log-json empty">No new data</div>
                                            <?php else: ?>
                                                <pre class="log-json mb-0"><?= htmlspecialchars($prettyNew) ?></pre>
                                            <?php endif; ?>
                                        </td>
                                    </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>

                    <!-- Pagination -->
                    <nav class="p-3 border-top">
                        <ul class="pagination pagination-sm mb-0 justify-content-center flex-wrap">
                            <?php
                            // previous
                            $prevDisabled = $page <= 1 ? ' disabled' : '';
                            $prevQuery = buildQuery(['page' => max(1, $page - 1)]);
                            ?>
                            <li class="page-item<?= $prevDisabled ?>">
                                <a class="page-link" href="<?= $page <= 1 ? '#' : '?' . htmlspecialchars($prevQuery) ?>">
                                    &laquo;
                                </a>
                            </li>

                            <?php
                            // show few pages around current
                            $start = max(1, $page - 2);
                            $end   = min($totalPages, $page + 2);
                            if ($start > 1) {
                                $firstQuery = buildQuery(['page' => 1]);
                                echo '<li class="page-item"><a class="page-link" href="?' . htmlspecialchars($firstQuery) . '">1</a></li>';
                                if ($start > 2) {
                                    echo '<li class="page-item disabled"><span class="page-link">…</span></li>';
                                }
                            }
                            for ($p = $start; $p <= $end; $p++) {
                                $active = $p == $page ? ' active' : '';
                                $q = buildQuery(['page' => $p]);
                                echo '<li class="page-item' . $active . '"><a class="page-link" href="?' . htmlspecialchars($q) . '">' . $p . '</a></li>';
                            }
                            if ($end < $totalPages) {
                                if ($end < $totalPages - 1) {
                                    echo '<li class="page-item disabled"><span class="page-link">…</span></li>';
                                }
                                $lastQuery = buildQuery(['page' => $totalPages]);
                                echo '<li class="page-item"><a class="page-link" href="?' . htmlspecialchars($lastQuery) . '">' . $totalPages . '</a></li>';
                            }

                            // next
                            $nextDisabled = $page >= $totalPages ? ' disabled' : '';
                            $nextQuery = buildQuery(['page' => min($totalPages, $page + 1)]);
                            ?>
                            <li class="page-item<?= $nextDisabled ?>">
                                <a class="page-link" href="<?= $page >= $totalPages ? '#' : '?' . htmlspecialchars($nextQuery) ?>">
                                    &raquo;
                                </a>
                            </li>
                        </ul>
                    </nav>
                <?php endif; ?>
            </div>
        </div>
    </main>

    <footer class="border-top bg-white py-3 small text-center text-muted">
        &copy; <?= date('Y') ?> System Logs
    </footer>
</div>

<!-- Bootstrap 5 JS (optional) -->
<script 
    src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" 
    integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" 
    crossorigin="anonymous">
</script>
</body>
</html>
