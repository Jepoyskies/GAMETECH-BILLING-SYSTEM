<?php include 'header.php'; ?>
<?php require 'database.php'; ?>

<?php
$message = '';
$error = '';

// Handle delete action
if (isset($_GET['delete'])) {
    $id = (int)$_GET['delete'];
    try {
        $stmt = $conn->prepare("DELETE FROM napbox_mapping WHERE id = :id");
        $stmt->execute([':id' => $id]);
        $message = 'NAP Box deleted successfully.';
    } catch (PDOException $e) {
        $error = 'Error deleting NAP Box: ' . $e->getMessage();
    }
}

// Fetch all entries
try {
    $stmt = $conn->query("SELECT * FROM napbox_mapping");
    $napboxes = $stmt->fetchAll();
} catch (PDOException $e) {
    $error = 'Error fetching data: ' . $e->getMessage();
}
?>

<main class="container py-4">
    <div class="row">
        <div class="col-12">
            <?php if ($message): ?>
                <div class="alert alert-success">
                    <?php echo htmlspecialchars($message); ?>
                </div>
            <?php endif; ?>

            <?php if ($error): ?>
                <div class="alert alert-danger">
                    <?php echo htmlspecialchars($error); ?>
                </div>
            <?php endif; ?>

            <h5 class="mb-3">NAP Box Mapping</h5>

            <!-- Table for PC view -->
            <div class="d-none d-lg-block">
                <table id="napboxesTable" class="table table-striped table-bordered">
                    <thead class="table-dark">
                        <tr>
                            <th>NAP Box No</th>
                            <th>Marker Color</th>
                            <th>Latitude</th>
                            <th>Longitude</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($napboxes as $napbox): ?>
                            <tr>
                                <td><?php echo htmlspecialchars($napbox['napbox_no']); ?></td>
                                <td><?php echo htmlspecialchars($napbox['marker_color']); ?></td>
                                <td><?php echo htmlspecialchars($napbox['nap_latitude']); ?></td>
                                <td><?php echo htmlspecialchars($napbox['nap_longitude']); ?></td>
                                <td>
                                    <a href="edit_nap.php?id=<?php echo $napbox['id']; ?>" class="btn btn-sm btn-outline-primary">Edit</a>
                                    <a href="?delete=<?php echo $napbox['id']; ?>" class="btn btn-sm btn-outline-danger" onclick="return confirm('Are you sure you want to delete this NAP Box?');">Delete</a>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>

            <!-- Cards for mobile view -->
            <div class="d-lg-none">
                <div class="row">
                    <?php foreach ($napboxes as $napbox): ?>
                        <div class="col-12 mb-4">
                            <div class="card shadow-sm">
                                <div class="card-body">
                                    <h6 class="card-title">NAP Box No: <?php echo htmlspecialchars($napbox['napbox_no']); ?></h6>
                                    <p class="card-text">
                                        <strong>Color:</strong> <?php echo htmlspecialchars($napbox['marker_color']); ?><br>
                                        <strong>Latitude:</strong> <?php echo htmlspecialchars($napbox['nap_latitude']); ?><br>
                                        <strong>Longitude:</strong> <?php echo htmlspecialchars($napbox['nap_longitude']); ?>
                                    </p>
                                    <a href="edit_nap.php?id=<?php echo $napbox['id']; ?>" class="btn btn-sm btn-outline-primary">Edit</a>
                                    <a href="?delete=<?php echo $napbox['id']; ?>" class="btn btn-sm btn-outline-danger" onclick="return confirm('Are you sure you want to delete this NAP Box?');">Delete</a>
                                </div>
                            </div>
                        </div>
                    <?php endforeach; ?>
                </div>
            </div>
        </div>
    </div>
</main>

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.11.5/js/dataTables.bootstrap5.min.js"></script>
<link rel="stylesheet" href="https://cdn.datatables.net/1.11.5/css/dataTables.bootstrap5.min.css">
<script>
$(document).ready(function() {
    $('#napboxesTable').DataTable({
        "paging": true,
        "searching": true,
        "ordering": true,
        "info": true,
        "lengthMenu": [5, 10, 25, 50], // Options for number of entries to show
        "pageLength": 10, // Default number of entries
        "language": {
            "search": "Filter records:",
            "lengthMenu": "Display _MENU_ records per page",
            "info": "Showing page _PAGE_ of _PAGES_",
            "infoEmpty": "No records available",
            "infoFiltered": "(filtered from _MAX_ total records)"
        }
    });
});
</script>

<?php include 'footer.php'; ?>
