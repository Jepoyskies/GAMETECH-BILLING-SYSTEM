<?php
// rebates_history.php

require 'header.php';
include 'database.php';

// 1. Get username
if (!isset($_GET['username']) || trim($_GET['username']) === '') {
    echo "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Error</title>
          <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'>
          </head><body class='bg-light'>
          <main class='container py-5'>
            <div class='alert alert-danger'>Username is required.</div>
          </main></body></html>";
    exit;
}
$username = $_GET['username'];

// 2. Pagination logic
$limit  = 10;
$page   = (isset($_GET['page']) && is_numeric($_GET['page'])) ? max(1, (int)$_GET['page']) : 1;
$offset = ($page - 1) * $limit;

// 3. Count total logs
$count_stmt = $pdo->prepare("SELECT COUNT(*) FROM rebates WHERE username = ?");
$count_stmt->execute([$username]);
$total_logs  = (int)$count_stmt->fetchColumn();
$total_pages = (int)ceil($total_logs / $limit);

// 4. Fetch logs
$stmt = $pdo->prepare(
    "SELECT plan_name, days, expires_at, current_expiry, paid_at, created_at, adjusted_by, note
     FROM rebates
     WHERE username = ?
     ORDER BY created_at DESC
     LIMIT ?, ?"
);
$stmt->bindValue(1, $username, PDO::PARAM_STR);
$stmt->bindValue(2, (int)$offset, PDO::PARAM_INT);
$stmt->bindValue(3, (int)$limit, PDO::PARAM_INT);
$stmt->execute();
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Rebates History - <?php echo htmlspecialchars($username); ?></title>

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.10.5/font/bootstrap-icons.min.css" rel="stylesheet">

    <style>
        body { background-color:#f5f6fa; }
        .page-header {
            display:flex;
            flex-wrap:wrap;
            align-items:center;
            justify-content:space-between;
            gap:10px;
            margin-bottom:1.5rem;
        }
        .page-header h2 {
            margin:0;
            font-size:1.4rem;
            font-weight:600;
        }
        .card-simple {
            border-radius:10px;
            border:1px solid #e1e5ee;
        }
        .card-simple .card-header {
            background:#fff;
            border-bottom:1px solid #e1e5ee;
            font-weight:600;
        }
        .table th, .table td {
            vertical-align:middle;
            font-size:0.9rem;
        }
        .table thead th {
            background:#f8f9fc;
            font-weight:600;
        }
        .search-input {
            max-width:260px;
        }
        .receipt-box {
            display:none;
            background:#fff;
            border-radius:8px;
            border:1px solid #e1e5ee;
            padding:12px 16px;
            width:320px;
            font-size:0.9rem;
        }
        .receipt-box .header {
            font-size:1rem;
            font-weight:600;
            color:#0d6efd;
            text-align:center;
            margin-bottom:8px;
        }
        .receipt-box .item { margin-bottom:4px; }
        .receipt-box .item strong {
            min-width:120px;
            display:inline-block;
        }
        th.sortable {
            cursor:pointer;
            user-select:none;
            white-space:nowrap;
        }
        th.sortable:after {
            content:'\2195';
            font-size:0.7rem;
            margin-left:4px;
            color:#aaa;
        }
        th.sortable.asc:after {
            content:'\2191';
            color:#0d6efd;
        }
        th.sortable.desc:after {
            content:'\2193';
            color:#0d6efd;
        }
        @media (max-width: 767.98px) {
            .table-wrapper { display:none; }
        }
        @media (min-width: 768px) {
            .cards-wrapper { display:none; }
        }
    </style>
</head>
<body>
<main class="container py-4" style="min-height:100vh;">

    <div class="page-header">
        <h2>
            Rebates / Adjustments for
            <span class="text-primary"><?php echo htmlspecialchars($username); ?></span>
        </h2>
        <div class="d-flex flex-wrap gap-2">
            <a href="subscription_plans.php" class="btn btn-outline-secondary btn-sm">
                <i class="bi bi-arrow-left me-1"></i>
            </a>
            <button type="button" onclick="location.reload();" class="btn btn-outline-primary btn-sm">
                <i class="bi bi-arrow-clockwise me-1"></i> Refresh
            </button>
        </div>
    </div>

    <?php if (isset($_GET['success']) && $_GET['success'] == 1): ?>
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            Payment processed successfully.
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    <?php endif; ?>

    <div class="card card-simple">
        <div class="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
            <span>History</span>
            <?php if ($rows && count($rows) > 0): ?>
                <input id="tableSearch" type="text" class="form-control form-control-sm search-input"
                       placeholder="Search in results">
            <?php endif; ?>
        </div>
        <div class="card-body">

            <?php if ($rows && count($rows) > 0): ?>

                <!-- Desktop / tablet table -->
                <div class="table-wrapper table-responsive mb-2">
                    <table class="table table-sm table-striped mb-0">
                        <thead>
                        <tr>
                            <th class="sortable" data-sort-col="created_at">Created</th>
                            <th class="sortable" data-sort-col="plan_name">Plan</th>
                            <th class="sortable" data-sort-col="days">Days</th>
                            <th class="sortable" data-sort-col="expires_at">New Expiry</th> 
                            <th class="sortable" data-sort-col="current_expiry">Old Expiry</th>
                            <th class="sortable" data-sort-col="adjusted_by">Adjusted By</th>
                            <th class="sortable" data-sort-col="note">Note</th>
                            <th style="width:110px;" class="text-center">Receipt</th>
                        </tr>
                        </thead>
                        <tbody>
                        <?php foreach ($rows as $i => $row): ?>
                            <tr>
                                <td><?php echo htmlspecialchars($row['created_at'] ?? ''); ?></td>
                                <td><?php echo htmlspecialchars($row['plan_name'] ?? ''); ?></td>
                                <td><?php echo htmlspecialchars($row['days'] ?? ''); ?></td>
                                <td><?php echo htmlspecialchars($row['expires_at'] ?? ''); ?></td>
                                <td><?php echo htmlspecialchars($row['current_expiry'] ?? ''); ?></td>
                                <td><?php echo htmlspecialchars($row['adjusted_by'] ?? ''); ?></td>
                                <td><?php echo htmlspecialchars($row['note'] ?? ''); ?></td>
                                <td class="text-center">
                                    <button class="btn btn-light btn-sm me-1"
                                            title="Print receipt"
                                            onclick="printReceiptImage('receipt-row-<?php echo $i; ?>','<?php echo $row['paid_at']; ?>')">
                                        <i class="bi bi-printer"></i>
                                    </button>
                                    <button class="btn btn-light btn-sm"
                                            title="Download image"
                                            onclick="downloadJPEG('receipt-row-<?php echo $i; ?>','<?php echo $row['paid_at']; ?>')">
                                        <i class="bi bi-image"></i>
                                    </button>

                                    <!-- Hidden receipt content -->
                                    <div id="receipt-row-<?php echo $i; ?>" class="receipt-box">
                                        <div class="header">Payment Receipt</div>
                                        <div class="item"><strong>Username:</strong> <?php echo htmlspecialchars($username); ?></div>
                                        <div class="item"><strong>Plan:</strong> <?php echo htmlspecialchars($row['plan_name'] ?? ''); ?></div>
                                        <div class="item"><strong>Days:</strong> <?php echo htmlspecialchars($row['days'] ?? ''); ?></div>
                                        <div class="item"><strong>New Expiry:</strong> <?php echo htmlspecialchars($row['expires_at'] ?? ''); ?></div>
                                        <div class="item"><strong>Old Expiry:</strong> <?php echo htmlspecialchars($row['current_expiry'] ?? ''); ?></div>
                                        <div class="item"><strong>Paid At:</strong> <?php echo htmlspecialchars($row['paid_at'] ?? ''); ?></div>
                                        <div class="item"><strong>Adjusted By:</strong> <?php echo htmlspecialchars($row['adjusted_by'] ?? ''); ?></div>
                                    </div>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>

                <!-- Mobile cards -->
                <div class="cards-wrapper">
                    <?php foreach ($rows as $cardIndex => $row): ?>
                        <div class="card mb-2 shadow-sm">
                            <div class="card-body">
                                <div class="d-flex justify-content-between mb-1">
                                    <div>
                                        <div class="fw-semibold small">
                                            <?php echo htmlspecialchars($row['plan_name'] ?? ''); ?>
                                        </div>
                                        <div class="text-muted small">
                                            Created: <?php echo htmlspecialchars($row['created_at'] ?? ''); ?>
                                        </div>
                                    </div>
                                    <div class="text-muted small text-end">
                                        Paid: <?php echo htmlspecialchars($row['paid_at'] ?? ''); ?>
                                    </div>
                                </div>

                                <div class="small mb-2">
                                    <div><strong>Days:</strong> <?php echo htmlspecialchars($row['days'] ?? ''); ?></div>
                                    <div><strong>New Expiry:</strong> <?php echo htmlspecialchars($row['expires_at'] ?? ''); ?></div>
                                    <div><strong>Old Expiry:</strong> <?php echo htmlspecialchars($row['current_expiry'] ?? ''); ?></div>
                                    <div><strong>Adjusted By:</strong> <?php echo htmlspecialchars($row['adjusted_by'] ?? ''); ?></div>
                                    <?php if (!empty($row['note'])): ?>
                                        <div><strong>Note:</strong> <?php echo htmlspecialchars($row['note']); ?></div>
                                    <?php endif; ?>
                                </div>

                                <div class="d-flex gap-2">
                                    <button type="button"
                                            class="btn btn-outline-primary btn-sm"
                                            onclick="printReceiptImage('receipt-row-m-<?php echo $cardIndex; ?>','<?php echo $row['paid_at']; ?>')">
                                        <i class="bi bi-printer me-1"></i>Print
                                    </button>
                                    <button type="button"
                                            class="btn btn-outline-secondary btn-sm"
                                            onclick="downloadJPEG('receipt-row-m-<?php echo $cardIndex; ?>','<?php echo $row['paid_at']; ?>')">
                                        <i class="bi bi-image me-1"></i>Image
                                    </button>
                                </div>

                                <!-- Hidden receipt for mobile -->
                                <div id="receipt-row-m-<?php echo $cardIndex; ?>" class="receipt-box">
                                    <div class="header">Payment Receipt</div>
                                    <div class="item"><strong>Username:<br></strong> <?php echo htmlspecialchars($username); ?></div>
                                    <div class="item"><strong>Plan:</strong> <?php echo htmlspecialchars($row['plan_name'] ?? ''); ?></div>
                                    <div class="item"><strong>Days:</strong> <?php echo htmlspecialchars($row['days'] ?? ''); ?></div>
                                    <div class="item"><strong>New Expiry:</strong> <?php echo htmlspecialchars($row['expires_at'] ?? ''); ?></div>
                                    <div class="item"><strong>Old Expiry:</strong> <?php echo htmlspecialchars($row['current_expiry'] ?? ''); ?></div>
                                    <div class="item"><strong>Paid At:</strong> <?php echo htmlspecialchars($row['paid_at'] ?? ''); ?></div>
                                    <div class="item"><strong>Adjusted By:</strong> <?php echo htmlspecialchars($row['adjusted_by'] ?? ''); ?></div>
                                </div>
                            </div>
                        </div>
                    <?php endforeach; ?>
                </div>

                <!-- Pagination -->
                <?php if ($total_pages > 1): ?>
                    <nav class="mt-3" aria-label="Page navigation">
                        <ul class="pagination pagination-sm justify-content-center mb-0">
                            <li class="page-item<?php if ($page <= 1) echo ' disabled'; ?>">
                                <a class="page-link" href="?username=<?php echo urlencode($username); ?>&page=1">&laquo;</a>
                            </li>
                            <li class="page-item<?php if ($page <= 1) echo ' disabled'; ?>">
                                <a class="page-link" href="?username=<?php echo urlencode($username); ?>&page=<?php echo max(1, $page-1); ?>">&lsaquo;</a>
                            </li>
                            <?php
                            $start = max(1, $page - 2);
                            $end   = min($total_pages, $page + 2);
                            for ($p = $start; $p <= $end; $p++): ?>
                                <li class="page-item<?php if ($p == $page) echo ' active'; ?>">
                                    <a class="page-link" href="?username=<?php echo urlencode($username); ?>&page=<?php echo $p; ?>">
                                        <?php echo $p; ?>
                                    </a>
                                </li>
                            <?php endfor; ?>
                            <li class="page-item<?php if ($page >= $total_pages) echo ' disabled'; ?>">
                                <a class="page-link" href="?username=<?php echo urlencode($username); ?>&page=<?php echo min($total_pages, $page+1); ?>">&rsaquo;</a>
                            </li>
                            <li class="page-item<?php if ($page >= $total_pages) echo ' disabled'; ?>">
                                <a class="page-link" href="?username=<?php echo urlencode($username); ?>&page=<?php echo $total_pages; ?>">&raquo;</a>
                            </li>
                        </ul>
                    </nav>
                <?php endif; ?>

            <?php else: ?>
                <p class="text-muted mb-0">No rebate or adjustment records found for this user.</p>
            <?php endif; ?>

        </div>
    </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
function printReceiptImage(receiptId, paidAt) {
    var receipt = document.getElementById(receiptId);
    if (!receipt) return;
    receipt.style.display = 'block';

    html2canvas(receipt).then(function (canvas) {
        var imgData = canvas.toDataURL('image/jpeg', 1.0);
        var printWindow = window.open('', '_blank');
        if (!printWindow) {
            receipt.style.display = 'none';
            return;
        }
        printWindow.document.write(
            '<html><head><title>Receipt</title></head>' +
            '<body style="margin:0;text-align:center;background:#f5f5f5;">' +
            '<img src="' + imgData + '" style="max-width:100%;margin:10px auto;" ' +
            'onload="window.print();window.close();" />' +
            '</body></html>'
        );
        printWindow.document.close();
        receipt.style.display = 'none';
    });
}

function downloadJPEG(receiptId, paidAt) {
    var receipt = document.getElementById(receiptId);
    if (!receipt) return;
    receipt.style.display = 'block';

    html2canvas(receipt).then(function (canvas) {
        var link = document.createElement('a');
        link.download = 'receipt_' + (paidAt ? paidAt.replace(/[^0-9]/g, '') : Date.now()) + '.jpeg';
        link.href = canvas.toDataURL('image/jpeg', 1.0);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        receipt.style.display = 'none';
    });
}

document.addEventListener('DOMContentLoaded', function () {
    var searchInput = document.getElementById('tableSearch');
    var table = document.querySelector('.table-wrapper table');
    if (!table) return;

    var tbody = table.querySelector('tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));

    // Search
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            var term = this.value.toLowerCase();
            rows.forEach(function (row) {
                var text = row.innerText.toLowerCase();
                row.style.display = text.indexOf(term) !== -1 ? '' : 'none';
            });
        });
    }

    // Sort
    var headers = table.querySelectorAll('th.sortable');
    var currentSort = { index: null, direction: 'asc' };

    headers.forEach(function (th, index) {
        th.addEventListener('click', function () {
            var visibleRows = rows.filter(function (r) { return r.style.display !== 'none'; });

            if (currentSort.index === index) {
                currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.index = index;
                currentSort.direction = 'asc';
            }

            headers.forEach(function (h) { h.classList.remove('asc', 'desc'); });
            th.classList.add(currentSort.direction);

            var isNumericCol = ['days'].includes(th.getAttribute('data-sort-col'));

            visibleRows.sort(function (a, b) {
                var aText = a.children[index].innerText.trim();
                var bText = b.children[index].innerText.trim();

                if (isNumericCol) {
                    var aNum = parseFloat(aText) || 0;
                    var bNum = parseFloat(bText) || 0;
                    return currentSort.direction === 'asc' ? aNum - bNum : bNum - aNum;
                } else {
                    var aDate = Date.parse(aText);
                    var bDate = Date.parse(bText);
                    if (!isNaN(aDate) && !isNaN(bDate)) {
                        return currentSort.direction === 'asc' ? aDate - bDate : bDate - aDate;
                    }
                    aText = aText.toLowerCase();
                    bText = bText.toLowerCase();
                    if (aText < bText) return currentSort.direction === 'asc' ? -1 : 1;
                    if (aText > bText) return currentSort.direction === 'asc' ? 1 : -1;
                    return 0;
                }
            });

            visibleRows.forEach(function (row) {
                tbody.appendChild(row);
            });
        });
    });
});
</script>

<?php include 'footer.php'; ?>
