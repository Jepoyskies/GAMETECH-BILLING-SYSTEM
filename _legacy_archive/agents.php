<?php
include 'header.php';
include 'database.php';

// Handle deletion
$deleteMessage = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete_agent_id'])) {
    $agentIdToDelete = $_POST['delete_agent_id'];

    $delSql = "DELETE FROM agents WHERE id = :id";
    $delStmt = $conn->prepare($delSql);
    $delStmt->bindParam(':id', $agentIdToDelete, PDO::PARAM_INT);

    if ($delStmt->execute()) {
        $deleteMessage = "Agent deleted successfully.";
    } else {
        $deleteMessage = "Failed to delete agent.";
    }
}

// Fetch all agents for display
$sql = "SELECT id, name, email, phone FROM agents ORDER BY name ASC";
$stmt = $conn->prepare($sql);
$stmt->execute();
$agents = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>

<main class="container py-4">

    <div class="d-flex justify-content-between align-items-center mb-3">
        <h2 class="mb-0 fw-bold text-primary"><i class="fa fa-address-card"></i> Agents</h2>
        <a href="add_agent.php" class="btn btn-success">
            <i class="fa fa-plus-circle"></i> Add Agent
        </a>
    </div>

    <!-- Cards view (mobile-first) -->
    <div class="row g-3 d-md-none" id="agents-cards">
        <?php
        if ($agents) {
            foreach ($agents as $agent) {
                echo '
                <div class="col-12">
                    <div class="card h-100 shadow-sm">
                        <div class="card-body d-flex flex-column">
                            <h5 class="card-title mb-2">' . htmlspecialchars($agent['name'], ENT_QUOTES, 'UTF-8') . '</h5>
                            <p class="card-text mb-1"><strong>Email:</strong> ' . htmlspecialchars($agent['email'], ENT_QUOTES, 'UTF-8') . '</p>
                            <p class="card-text mb-3"><strong>Phone:</strong> ' . htmlspecialchars($agent['phone'], ENT_QUOTES, 'UTF-8') . '</p>

                            <div class="mt-auto">
                                <a href="view_agent.php?id=' . urlencode($agent['id']) . '" class="btn btn-sm btn-info me-2">View</a>
                                <a href="edit_agent.php?id=' . urlencode($agent['id']) . '" class="btn btn-sm btn-primary me-2">Edit</a>
                                <form method="post" onsubmit="return confirm(\'Are you sure you want to delete this agent?\');" class="d-inline-block">
                                    <input type="hidden" name="delete_agent_id" value="' . htmlspecialchars($agent['id'], ENT_QUOTES, 'UTF-8') . '">
                                    <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>';
            }
        } else {
            echo '<div class="col-12"><div class="alert alert-info">No agents found</div></div>';
        }
        ?>
    </div>

    <!-- Table view (desktop) -->
    <div class="table-responsive d-none d-md-block" id="agents-table">
        <table id="agentsDataTable" class="table table-striped table-bordered table-sm small">
            <thead class="thead-dark">
                <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th style="width: 230px;">Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php
                if ($agents) {
                    foreach ($agents as $agent) {
                        echo "<tr>
                                <td>" . htmlspecialchars($agent['name'], ENT_QUOTES, 'UTF-8') . "</td>
                                <td>" . htmlspecialchars($agent['email'], ENT_QUOTES, 'UTF-8') . "</td>
                                <td>" . htmlspecialchars($agent['phone'], ENT_QUOTES, 'UTF-8') . "</td>
                                <td>
                                    <a href=\"view_agent.php?id=" . urlencode($agent['id']) . "\" class=\"btn btn-sm btn-info me-1\">View</a>
                                    <a href=\"edit_agent.php?id=" . urlencode($agent['id']) . "\" class=\"btn btn-sm btn-primary me-1\">Edit</a>
                                    <form method=\"post\" onsubmit=\"return confirm('Are you sure you want to delete this agent?');\" style=\"display:inline-block;\">
                                        <input type=\"hidden\" name=\"delete_agent_id\" value=\"" . htmlspecialchars($agent['id'], ENT_QUOTES, 'UTF-8') . "\">
                                        <button type=\"submit\" class=\"btn btn-sm btn-danger\">Delete</button>
                                    </form>
                                </td>
                              </tr>";
                    }
                } else {
                    echo "<tr><td colspan='4'>No agents found</td></tr>";
                }
                ?>
            </tbody>
        </table>
    </div>

    <!-- Notification area -->
    <?php if (!empty($deleteMessage)): ?>
        <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1055;">
            <div id="deleteToast" class="toast show align-items-center text-bg-success border-0" role="alert" aria-live="polite" aria-atomic="true" data-bs-delay="5000" style="min-width: 320px;">
                <div class="d-flex">
                    <div class="toast-body">
                        <?php echo htmlspecialchars($deleteMessage, ENT_QUOTES, 'UTF-8'); ?>
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        </div>
    <?php endif; ?>

</main>

<link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>

<script>
    $(document).ready(function() {
        $('#agentsDataTable').DataTable({
            "paging": true,
            "searching": true,
            "ordering": true,
            "info": true
        });
    });
</script>

<?php include 'footer.php'; ?>
