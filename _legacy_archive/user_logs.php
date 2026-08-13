<?php
// payment_history.php

require 'header.php';
include 'database.php';

// Validate username
if (!isset($_GET['username']) || trim($_GET['username']) === '') {
    echo "<p class='text-center mt-5'>Username is required.</p>";
    include 'footer.php';
    exit;
}
$username = $_GET['username'];

// Pagination
$limit = 10;
$page  = isset($_GET['page']) && is_numeric($_GET['page'])
    ? max(1, (int)$_GET['page'])
    : 1;
$offset = ($page - 1) * $limit;

// Count total logs
$count_stmt = $pdo->prepare("SELECT COUNT(*) FROM payments WHERE username = ?");
$count_stmt->execute([$username]);
$total_logs  = (int)$count_stmt->fetchColumn();
$total_pages = (int)ceil($total_logs / $limit);

// Fetch logs for current page
$stmt = $pdo->prepare(
    "SELECT id, plan_name, created_at, amount, days, expires_at, paid_at, adjusted_by
     FROM payments
     WHERE username = ?
     ORDER BY paid_at DESC
     LIMIT ? OFFSET ?"
);
$stmt->bindValue(1, $username, PDO::PARAM_STR);
$stmt->bindValue(2, $limit, PDO::PARAM_INT);
$stmt->bindValue(3, $offset, PDO::PARAM_INT);
$stmt->execute();
$results = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Payment History - <?php echo htmlspecialchars($username); ?></title>

    <!-- Bootstrap & Icons -->
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.10.5/font/bootstrap-icons.min.css">

    <style>
        body {
            background: #f4f6f9;
            font-size: 0.95rem;
        }
        main {
            max-width: 1100px;
        }
        .page-header {
            border-bottom: 1px solid #e0e4ec;
            padding-bottom: 0.75rem;
            margin-bottom: 1.25rem;
        }
        .page-header h2 {
            font-size: 1.5rem;
            margin: 0;
        }
        .page-header small {
            color: #6c757d;
        }
        .toolbar {
            gap: .5rem;
        }
        #tableSearch {
            max-width: 260px;
        }

        /* Enhanced receipt */
        .receipt-content {
            display: none;
            width: 340px;
            background: #ffffff;
            border-radius: 12px;
            border: 1px solid #e3e6ef;
            padding: 18px 20px 14px;
            font-size: 0.9rem;
            color: #212529;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
        }
        .receipt-header {
            text-align: center;
            margin-bottom: 8px;
        }
        .receipt-logo {
            max-width: 80px;
            max-height: 80px;
            margin-bottom: 4px;
        }
        .receipt-business-name {
            font-weight: 700;
            font-size: 1.05rem;
            margin-bottom: 2px;
        }
        .receipt-business-details {
            font-size: 0.75rem;
            color: #6c757d;
            line-height: 1.1;
        }
        .receipt-title {
            font-weight: 600;
            font-size: 0.95rem;
            text-align: center;
            color: #0d6efd;
            margin: 6px 0 10px;
        }
        .receipt-section-title {
            font-weight: 600;
            font-size: 0.8rem;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin: 6px 0 2px;
        }
        .receipt-item {
            margin-bottom: 3px;
        }
        .receipt-item strong {
            display: inline-block;
            min-width: 110px;
        }
        .receipt-hr {
            border: 0;
            border-top: 1px dashed #d0d4e0;
            margin: 8px 0;
        }
        .receipt-total {
            font-weight: 700;
        }
        .receipt-footer {
            margin-top: 8px;
            font-size: 0.75rem;
            text-align: center;
            color: #6c757d;
        }

        /* Table */
        .payments-table th,
        .payments-table td {
            vertical-align: middle;
            white-space: nowrap;
        }
        .payments-table td:nth-child(2) {
            white-space: normal;
        }
        th.sortable {
            cursor: pointer;
        }
        th.sortable span.sort-indicator {
            font-size: 0.7rem;
            margin-left: 4px;
            visibility: hidden;
        }
        th.sortable.active span.sort-indicator {
            visibility: visible;
        }

        /* Mobile cards */
        .payment-card {
            border: 1px solid #e1e4ec;
            border-radius: .5rem;
        }
        .payment-card .card-title {
            font-size: 1rem;
        }
        .payment-card small {
            font-size: 0.75rem;
        }
    </style>
</head>
<body>
<main class="container py-4">
    <!-- HEADER -->
    <div class="d-flex flex-wrap justify-content-between align-items-center page-header">
        <div>
            <h2 class="mb-1">
                Payments for
                <span class="text-primary"><?php echo htmlspecialchars($username); ?></span>
            </h2>
            <small>Total records: <?php echo $total_logs; ?></small>
        </div>
        <div class="d-flex align-items-center toolbar mt-2 mt-sm-0">
            <a href="subscription_plans.php" class="btn btn-outline-secondary btn-sm">
                <i class="bi bi-arrow-left"></i>
            </a>
            <button type="button" class="btn btn-outline-secondary btn-sm"
                    onclick="window.location.reload()">
                <i class="bi bi-arrow-clockwise"></i>
            </button>
            <input type="text"
                   id="tableSearch"
                   class="form-control form-control-sm"
                   placeholder="Search payments">
        </div>
    </div>

    <?php if (isset($_GET['success']) && $_GET['success'] == 1): ?>
        <div class="alert alert-success alert-sm py-2">
            Payment successful. Renewal has been processed.
        </div>
    <?php endif; ?>

    <?php if ($results && count($results) > 0): ?>

        <!-- DESKTOP TABLE -->
        <div class="table-responsive d-none d-md-block">
            <table class="table table-hover table-sm align-middle payments-table bg-white border rounded">
                <thead class="table-light">
                <tr>
                    <th class="sortable" data-column="0">
                        Created
                        <span class="sort-indicator">▲</span>
                    </th>
                    <th class="sortable" data-column="1">
                        Plan
                        <span class="sort-indicator">▲</span>
                    </th>
                    <th class="sortable" data-column="2">
                        Amount
                        <span class="sort-indicator">▲</span>
                    </th>
                    <th class="sortable" data-column="3">
                        Days
                        <span class="sort-indicator">▲</span>
                    </th>
                    <th class="sortable" data-column="4">
                        Expires
                        <span class="sort-indicator">▲</span>
                    </th>
                    <th class="sortable" data-column="5">
                        Paid At
                        <span class="sort-indicator">▲</span>
                    </th>
                    <th class="sortable" data-column="6">
                        Adjusted By
                        <span class="sort-indicator">▲</span>
                    </th>
                    <th class="text-center">Receipt</th>
                </tr>
                </thead>
                <tbody>
                <?php $i = 0; foreach ($results as $row): $i++; ?>
                    <tr>
                        <td><?php echo htmlspecialchars($row['created_at'] ?? ''); ?></td>
                        <td><?php echo htmlspecialchars($row['plan_name'] ?? ''); ?></td>
                        <td>₱<?php echo number_format($row['amount'] ?? 0, 2); ?></td>
                        <td><?php echo htmlspecialchars($row['days'] ?? ''); ?></td>
                        <td><?php echo htmlspecialchars($row['expires_at'] ?? ''); ?></td>
                        <td><?php echo htmlspecialchars($row['paid_at'] ?? ''); ?></td>
                        <td><?php echo htmlspecialchars($row['adjusted_by'] ?? ''); ?></td>
                        <td class="text-center">
                            <button type="button"
                                    class="btn btn-outline-primary btn-sm me-1"
                                    title="Print"
                                    onclick="printReceiptImage('receipt-<?php echo $i; ?>','<?php echo $row['paid_at']; ?>')">
                                <i class="bi bi-printer"></i>
                            </button>
                            <button type="button"
                                    class="btn btn-outline-secondary btn-sm"
                                    title="Download image"
                                    onclick="downloadJPEG('receipt-<?php echo $i; ?>','<?php echo $row['paid_at']; ?>')">
                                <i class="bi bi-card-image"></i>
                            </button>

                            <!-- Hidden receipt -->
                            <div id="receipt-<?php echo $i; ?>" class="receipt-content">
                                <div class="receipt-header">
                                    <!-- CHANGE logo.png TO YOUR ACTUAL LOGO PATH -->
                                    <img src="assets/images/logo_black.png" alt="Logo" class="receipt-logo">
                                    <div class="receipt-business-name"></div>
                                    <div class="receipt-business-details">
                                        043 St. therese, camp evangelista Patag<br>
                                        Cagayan de Oro City, Misamis Oriental 9000, Philippines<br>
                                        Phone: 0936-274-2712 | 0927-303-4845
                                                                            <br>
                                      www.facebook.com/gametechunlifiberph.com
                                       <br>
                                      www.gametechunlifiberph.com
                                    </div>
                                </div>

                                <div class="receipt-title">Payment Receipt</div>
                                <div class="receipt-item">
                                    <strong>Receipt No.:</strong> 
                                    <?php echo 'R-' . str_pad((int)($row['id'] ?? 0), 6, '0', STR_PAD_LEFT); ?>
                                </div>
                                <div class="receipt-item">
                                    <strong>Username:</strong> <?php echo htmlspecialchars($username); ?>
                                </div>
                                <div class="receipt-item">
                                    <strong>Plan:</strong><?php echo htmlspecialchars($row['plan_name'] ?? ''); ?>
                                </div>
                                <hr class="receipt-hr">
                                <div class="receipt-item receipt-total">
                                    <strong>Amount Paid:</strong>
                                    ₱<?php echo number_format($row['amount'] ?? 0, 2); ?>
                                </div>
                                <div class="receipt-item">
                                    <strong>Days:</strong> <?php echo htmlspecialchars($row['days'] ?? ''); ?>
                                </div>
                                <div class="receipt-item">
                                    <strong>Period:</strong><br>
                                    <?php echo htmlspecialchars($row['created_at'] ?? ''); ?>
                                    &nbsp;to&nbsp;
                                    <?php echo htmlspecialchars($row['expires_at'] ?? ''); ?>
                                </div>
                                <div class="receipt-item">
                                    <strong>Paid At:</strong> <?php echo htmlspecialchars($row['paid_at'] ?? ''); ?>
                                </div>
                                <div class="receipt-item">
                                    <strong>Processed By:</strong> <?php echo htmlspecialchars($row['adjusted_by'] ?? ''); ?>
                                </div>
                                <hr class="receipt-hr">
                                <div class="receipt-footer">
                                    Thank you for your payment.<br>
                                    This is a system-generated receipt.

                                </div>
                            </div>
                        </td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>

        <!-- MOBILE CARDS -->
        <div class="d-block d-md-none">
            <?php $cardIndex = 0; foreach ($results as $row): $cardIndex++; ?>
                <div class="card payment-card mb-3 bg-white">
                    <div class="card-body">
                        <div class="d-flex justify-content-between mb-1">
                            <h6 class="card-title mb-0">
                                <?php echo htmlspecialchars($row['plan_name'] ?? ''); ?>
                            </h6>
                            <small class="text-muted">
                                <?php echo htmlspecialchars($row['paid_at'] ?? ''); ?>
                            </small>
                        </div>
                        <ul class="list-unstyled mb-2">
                            <li><strong>Amount:</strong> ₱<?php echo number_format($row['amount'] ?? 0, 2); ?></li>
                            <li><strong>Days:</strong> <?php echo htmlspecialchars($row['days'] ?? ''); ?></li>
                            <li><strong>Expires:</strong> <?php echo htmlspecialchars($row['expires_at'] ?? ''); ?></li>
                            <li><strong>By:</strong> <?php echo htmlspecialchars($row['adjusted_by'] ?? ''); ?></li>
                        </ul>
                        <div class="d-flex gap-2">
                            <button type="button"
                                    class="btn btn-outline-primary btn-sm"
                                    onclick="printReceiptImage('receipt-card-<?php echo $cardIndex; ?>','<?php echo $row['paid_at']; ?>')">
                                <i class="bi bi-printer"></i> Print
                            </button>
                            <button type="button"
                                    class="btn btn-outline-secondary btn-sm"
                                    onclick="downloadJPEG('receipt-card-<?php echo $cardIndex; ?>','<?php echo $row['paid_at']; ?>')">
                                <i class="bi bi-card-image"></i> Image
                            </button>
                        </div>

                        <!-- Mobile receipt -->
                        <div id="receipt-card-<?php echo $cardIndex; ?>" class="receipt-content mt-2">
                            <div class="receipt-header">
                                <img src="assets/images/logo_black.png" alt="Logo" class="receipt-logo">
                                <div class="receipt-business-name"></div>
                                <div class="receipt-business-details">
                                        043 St. therese, camp evangelista Patag<br>
                                        Cagayan de Oro City, Misamis Oriental 9000, Philippines<br>
                                        Phone: 0936-274-2712 | 0927-303-4845
                                                                            <br>
                                      www.facebook.com/gametechunlifiberph.com
                                       <br>
                                      www.gametechunlifiberph.com
                                </div>
                            </div>

                            <div class="receipt-title">Payment Receipt</div>
                            <div class="receipt-item">
                                <strong>Receipt No.:</strong>
                                <?php echo 'R-' . str_pad((int)($row['id'] ?? 0), 6, '0', STR_PAD_LEFT); ?>
                            </div>
                            <div class="receipt-item">
                                <strong>Username:</strong> <?php echo htmlspecialchars($username); ?>
                            </div>
                            <div class="receipt-item">
                                <strong>Plan:</strong> <?php echo htmlspecialchars($row['plan_name'] ?? ''); ?>
                            </div>
                            <hr class="receipt-hr">
                            <div class="receipt-item receipt-total">
                                <strong>Amount Paid:</strong>
                                ₱<?php echo number_format($row['amount'] ?? 0, 2); ?>
                            </div>
                            <div class="receipt-item">
                                <strong>Days:</strong> <?php echo htmlspecialchars($row['days'] ?? ''); ?>
                            </div>
                            <div class="receipt-item">
                                <strong>Period:</strong>
                                <?php echo htmlspecialchars($row['created_at'] ?? ''); ?>
                                &nbsp;to&nbsp;
                                <?php echo htmlspecialchars($row['expires_at'] ?? ''); ?>
                            </div>
                            <div class="receipt-item">
                                <strong>Paid At:</strong> <?php echo htmlspecialchars($row['paid_at'] ?? ''); ?>
                            </div>
                            <div class="receipt-item">
                                <strong>Processed By:</strong> <?php echo htmlspecialchars($row['adjusted_by'] ?? ''); ?>
                            </div>
                            <hr class="receipt-hr">
                            <div class="receipt-footer">
                                Thank you for your payment.<br>
                                This is a system-generated receipt.
                            </div>
                        </div>
                    </div>
                </div>
            <?php endforeach; ?>
        </div>

        <!-- PAGINATION -->
        <?php if ($total_pages > 1): ?>
            <nav aria-label="Payments pages" class="mt-3">
                <ul class="pagination pagination-sm justify-content-center mb-0">
                    <li class="page-item <?php if ($page <= 1) echo 'disabled'; ?>">
                        <a class="page-link"
                           href="?username=<?php echo urlencode($username); ?>&page=1">
                            « First
                        </a>
                    </li>
                    <li class="page-item <?php if ($page <= 1) echo 'disabled'; ?>">
                        <a class="page-link"
                           href="?username=<?php echo urlencode($username); ?>&page=<?php echo max(1, $page - 1); ?>">
                            ‹ Prev
                        </a>
                    </li>

                    <?php
                    $start = max(1, $page - 2);
                    $end   = min($total_pages, $page + 2);
                    for ($p = $start; $p <= $end; $p++): ?>
                        <li class="page-item <?php if ($p == $page) echo 'active'; ?>">
                            <a class="page-link"
                               href="?username=<?php echo urlencode($username); ?>&page=<?php echo $p; ?>">
                                <?php echo $p; ?>
                            </a>
                        </li>
                    <?php endfor; ?>

                    <li class="page-item <?php if ($page >= $total_pages) echo 'disabled'; ?>">
                        <a class="page-link"
                           href="?username=<?php echo urlencode($username); ?>&page=<?php echo min($total_pages, $page + 1); ?>">
                            Next ›
                        </a>
                    </li>
                    <li class="page-item <?php if ($page >= $total_pages) echo 'disabled'; ?>">
                        <a class="page-link"
                           href="?username=<?php echo urlencode($username); ?>&page=<?php echo $total_pages; ?>">
                            Last »
                        </a>
                    </li>
                </ul>
            </nav>
        <?php endif; ?>

    <?php else: ?>
        <div class="alert alert-info">
            No payment records found for this user.
        </div>
    <?php endif; ?>
</main>

<!-- JS -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function () {
    const searchInput    = document.getElementById('tableSearch');
    const table          = document.querySelector('.payments-table');
    const tableBody      = table ? table.querySelector('tbody') : null;
    const headers        = table ? table.querySelectorAll('th.sortable') : [];
    const cardsContainer = document.querySelector('.d-block.d-md-none');

    // SEARCH (table + mobile cards)
    function filterResults() {
        const term = (searchInput.value || '').toLowerCase();

        if (tableBody) {
            tableBody.querySelectorAll('tr').forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(term) ? '' : 'none';
            });
        }

        if (cardsContainer) {
            cardsContainer.querySelectorAll('.card').forEach(card => {
                const text = card.innerText.toLowerCase();
                card.style.display = text.includes(term) ? '' : 'none';
            });
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', filterResults);
    }

    // SORT (desktop table only)
    let sortState = {}; // columnIndex -> 'asc' | 'desc'

    function sortTableByColumn(colIndex) {
        if (!tableBody) return;

        const rows = Array.from(tableBody.querySelectorAll('tr'));
        const currentOrder = sortState[colIndex] === 'asc' ? 'desc' : 'asc';
        sortState[colIndex] = currentOrder;

        // Visual state on header
        headers.forEach(h => h.classList.remove('active'));
        const activeHeader = Array.from(headers).find(h => parseInt(h.dataset.column) === colIndex);
        if (activeHeader) {
            activeHeader.classList.add('active');
            const indicator = activeHeader.querySelector('.sort-indicator');
            if (indicator) indicator.textContent = currentOrder === 'asc' ? '▲' : '▼';
        }

        rows.sort((a, b) => {
            const aText = (a.children[colIndex].innerText || '').trim();
            const bText = (b.children[colIndex].innerText || '').trim();

            const aNum = parseFloat(aText.replace(/[^0-9.\-]/g, ''));
            const bNum = parseFloat(bText.replace(/[^0-9.\-]/g, ''));
            const bothNumeric = !isNaN(aNum) && !isNaN(bNum);

            let cmp;
            if (bothNumeric) {
                cmp = aNum - bNum;
            } else {
                cmp = aText.localeCompare(bText);
            }

            return currentOrder === 'asc' ? cmp : -cmp;
        });

        rows.forEach(r => tableBody.appendChild(r));
    }

    headers.forEach(header => {
        header.addEventListener('click', function () {
            const colIndex = parseInt(this.dataset.column, 10);
            sortTableByColumn(colIndex);
        });
    });
});

// RECEIPT IMAGE / PRINT
function printReceiptImage(receiptId, paidAt) {
    const receipt = document.getElementById(receiptId);
    if (!receipt) return;

    receipt.style.display = 'block';

    html2canvas(receipt, {
        scale: 2, // better quality
        useCORS: true
    }).then(canvas => {
        const imgData = canvas.toDataURL('image/jpeg', 1.0);
        const w = window.open('', '_blank');

        w.document.write(
            '<html><head><title>Receipt</title></head>' +
            '<body style="margin:0;background:#f4f4f4;text-align:center;">' +
            '<img src="' + imgData + '" style="max-width:100%;margin:20px auto;display:block;" ' +
            'onload="window.print();window.close();">' +
            '</body></html>'
        );
        w.document.close();
        receipt.style.display = 'none';
    });
}

function downloadJPEG(receiptId, paidAt) {
    const receipt = document.getElementById(receiptId);
    if (!receipt) return;

    receipt.style.display = 'block';

    html2canvas(receipt, {
        scale: 2,
        useCORS: true
    }).then(canvas => {
        const link = document.createElement('a');
        const safeDate = (paidAt || '').replace(/[^0-9]/g, '') || Date.now();
        link.download = 'receipt_' + safeDate + '.jpeg';
        link.href = canvas.toDataURL('image/jpeg', 1.0);
        link.click();
        receipt.style.display = 'none';
    });
}
</script>
</body>
</html>
<?php include 'footer.php'; ?>
