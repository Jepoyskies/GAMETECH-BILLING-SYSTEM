<?php
// plans.php

// --- Database connection (adjust as needed) ---
require 'database.php'; // Make sure $pdo is a valid PDO object
include 'header.php';

// --- Fetch all plans (no pagination/limit needed) ---
$sql = "SELECT id, plan_name, speed_up, speed_down, price, validity_days, description FROM service_plans";
$stmt = $pdo->query($sql);
$plans = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Service Plans</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- FontAwesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.1/css/all.min.css">
    <!-- DataTables Bootstrap 5 CSS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css">
    <style>
        #plansTable th, #plansTable td { padding: 0.45rem 0.6rem !important; font-size: 0.97rem; }
        .dataTables_length, .dataTables_filter { margin-bottom: 1rem; }
        .toast { z-index: 1060; min-width:200px;}
        @media (max-width: 767.98px) {
            #plansTable { font-size: 0.94rem; }
        }
    </style>
</head>
<body>
<main class="container py-4">

    <div class="d-flex align-items-center mb-4">
        <h2 class="mb-0 fw-bold text-primary">
            <i class="fa-solid fa-network-wired"></i> Service Plans
        </h2>
    </div>

    <div class="mb-3">
        <a href="add_serviceplans.php" class="btn btn-outline-secondary me-2" title="Add Plan">
            <i class="fa-solid fa-user-plus"></i> Add Plan
        </a>
    </div>

    <div class="table-responsive">
        <table id="plansTable" class="table table-sm table-hover table-bordered align-middle" style="width:100%">
            <thead class="table-primary">
                <tr>
                    <th>ID</th>
                    <th>Plan Name</th>
                    <th>Up (Mbps)</th>
                    <th>Down (Mbps)</th>
                    <th>Price (₱)</th>
                    <th>Validity (days)</th>
                    <th>Description</th>
                    <th style="min-width:110px;">Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($plans as $row): ?>
                <tr>
                    <td><?= htmlspecialchars($row['id']) ?></td>
                    <td><b><?= htmlspecialchars($row['plan_name']) ?></b></td>
                    <td><?= htmlspecialchars($row['speed_up']) ?></td>
                    <td><?= htmlspecialchars($row['speed_down']) ?></td>
                    <td>₱<?= number_format($row['price'], 2) ?></td>
                    <td><?= htmlspecialchars($row['validity_days']) ?></td>
                    <td style="max-width:180px; white-space:pre-line;"><?= htmlspecialchars($row['description']) ?></td>
                    <td>
                        <a href="edit_serviceplans.php?id=<?= $row['id'] ?>" class="btn btn-sm btn-outline-info mb-1" title="Edit">
                            <i class="fas fa-edit"></i>
                        </a>
                        <button class="btn btn-sm btn-outline-danger mb-1"
                            onclick="deletePlan(<?= $row['id'] ?>, this)">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>

    <!-- Toast Notification -->
    <div id="notifToast" class="toast align-items-center text-bg-primary border-0 position-fixed bottom-0 end-0 m-4" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
            <div class="toast-body" id="notifToastMsg"></div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    </div>

</main>

<!-- JS dependencies -->
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>

<script>
$(document).ready(function() {
    $('#plansTable').DataTable({
        "lengthMenu": [5, 10, 25, 50, 100],
        "pageLength": 10,
        "order": [[0, "asc"]],
        "columnDefs": [
            { "orderable": false, "targets": 7 } // Actions column not sortable
        ]
    });
});

// Toast and deletePlan function
function showNotification(message, type = 'success') {
    const toast = document.getElementById('notifToast');
    const toastMsg = document.getElementById('notifToastMsg');
    toast.className = 'toast align-items-center text-bg-' + (type === 'success' ? 'success' : 'danger') + ' border-0 position-fixed bottom-0 end-0 m-4';
    toastMsg.textContent = message;
    var bsToast = new bootstrap.Toast(toast, {delay: 2500});
    bsToast.show();
}

function deletePlan(id, btn) {
    if (!confirm("Are you sure you want to delete this plan?")) return;
    btn.disabled = true;
    fetch('delete_service.php?id=' + id)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Remove row from DataTable
                var table = $('#plansTable').DataTable();
                var $row = $(btn).closest('tr');
                table.row($row).remove().draw();

                showNotification('Plan deleted successfully!', 'success');
            } else {
                showNotification(data.message || 'Delete failed!', 'danger');
                btn.disabled = false;
            }
        })
        .catch(() => {
            showNotification('Network error. Try again.', 'danger');
            btn.disabled = false;
        });
}
</script>
</body>
</html>
