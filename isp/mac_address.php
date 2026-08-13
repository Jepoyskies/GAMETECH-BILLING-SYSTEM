<?php
include 'header.php';
require_once 'database.php';

// Your PHP logic (unchanged)
$records_per_page = 5000; // Show all by default, DataTables will paginate
$search = isset($_GET['search']) ? trim($_GET['search']) : '';
$page = 1; // Not needed with DataTables, but left for compatibility

// Search and params
$where = '';
$params = [];
if ($search !== '') {
    $where = "WHERE 
        cmh.customer_id LIKE :search1 OR 
        cmh.mac_address LIKE :search2 OR 
        cmh.detected_at LIKE :search3 OR
        c.full_name LIKE :search4";
    $params[':search1'] = '%' . $search . '%';
    $params[':search2'] = '%' . $search . '%';
    $params[':search3'] = '%' . $search . '%';
    $params[':search4'] = '%' . $search . '%';
}

// Fetch all data (DataTables will paginate client-side)
$data_sql = "SELECT 
                cmh.id, 
                cmh.customer_id, 
                cmh.mac_address, 
                cmh.detected_at, 
                c.full_name
            FROM customer_mac_history cmh
            LEFT JOIN customers c ON cmh.customer_id = c.id
            $where
            ORDER BY cmh.detected_at DESC
            LIMIT :limit";
$stmt = $pdo->prepare($data_sql);
foreach ($params as $key => $value) {
    $stmt->bindValue($key, $value, PDO::PARAM_STR);
}
$stmt->bindValue(':limit', $records_per_page, PDO::PARAM_INT);
$stmt->execute();
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>

<meta name="viewport" content="width=device-width, initial-scale=1">

<!-- DataTables CSS & JS -->
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.8/css/dataTables.bootstrap5.min.css">
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.8/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.8/js/dataTables.bootstrap5.min.js"></script>

<style>
/* Mobile responsive, small table */
@media (max-width: 576px) {
    table.table thead { display: none; }
    table.table tbody tr { display: block; margin-bottom: 1rem; border: 1px solid #e0e0e0; border-radius: .5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.03); padding: .5rem .75rem; }
    table.table tbody td { display: flex; justify-content: space-between; align-items: center; padding: .35rem 0; border: none; font-size: 1em; }
    table.table tbody td::before { content: attr(data-label); font-weight: 600; flex-basis: 50%; color: #555; margin-right: .5rem; text-align: left; }
}
.dataTables_length, .dataTables_info { font-size: .95em; }
.dataTables_filter { margin-bottom: 1rem; }
.table-sm th, .table-sm td { padding: .3rem .4rem; }
</style>

<main class="container py-4">

 

    <!-- MAC Address History Table -->
    <div class="row">
        <div class="col-12">
            <div class="card shadow-sm border-0 mb-4">
                <div class="card-body p-2 p-md-3">
                    <h5 class="card-title mb-3">Customer MAC History</h5>
                    <div class="table-responsive">
                        <table id="mac-history" class="table table-striped table-bordered table-sm align-middle mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>ID</th>
                                    <th>Customer ID</th>
                                    <th>Customer Name</th>
                                    <th>MAC Address</th>
                                    <th>Detected At</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php if ($rows): ?>
                                    <?php foreach ($rows as $row): ?>
                                        <tr>
                                            <td data-label="ID"><?= htmlspecialchars($row['id']) ?></td>
                                            <td data-label="Customer ID"><?= htmlspecialchars($row['customer_id']) ?></td>
                                            <td data-label="Customer Name"><?= htmlspecialchars($row['full_name'] ?? 'N/A') ?></td>
                                            <td data-label="MAC Address"><?= htmlspecialchars($row['mac_address']) ?></td>
                                            <td data-label="Detected At"><?= htmlspecialchars($row['detected_at']) ?></td>
                                        </tr>
                                    <?php endforeach; ?>
                                <?php else: ?>
                                    <tr>
                                        <td colspan="5" class="text-center text-muted">No MAC history found.</td>
                                    </tr>
                                <?php endif; ?>
                            </tbody>
                        </table>
                    </div>
                    <!-- DataTables handles pagination, length menu, etc. -->
                </div>
            </div>
        </div>
    </div>
</main>

<script>
$(document).ready(function() {
    $('#mac-history').DataTable({
        // DataTables options
        "lengthMenu": [ [10, 25, 50, 100, -1], [10, 25, 50, 100, "All"] ],
        "pageLength": 10,
        "order": [[ 4, "desc" ]], // Default sort by Detected At DESC
        "columnDefs": [
            { "orderable": false, "targets": [] } // Make columns unsortable if needed
        ],
        "responsive": false // You have your own mobile CSS
    });
});
</script>

<?php include 'footer.php'; ?>
