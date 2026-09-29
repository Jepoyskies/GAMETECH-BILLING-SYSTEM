<?php
require 'database.php';
include 'header.php';

if (session_status() === PHP_SESSION_NONE) session_start();

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}
$csrf_token = $_SESSION['csrf_token'];

$STATUS_MAP = [
    'active'     => 'success',
    'inactive'   => 'secondary',
    'pending'    => 'warning',
    'suspended'  => 'danger',
    'pull out'   => 'info',
];

$notification = '';
if (!empty($_SESSION['notification'])) {
    $notification = $_SESSION['notification'];
    unset($_SESSION['notification']);
}

$search = isset($_GET['search']) ? trim($_GET['search']) : '';
$start_date = $_GET['start_date'] ?? '';
$end_date   = $_GET['end_date'] ?? '';
$username_status = $_GET['username_status'] ?? '';
$status_filter   = $_GET['status'] ?? '';
$sort_by = $_GET['sort_by'] ?? 'created_at';
$sort_order = strtolower($_GET['sort_order'] ?? 'desc') === 'asc' ? 'asc' : 'desc';
$page = isset($_GET['page']) && is_numeric($_GET['page']) && $_GET['page'] > 0 ? (int)$_GET['page'] : 1;
$per_page = isset($_GET['per_page']) && is_numeric($_GET['per_page']) && $_GET['per_page'] > 0 ? (int)$_GET['per_page'] : 25;

$allowed_sort_cols = [
    'created_at','username','full_name','account_type','address','status','adjusted_by_router','agent','created_form_by','phone','sms_sent_at'
];
if (!in_array($sort_by, $allowed_sort_cols, true)) {
    $sort_by = 'created_at';
}

$conds = [];
$params = [];

if ($username_status === 'has') {
    $conds[] = "COALESCE(username, '') <> ''";
} elseif ($username_status === 'not_connected') {
    $conds[] = "COALESCE(username, '') = ''";
}
if ($status_filter !== '') {
    $conds[] = "LOWER(status) = LOWER(:status_filter)";
    $params[':status_filter'] = $status_filter;
}
if ($start_date) {
    $conds[] = "created_at >= :start_date";
    $params[':start_date'] = $start_date;
}
if ($end_date) {
    $conds[] = "created_at <= :end_date";
    $params[':end_date'] = $end_date;
}
if ($search !== '') {
    $hay = '%' . strtolower($search) . '%';
    $conds[] = "(LOWER(full_name) LIKE :hay 
    OR LOWER(email) LIKE :hay 
    OR LOWER(phone) LIKE :hay 
    OR LOWER(username) LIKE :hay 
    OR LOWER(address) LIKE :hay 
    OR LOWER(account_type) LIKE :hay 
    OR LOWER(agent) LIKE :hay 
    OR LOWER(created_form_by) LIKE :hay 
    OR LOWER(mac_address) LIKE :hay
    OR LOWER(b.name) LIKE :hay)";

    $params[':hay'] = $hay;
}

$sql = "SELECT 
            c.id, c.username, c.created_at, c.full_name, c.email, c.phone, 
            c.address, c.status, c.longitude, c.latitude, 
            c.adjusted_by_router, c.account_type, c.agent, 
            c.created_form_by, c.phone, c.sms_sent_at,
            b.name AS barangay_name
        FROM customers c
        LEFT JOIN barangays b ON c.barangay_id = b.id";



if (!empty($conds)) $sql .= " WHERE " . implode(" AND ", $conds);
$sql .= " ORDER BY " . $sort_by . " " . ($sort_order === 'asc' ? 'ASC' : 'DESC');
$offset = ($page - 1) * $per_page;
$sql .= " LIMIT :limit OFFSET :offset";
$params[':limit'] = (int)$per_page;
$params[':offset'] = (int)$offset;

$stmt = $conn->prepare($sql);
foreach ($params as $k => $v) {
    if ($k === ':limit' || $k === ':offset') $stmt->bindValue($k, (int)$v, PDO::PARAM_INT);
    else $stmt->bindValue($k, $v, PDO::PARAM_STR);
}
$stmt->execute();
$display_rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

$countSql = "SELECT COUNT(*) FROM customers c
             LEFT JOIN barangays b ON c.barangay_id = b.id";

if (!empty($conds)) $countSql .= " WHERE " . implode(" AND ", $conds);
$countStmt = $conn->prepare($countSql);
foreach ($params as $k => $v) {
    if ($k === ':limit' || $k === ':offset') continue;
    $countStmt->bindValue($k, $v, PDO::PARAM_STR);
}
$countStmt->execute();
$total_rows = (int)$countStmt->fetchColumn();
$total_pages = max(1, (int)ceil($total_rows / $per_page));

// UI helpers
$fromRow = $total_rows ? (($page - 1) * $per_page + 1) : 0;
$toRow   = $total_rows ? min($total_rows, $page * $per_page) : 0;

function buildUrl(array $overrides = []): string {
    $q = array_merge($_GET, $overrides);
    return '?' . http_build_query($q);
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>Customers</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet" />

    <style>
        :root{
            --card-radius: 14px;
            --soft-border: rgba(0,0,0,.08);
        }

        body{
            background:
              radial-gradient(1200px 600px at 15% 5%, rgba(13,110,253,.10), transparent 55%),
              radial-gradient(900px 500px at 95% 10%, rgba(32,201,151,.10), transparent 55%),
              #f7f9fc;
        }

        .page-shell{
            background: rgba(255,255,255,.86);
            border: 1px solid var(--soft-border);
            border-radius: var(--card-radius);
            box-shadow: 0 10px 30px rgba(17,24,39,.06);
            backdrop-filter: blur(6px);
        }

        .page-head{
            border-bottom: 1px solid var(--soft-border);
            padding: 1rem 1rem .75rem 1rem;
        }

        .title-wrap h2{ margin:0; }
        .subtle{ color:#6b7280; }

        .filters{
            padding: .9rem 1rem 1rem 1rem;
        }

        .filter-card{
            background: rgba(255,255,255,.9);
            border: 1px solid var(--soft-border);
            border-radius: 12px;
            padding: .75rem;
        }

        .form-control, .form-select{
            border-radius: 10px;
        }

        .btn{
            border-radius: 10px;
        }

        .btn-icon{
            width: 40px;
            height: 40px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0;
        }

        .kpi{
            display:flex;
            gap:.75rem;
            flex-wrap:wrap;
            align-items:center;
        }
        .kpi .pill{
            background:#fff;
            border:1px solid var(--soft-border);
            border-radius:999px;
            padding:.35rem .7rem;
            font-size:.9rem;
            color:#111827;
        }

        .table-wrap{
            border-top: 1px solid var(--soft-border);
            padding: 0 1rem 1rem 1rem;
        }

        .table{
            overflow:hidden;
            border-radius: 12px;
        }

        th.sortable{ cursor:pointer; }
        th.sorted-asc::after { content: " \25B2"; }
        th.sorted-desc::after { content: " \25BC"; }

        .table-sm-custom > :not(caption) > * > * { padding: 0.35rem 0.45rem; font-size: 0.82rem; }
        .table-sm th, .table-sm td { padding: 0.35rem 0.45rem; font-size: 0.82rem; }

        .table th, .table td { white-space: normal !important; word-break: break-word; vertical-align: middle; }
        .col-id { max-width: 52px; }
        .col-status { max-width: 84px; }
        .col-username { max-width: 140px; }
        .col-fullname { max-width: 160px; }
        .col-mac { max-width: 140px; }
        .col-address { max-width: 220px; }
        .col-agent { max-width: 110px; }
        .col-createdat { max-width: 140px; }
        .col-router { max-width: 130px; }
        .col-sms { max-width: 170px; }
        .col-location { max-width: 110px; }

        .action-group .btn{
            border-radius: 10px;
        }

        .badge{
            border-radius: 999px;
            padding: .38rem .55rem;
            font-weight: 600;
        }

        .toast-corner { position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 1060; min-width: 220px; }

        .mobile-card{
            border:1px solid var(--soft-border);
            border-radius: 14px;
            box-shadow: 0 10px 25px rgba(17,24,39,.05);
        }

        .mobile-card .kv{
            display:grid;
            grid-template-columns: 120px 1fr;
            gap:.25rem .75rem;
            font-size:.92rem;
        }

        .mobile-card .kv .k{ color:#6b7280; }
        .mobile-card .kv .v{ color:#111827; font-weight: 500; }

        .pagination .page-link{
            border-radius: 10px !important;
            margin: 0 .15rem;
        }

        @media (max-width: 768px){
            .page-head{ padding: .9rem; }
            .filters{ padding: .75rem .9rem .9rem .9rem; }
            .table-wrap{ padding: 0 .9rem .9rem .9rem; }
        }
    </style>
</head>
<body>

<main class="container py-4">
    <div class="page-shell">
        <div class="page-head d-flex flex-wrap gap-3 align-items-center justify-content-between">
            <div class="title-wrap">
                <h2 class="fw-bold text-primary">
                    <i class="fas fa-users me-2"></i> Customers
                </h2>
                <div class="subtle small">Manage customers, filter, sort, and review details.</div>
            </div>

            <div class="kpi">
                <span class="pill">
                    <i class="fa-solid fa-database me-1 text-primary"></i>
                    Total: <strong><?= number_format($total_rows) ?></strong>
                </span>
                <span class="pill">
                    <i class="fa-solid fa-list-check me-1 text-success"></i>
                    Showing: <strong><?= (int)$fromRow ?>-<?= (int)$toRow ?></strong>
                </span>

                <div class="d-flex gap-2">
                    <a href="add_customer_pppoe.php" class="btn btn-outline-secondary btn-icon" title="Add Customer">
                        <i class="fa-solid fa-user-plus"></i>
                    </a>
                    <a href="serviceplans.php" class="btn btn-outline-secondary btn-icon" title="Service Plans">
                        <i class="fa-solid fa-clipboard-user"></i>
                    </a>
                    <a href="mtpppoe_list.php" class="btn btn-outline-secondary btn-icon" title="PPPoE">
                        <i class="fa-solid fa-computer"></i>
                    </a>
                    <button type="button" class="btn btn-outline-info btn-icon" onclick="location.reload();" title="Refresh">
                        <i class="fa-solid fa-arrows-rotate"></i>
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-icon" title="Reset filters"
                            onclick="window.location='customers.php'">
                        <i class="fa-solid fa-eraser"></i>
                    </button>
                </div>
            </div>
        </div>

        <div class="filters">
            <?php if ($notification): ?>
                <div class="alert alert-info mb-3" role="alert"><?= htmlspecialchars($notification) ?></div>
            <?php endif; ?>

            <div id="notifToast" class="toast toast-corner align-items-center text-bg-primary border-0" role="alert" aria-live="assertive" aria-atomic="true" style="display:none;">
                <div class="d-flex">
                    <div class="toast-body" id="notifToastMsg"></div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>

            <form method="get" id="searchForm" class="filter-card">
                <div class="row g-2 align-items-end">
                    <div class="col-12 col-lg-4">
                        <label class="form-label small subtle mb-1">Search</label>
                        <div class="input-group">
                            <span class="input-group-text bg-white"><i class="fa fa-search"></i></span>
                            <input type="text" id="searchInput" name="search" class="form-control"
                                   placeholder="Name, email, phone, agent, username, MAC..."
                                   value="<?= htmlspecialchars($search) ?>">
                            <button type="submit" class="btn btn-primary" id="searchBtn">Search</button>
                        </div>
                    </div>

                    <div class="col-6 col-md-3 col-lg-2">
                        <label class="form-label small subtle mb-1">Username</label>
                        <select id="usernameStatus" name="username_status" class="form-select">
                            <option value=""<?= $username_status === '' ? ' selected' : '' ?>>All</option>
                            <option value="has"<?= $username_status === 'has' ? ' selected' : '' ?>>Has Username</option>
                            <option value="not_connected"<?= $username_status === 'not_connected' ? ' selected' : '' ?>>Not Connected</option>
                        </select>
                    </div>

                    <div class="col-6 col-md-3 col-lg-2">
                        <label class="form-label small subtle mb-1">Status</label>
                        <select id="statusFilter" name="status" class="form-select">
                            <option value=""<?= $status_filter === '' ? ' selected' : '' ?>>All</option>
                            <?php
                            $STATUS_DEFS = [
                                'active'     => 'Active',
                                'inactive'   => 'Inactive',
                                'pending'    => 'Pending',
                                'suspended'  => 'Suspended',
                                'pull out'   => 'Pull Out'
                            ];
                            foreach ($STATUS_DEFS as $value => $label): ?>
                                <option value="<?= htmlspecialchars($value) ?>"<?= ($status_filter === $value) ? ' selected' : '' ?>>
                                    <?= htmlspecialchars($label) ?>
                                </option>
                            <?php endforeach; ?>
                        </select>
                    </div>

                    <div class="col-6 col-md-3 col-lg-2">
                        <label class="form-label small subtle mb-1">Start date</label>
                        <input type="date" id="startDate" name="start_date" class="form-control" value="<?= htmlspecialchars($start_date) ?>">
                    </div>

                    <div class="col-6 col-md-3 col-lg-2">
                        <label class="form-label small subtle mb-1">End date</label>
                        <input type="date" id="endDate" name="end_date" class="form-control" value="<?= htmlspecialchars($end_date) ?>">
                    </div>

                    <div class="col-12 col-lg-auto ms-lg-auto d-flex align-items-end justify-content-between gap-2">
                        <div>
                            <label class="form-label small subtle mb-1">Per page</label>
                            <select id="perPageSelect" name="per_page" class="form-select"
                                    onchange="document.getElementById('searchForm').submit();">
                                <option value="25"<?= $per_page == 25 ? ' selected' : '' ?>>25</option>
                                <option value="50"<?= $per_page == 50 ? ' selected' : '' ?>>50</option>
                                <option value="100"<?= $per_page == 100 ? ' selected' : '' ?>>100</option>
                            </select>
                        </div>

                        <div class="text-end small subtle d-none d-lg-block" style="max-width:220px;">
                            Tip: type then click Search to filter results.
                        </div>
                    </div>

                    <div class="col-12 d-lg-none">
                        <small class="text-muted">Tip: type then click Search to filter results.</small>
                    </div>
                </div>
            </form>
        </div>

        <div class="table-wrap">
            <div class="table-responsive d-none d-md-block">
                <table class="table table-striped table-hover table-bordered align-middle table-sm-custom table-sm">
                    <thead class="table-light">
                        <tr>
                            <th class="text-nowrap text-center col-action">Actions</th>
                            <th class="text-nowrap text-center col-id">ID</th>
                            <?php
$columns = [
    'status'        => 'Status',
    'created_at'    => 'Created at',
    'username'      => 'Username',
    'full_name'     => 'Full Name',
    'account_type'  => 'Account Type',
    'barangay_name' => 'Barangay', // ✅ ADD THIS
    'address'       => 'Address',
    'agent'         => 'Agent',
    'adjusted_by_router' => 'Router (adjusted by)',
    'created_form_by' => 'Created Form By',
    'phone'   => 'Phone',
    'sms_sent_at'   => 'SMS Sent At',
    'location'      => 'Location'
];

                            $col_classes = [
                                'status' => 'col-status',
                                'created_at' => 'col-createdat',
                                'username' => 'col-username',
                                'full_name' => 'col-fullname',
                                'account_type' => '',
                                'address' => 'col-address',
                                'agent' => 'col-agent',
                                'adjusted_by_router' => 'col-router',
                                'created_form_by' => '',
                                'phone' => 'col-phone',
                                'sms_sent_at' => 'col-sms',
                                'location' => 'col-location'
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

                                    echo "<th class=\"text-nowrap sortable $th_class\">";
                                    echo "<a href=\"$url\" class=\"text-decoration-none text-reset\">$disp</a>";
                                    echo "</th>";
                                } elseif ($col === 'location') {
                                    echo '<th class="text-nowrap text-center col-location">Location</th>';
                                } else {
                                    echo "<th class=\"text-nowrap $th_class\">$disp</th>";
                                }
                            }
                            ?>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <?php if (!empty($display_rows)): ?>
                            <?php foreach ($display_rows as $row): ?>
                                <?php
                                $raw_status = $row['status'] ?? '';
                                $status_class = $STATUS_MAP[$raw_status] ?? 'secondary';
                                ?>
                                <tr data-id="<?= htmlspecialchars($row['id']); ?>">
                                    <td class="text-center col-action">
                                        <div class="btn-group action-group" role="group" aria-label="Actions">
                                            <a href="view_customer.php?id=<?= htmlspecialchars($row['id']); ?>" class="btn btn-outline-secondary btn-sm" title="View">
                                                <i class="fas fa-eye"></i>
                                            </a>
                                            <a href="edit_customer.php?id=<?= htmlspecialchars($row['id']); ?>" class="btn btn-outline-info btn-sm" title="Edit">
                                                <i class="fas fa-edit"></i>
                                            </a>
                                        </div>
                                    </td>
                                    <td class="text-center col-id"><?= htmlspecialchars($row['id']); ?></td>

                                    <td class="col-status">
                                        <span class="badge bg-<?= htmlspecialchars($status_class); ?>">
                                            <?= htmlspecialchars(ucfirst($raw_status)); ?>
                                        </span>
                                    </td>

                                    <td class="col-createdat"><?= htmlspecialchars($row['created_at'] ?? ''); ?></td>

                                    <td class="col-username">
                                        <?php if (!empty($row['username'])): ?>
                                            <?= htmlspecialchars($row['username']); ?>
                                        <?php else: ?>
                                            <span class="badge bg-danger">Not Connected</span>
                                        <?php endif; ?>
                                    </td>

                                    <td class="col-fullname"><?= htmlspecialchars($row['full_name'] ?? ''); ?></td>
                                    <td><?= htmlspecialchars($row['account_type'] ?? ''); ?></td>
<td><?= htmlspecialchars($row['barangay_name'] ?? ''); ?></td>


                                    <td class="d-none d-lg-table-cell col-address"><?= htmlspecialchars($row['address'] ?? ''); ?></td>
                                    <td class="col-agent"><?= htmlspecialchars($row['agent'] ?? ''); ?></td>

                                    <td class="text-center col-router">
                                        <?= !empty($row['adjusted_by_router']) ? htmlspecialchars($row['adjusted_by_router']) : '<span class="text-muted">None</span>'; ?>
                                    </td>

                                    <td><?= htmlspecialchars($row['created_form_by'] ?? ''); ?></td>
                                    <td class="col-phone"><?= htmlspecialchars($row['phone'] ?? ''); ?></td>
                                    <td class="col-sms"><?= htmlspecialchars($row['sms_sent_at'] ?? ''); ?></td>

                                    <td class="text-center col-location">
                                        <?php if (!empty($row['latitude']) && !empty($row['longitude'])): ?>
                                            <a class="text-decoration-none" href="https://www.google.com/maps?q=<?= urlencode($row['latitude']) ?>,<?= urlencode($row['longitude']) ?>" target="_blank" title="View Location on Map">
                                                <i class="fas fa-map-marker-alt text-danger me-1"></i><span class="small">Map</span>
                                            </a>
                                            <div class="small text-muted"><?= htmlspecialchars($row['latitude']) ?>, <?= htmlspecialchars($row['longitude']) ?></div>
                                        <?php else: ?>
                                            <span class="text-muted">No location</span>
                                        <?php endif; ?>
                                    </td>
                                </tr>
                            <?php endforeach; ?>
                        <?php else: ?>
                            <tr><td colspan="15" class="text-center py-4 text-muted">No customers found.</td></tr>
                        <?php endif; ?>
                    </tbody>
                </table>
            </div>

            <!-- Mobile cards -->
            <div class="d-md-none" id="mobileCards">
                <?php if (!empty($display_rows)): ?>
                    <?php foreach ($display_rows as $row): ?>
                        <?php
                        $raw_status = $row['status'] ?? '';
                        $status_class = $STATUS_MAP[$raw_status] ?? 'secondary';
                        ?>
                        <div class="card mobile-card mb-3" data-id="<?= htmlspecialchars($row['id']); ?>">
                            <div class="card-body py-3">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <span class="badge bg-<?= htmlspecialchars($status_class); ?>">
                                        <?= htmlspecialchars(ucfirst($raw_status)); ?>
                                    </span>

                                    <div class="btn-group" role="group" aria-label="Actions">
                                        <a href="view_customer.php?id=<?= htmlspecialchars($row['id']); ?>" class="btn btn-outline-secondary btn-sm" title="View">
                                            <i class="fas fa-eye"></i>
                                        </a>
                                        <a href="edit_customer.php?id=<?= htmlspecialchars($row['id']); ?>" class="btn btn-outline-info btn-sm" title="Edit">
                                            <i class="fas fa-edit"></i>
                                        </a>
                                    </div>
                                </div>

                                <div class="kv">
                                    <div class="k">ID</div><div class="v"><?= htmlspecialchars($row['id']); ?></div>
                                    <div class="k">Created</div><div class="v"><?= htmlspecialchars($row['created_at'] ?? ''); ?></div>
                                    <div class="k">Username</div>
                                    <div class="v">
                                        <?= !empty($row['username']) ? htmlspecialchars($row['username']) : '<span class="badge bg-danger">Not Connected</span>'; ?>
                                    </div>
                                    <div class="k">Full name</div><div class="v"><?= htmlspecialchars($row['full_name'] ?? ''); ?></div>
                                    <div class="k">Account type</div><div class="v"><?= htmlspecialchars($row['account_type'] ?? ''); ?></div>
                                    <div class="k">Barangay</div><div class="v"><?= htmlspecialchars($row['barangay_name'] ?? ''); ?></div>

                                    <div class="k">Address</div><div class="v"><?= htmlspecialchars($row['address'] ?? ''); ?></div>
                                    <div class="k">Agent</div><div class="v"><?= htmlspecialchars($row['agent'] ?? ''); ?></div>
                                    <div class="k">Router</div><div class="v"><?= htmlspecialchars($row['adjusted_by_router'] ?? 'None'); ?></div>
                                    <div class="k">Created by</div><div class="v"><?= htmlspecialchars($row['created_form_by'] ?? ''); ?></div>
                                    <div class="k">Phone</div><div class="v"><?= htmlspecialchars($row['phone'] ?? ''); ?></div>
                                    <div class="k">SMS sent</div><div class="v"><?= htmlspecialchars($row['sms_sent_at'] ?? ''); ?></div>
                                </div>

                                <div class="mt-3 small text-muted">
                                    <?php if (!empty($row['latitude']) && !empty($row['longitude'])): ?>
                                        <a class="text-decoration-none" href="https://www.google.com/maps?q=<?= urlencode($row['latitude']) ?>,<?= urlencode($row['longitude']) ?>" target="_blank" title="View Location on Map">
                                            <i class="fas fa-map-marker-alt text-danger me-1"></i>Open in Google Maps
                                        </a>
                                        <div><?= htmlspecialchars($row['latitude']) ?>, <?= htmlspecialchars($row['longitude']) ?></div>
                                    <?php else: ?>
                                        <span>No location</span>
                                    <?php endif; ?>
                                </div>
                            </div>
                        </div>
                    <?php endforeach; ?>
                <?php else: ?>
                    <div class="alert alert-info text-center">No customers found.</div>
                <?php endif; ?>
            </div>

            <?php if ($total_pages > 1): ?>
                <nav aria-label="Page navigation" class="mt-3">
                    <ul class="pagination justify-content-center flex-wrap">
                        <li class="page-item <?= ($page <= 1) ? 'disabled' : '' ?>">
                            <a class="page-link" href="<?= buildUrl(['page'=>max(1, $page-1)]) ?>" aria-label="Previous">&laquo;</a>
                        </li>

                        <?php
                        // nicer pagination window
                        $window = 2;
                        $startP = max(1, $page - $window);
                        $endP = min($total_pages, $page + $window);

                        if ($startP > 1) {
                            echo '<li class="page-item"><a class="page-link" href="'.buildUrl(['page'=>1]).'">1</a></li>';
                            if ($startP > 2) echo '<li class="page-item disabled"><span class="page-link">…</span></li>';
                        }

                        for ($p = $startP; $p <= $endP; $p++): ?>
                            <li class="page-item <?= ($p == $page) ? 'active' : '' ?>">
                                <a class="page-link" href="<?= buildUrl(['page'=>$p]) ?>"><?= $p; ?></a>
                            </li>
                        <?php endfor;

                        if ($endP < $total_pages) {
                            if ($endP < $total_pages - 1) echo '<li class="page-item disabled"><span class="page-link">…</span></li>';
                            echo '<li class="page-item"><a class="page-link" href="'.buildUrl(['page'=>$total_pages]).'">'.$total_pages.'</a></li>';
                        }
                        ?>

                        <li class="page-item <?= ($page >= $total_pages) ? 'disabled' : '' ?>">
                            <a class="page-link" href="<?= buildUrl(['page'=>min($total_pages, $page+1)]) ?>" aria-label="Next">&raquo;</a>
                        </li>
                    </ul>
                </nav>
            <?php endif; ?>

            <input type="hidden" id="csrf_token" value="<?= htmlspecialchars($csrf_token) ?>">
        </div>
    </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
<?php
if (function_exists('ob_end_flush')) @ob_end_flush();
?>
