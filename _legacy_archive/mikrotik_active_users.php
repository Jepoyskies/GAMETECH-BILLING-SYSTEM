<?php
require_once __DIR__ . '/MikrotikManager/MikrotikManager_active_users.php';

// Default values if MikroTikManager_active.php didn't set them
$error_msg    = $error_msg ?? '';
$ppp_active   = $ppp_active ?? [];
$hs_active    = $hs_active ?? [];
$allActive    = $allActive ?? [];
$devicesError = $devicesError ?? '';
$errors       = $errors ?? [];

/**
 * SEARCH
 * q : search query
 */
$q = isset($_GET['q']) ? trim($_GET['q']) : '';

if ($q !== '') {
    $qLower = mb_strtolower($q);
    $allActive = array_values(array_filter($allActive, function ($row) use ($qLower) {
        $fields = [
            $row['device']  ?? '',
            $row['name']    ?? '',
            $row['address'] ?? '',
            $row['uptime']  ?? '',
            $row['service'] ?? '',
        ];
        foreach ($fields as $f) {
            if (mb_strpos(mb_strtolower((string)$f), $qLower) !== false) {
                return true;
            }
        }
        return false;
    }));
}

/**
 * SORTING
 */
$validSortColumns = ['device', 'name', 'address', 'uptime', 'service'];
$sort   = isset($_GET['sort']) && in_array($_GET['sort'], $validSortColumns, true) ? $_GET['sort'] : 'name';
$order  = isset($_GET['order']) && in_array(strtolower($_GET['order']), ['asc', 'desc'], true) ? strtolower($_GET['order']) : 'asc';

usort($allActive, function ($a, $b) use ($sort, $order) {
    $va = $a[$sort] ?? '';
    $vb = $b[$sort] ?? '';

    $va = is_string($va) ? mb_strtolower($va) : $va;
    $vb = is_string($vb) ? mb_strtolower($vb) : $vb;

    if ($va == $vb) return 0;
    if ($order === 'asc') {
        return ($va < $vb) ? -1 : 1;
    }
    return ($va > $vb) ? -1 : 1;
});

/**
 * PAGINATION
 */
$totalActiveUsers = count($allActive);
$perPage          = isset($_GET['per_page']) && ctype_digit($_GET['per_page']) && (int)$_GET['per_page'] > 0
                    ? (int)$_GET['per_page']
                    : 10;

$totalPages = $totalActiveUsers > 0 ? (int)ceil($totalActiveUsers / $perPage) : 1;
$page       = isset($_GET['page']) && ctype_digit($_GET['page']) && (int)$_GET['page'] > 0
              ? (int)$_GET['page']
              : 1;
$page       = min($page, $totalPages);

$offset     = ($page - 1) * $perPage;
$rowsToShow = array_slice($allActive, $offset, $perPage);

/**
 * Helpers
 */
function buildUrl(array $params = []): string
{
    $query = array_merge($_GET, $params);
    return htmlspecialchars('?' . http_build_query($query));
}

function sortOrderFor(string $column, string $currentSort, string $currentOrder): string
{
    if ($currentSort === $column) {
        return $currentOrder === 'asc' ? 'desc' : 'asc';
    }
    return 'asc';
}

// Helper to clear all filters/sort/pagination for refresh (keep none)
$refreshUrl = htmlspecialchars($_SERVER['PHP_SELF']);
?>
<!-- Page-specific content starts here -->
<main class="container py-4">


        <!-- Active PPPoE Users from all devices -->
        <div class="col-12">
            <div class="card shadow-sm border-0 mb-4">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">

                            <h2 class="mb-0 fw-bold text-primary"><i class="fa-solid fa-computer"></i> Mikrotik Active Users</h2> <br>
                  

                        <!-- Section refresh (keeps filters/sort/page) -->
                        <a href="<?php echo htmlspecialchars('?' . http_build_query($_GET)); ?>"
                           class="btn btn-sm btn-outline-primary">
                            Refresh List
                        </a>
                    </div>

                    <?php if (!empty($devicesError)): ?>
                        <div class="alert alert-danger"><?php echo htmlspecialchars($devicesError); ?></div>
                    <?php endif; ?>

                    <?php if (!empty($errors)): ?>
                        <div class="alert alert-warning">
                            <?php foreach ($errors as $e): ?>
                                <div><?php echo htmlspecialchars($e); ?></div>
                            <?php endforeach; ?>
                        </div>
                    <?php endif; ?>

                    <div class="mb-3 d-flex flex-wrap align-items-center justify-content-between gap-2">
                        <span class="badge bg-success">
                            Total Active Users: <?php echo $totalActiveUsers; ?>
                            <?php if ($q !== ''): ?>
                                (filtered)
                            <?php endif; ?>
                        </span>

                        <!-- Search form -->
                        <form method="get" class="d-flex align-items-center flex-wrap gap-2" id="searchForm">
                            <?php
                            // preserve all GET parameters except 'q' and 'page'
                            foreach ($_GET as $k => $v):
                                if (in_array($k, ['q', 'page'], true)) {
                                    continue;
                                }
                                ?>
                                <input type="hidden" name="<?php echo htmlspecialchars($k); ?>"
                                       value="<?php echo htmlspecialchars($v); ?>">
                            <?php endforeach; ?>

                            <div class="input-group input-group-sm">
                                <input
                                    type="text"
                                    class="form-control"
                                    name="q"
                                    id="searchInput"
                                    placeholder="Search user, device, IP, service\..."
                                    value="<?php echo htmlspecialchars($q); ?>"
                                    autocomplete="off"
                                >
                                <button class="btn btn-outline-secondary" type="submit">
                                    Search
                                </button>
                                <?php if ($q !== ''): ?>
                                    <a class="btn btn-outline-danger"
                                       href="<?php
                                       $params = $_GET;
                                       unset($params['q'], $params['page']);
                                       echo htmlspecialchars('?' . http_build_query($params));
                                       ?>">
                                        Clear
                                    </a>
                                <?php endif; ?>
                            </div>
                        </form>
                    </div>

                    <!-- Rows per page selector -->
                    <div class="mb-3 d-flex justify-content-end">
                        <form method="get" class="d-flex align-items-center">
                            <?php
                            // Preserve existing GET params except per_page and page
                            foreach ($_GET as $k => $v):
                                if (in_array($k, ['per_page', 'page'], true)) {
                                    continue;
                                }
                                ?>
                                <input type="hidden" name="<?php echo htmlspecialchars($k); ?>"
                                       value="<?php echo htmlspecialchars($v); ?>">
                            <?php endforeach; ?>
                            <label class="me-2 mb-0" for="per_page">Rows per page:</label>
                            <select id="per_page" name="per_page" class="form-select form-select-sm"
                                    style="width:auto" onchange="this.form.submit()">
                                <?php foreach ([5,10,25,50,100] as $size): ?>
                                    <option value="<?php echo $size; ?>" <?php echo $perPage === $size ? 'selected' : ''; ?>>
                                        <?php echo $size; ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </form>
                    </div>

                    <?php if (empty($allActive)): ?>
                        <p class="text-muted mb-0">
                            <?php if ($q !== ''): ?>
                                No active PPPoE sessions match your search.
                            <?php else: ?>
                                No active PPPoE sessions found.
                            <?php endif; ?>
                        </p>
                    <?php else: ?>
                        <div class="table-responsive">
                            <table class="table table-striped table-bordered align-middle">
                                <thead class="table-light">
                                <tr>
                                    <th style="width:60px">#</th>
                                    <th>
                                        <a href="<?php echo buildUrl([
                                            'sort'  => 'device',
                                            'order' => sortOrderFor('device', $sort, $order),
                                            'page'  => 1
                                        ]); ?>">
                                            Device
                                            <?php if ($sort === 'device'): ?>
                                                <?php echo $order === 'asc' ? '&uarr;' : '&darr;'; ?>
                                            <?php endif; ?>
                                        </a>
                                    </th>
                                    <th>
                                        <a href="<?php echo buildUrl([
                                            'sort'  => 'name',
                                            'order' => sortOrderFor('name', $sort, $order),
                                            'page'  => 1
                                        ]); ?>">
                                            User
                                            <?php if ($sort === 'name'): ?>
                                                <?php echo $order === 'asc' ? '&uarr;' : '&darr;'; ?>
                                            <?php endif; ?>
                                        </a>
                                    </th>
                                    <th>
                                        <a href="<?php echo buildUrl([
                                            'sort'  => 'address',
                                            'order' => sortOrderFor('address', $sort, $order),
                                            'page'  => 1
                                        ]); ?>">
                                            Address
                                            <?php if ($sort === 'address'): ?>
                                                <?php echo $order === 'asc' ? '&uarr;' : '&darr;'; ?>
                                            <?php endif; ?>
                                        </a>
                                    </th>
                                    <th>
                                        <a href="<?php echo buildUrl([
                                            'sort'  => 'uptime',
                                            'order' => sortOrderFor('uptime', $sort, $order),
                                            'page'  => 1
                                        ]); ?>">
                                            Uptime
                                            <?php if ($sort === 'uptime'): ?>
                                                <?php echo $order === 'asc' ? '&uarr;' : '&darr;'; ?>
                                            <?php endif; ?>
                                        </a>
                                    </th>
                                    <th>
                                        <a href="<?php echo buildUrl([
                                            'sort'  => 'service',
                                            'order' => sortOrderFor('service', $sort, $order),
                                            'page'  => 1
                                        ]); ?>">
                                            Service
                                            <?php if ($sort === 'service'): ?>
                                                <?php echo $order === 'asc' ? '&uarr;' : '&darr;'; ?>
                                            <?php endif; ?>
                                        </a>
                                    </th>
                                </tr>
                                </thead>
                                <tbody>
                                <?php foreach ($rowsToShow as $idx => $row): ?>
                                    <tr>
                                        <td><?php echo $offset + $idx + 1; ?></td>
                                        <td><?php echo htmlspecialchars($row['device'] ?? ''); ?></td>
                                        <td><?php echo htmlspecialchars($row['name'] ?? ''); ?></td>
                                        <td><?php echo htmlspecialchars($row['address'] ?? ''); ?></td>
                                        <td><?php echo htmlspecialchars($row['uptime'] ?? ''); ?></td>
                                        <td><?php echo htmlspecialchars($row['service'] ?? ''); ?></td>
                                    </tr>
                                <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>

                        <!-- Pagination controls -->
                        <?php if ($totalPages > 1): ?>
                            <nav aria-label="Active users pagination">
                                <ul class="pagination pagination-sm justify-content-center mb-0">
                                    <!-- Previous -->
                                    <li class="page-item <?php echo $page <= 1 ? 'disabled' : ''; ?>">
                                        <a class="page-link"
                                           href="<?php echo $page > 1 ? buildUrl(['page' => $page - 1]) : '#'; ?>"
                                           tabindex="-1">Previous</a>
                                    </li>

                                    <!-- Page numbers -->
                                    <?php
                                    $window = 2;
                                    $start  = max(1, $page - $window);
                                    $end    = min($totalPages, $page + $window);

                                    if ($start > 1): ?>
                                        <li class="page-item">
                                            <a class="page-link" href="<?php echo buildUrl(['page' => 1]); ?>">1</a>
                                        </li>
                                        <?php if ($start > 2): ?>
                                            <li class="page-item disabled"><span class="page-link">\~</span></li>
                                        <?php endif; ?>
                                    <?php endif; ?>

                                    <?php for ($p = $start; $p <= $end; $p++): ?>
                                        <li class="page-item <?php echo $p === $page ? 'active' : ''; ?>">
                                            <a class="page-link" href="<?php echo buildUrl(['page' => $p]); ?>">
                                                <?php echo $p; ?>
                                            </a>
                                        </li>
                                    <?php endfor; ?>

                                    <?php if ($end < $totalPages): ?>
                                        <?php if ($end < $totalPages - 1): ?>
                                            <li class="page-item disabled"><span class="page-link">\~</span></li>
                                        <?php endif; ?>
                                        <li class="page-item">
                                            <a class="page-link"
                                               href="<?php echo buildUrl(['page' => $totalPages]); ?>">
                                                <?php echo $totalPages; ?>
                                            </a>
                                        </li>
                                    <?php endif; ?>

                                    <!-- Next -->
                                    <li class="page-item <?php echo $page >= $totalPages ? 'disabled' : ''; ?>">
                                        <a class="page-link"
                                           href="<?php echo $page < $totalPages ? buildUrl(['page' => $page + 1]) : '#'; ?>">
                                            Next
                                        </a>
                                    </li>
                                </ul>
                            </nav>
                        <?php endif; ?>
                    <?php endif; ?>

                </div>
            </div>
        </div>
    </div>
</main>
<!-- Page-specific content ends -->

<!-- Automatic search on typing (debounced) -->
<script>
(function () {
    const input = document.getElementById('searchInput');
    const form  = document.getElementById('searchForm');
    if (!input || !form) return;

    let timer = null;
    input.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
            const pageInput = form.querySelector('input[name="page"]');
            if (pageInput) {
                pageInput.value = 1;
            } else {
                const hidden = document.createElement('input');
                hidden.type = 'hidden';
                hidden.name = 'page';
                hidden.value = '1';
                form.appendChild(hidden);
            }
            form.submit();
        }, 500); // debounce delay
    });
})();
</script>

<?php include 'footer.php'; ?>
