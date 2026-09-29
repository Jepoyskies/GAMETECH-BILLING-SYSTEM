<?php
require_once 'database.php'; // $pdo
require_once 'MikrotikManager/MikrotikManager_devices.php';

header('X-Content-Type-Options: nosniff');

// 1. AJAX handler for connection test
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['device_name']) && !isset($_POST['action'])) {
    header('Content-Type: application/json');
    $deviceName = $_POST['device_name'];

    $stmt = $pdo->prepare("SELECT * FROM mikrotik_devices WHERE device_name = ?");
    $stmt->execute([$deviceName]);
    $device = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$device) {
        echo json_encode(['status' => 'error', 'error' => 'Device not found in database.']);
        exit;
    }

    $ip   = $device['ip_address'];
    $user = $device['api_username'];
    $pass = $device['api_password'];
    $port = $device['api_port'];

    try {
        $mt = new MikroTikManager($ip, $user, $pass, $port);
        $mt->connect();
        $mt->disconnect();
        echo json_encode(['status' => 'success']);
    } catch (Throwable $e) {
        echo json_encode([
            'status' => 'error',
            'error'  => $e->getMessage()
        ]);
    }
    exit;
}

// 2. Normal HTML page rendering
$sql = "SELECT * FROM mikrotik_devices ORDER BY device_name ASC";
$stmt = $pdo->prepare($sql);
$stmt->execute();
$devices = $stmt->fetchAll(PDO::FETCH_ASSOC);

include 'header.php';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MikroTik Devices</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- Bootstrap & FontAwesome -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
    <style>
        @media (max-width: 576px) {
            .action-btns {
                display: flex;
                flex-direction: column;
                gap: 0.25rem;
            }
            table, th, td { font-size: 0.95rem; }
        }
        /* Hide table on mobile, hide cards on desktop */
        @media (max-width: 767.98px) {
            #devices-table-wrapper { display:none; }
            #devices-cards-wrapper { display:block; }
        }
        @media (min-width: 768px) {
            #devices-table-wrapper { display:block; }
            #devices-cards-wrapper { display:none; }
        }
    </style>
</head>
<body>
<main class="container py-4">
    <div class="row">
        <div class="col-12 mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
              <h2 class="mb-0 fw-bold text-primary"><i class="fa fa-mobile"></i> Mikrotik Devices</h2>
                <button class="btn btn-success" data-bs-toggle="modal" data-bs-target="#addDeviceModal">
                    <i class="fas fa-plus"></i> Add Device
                </button>
            </div>

            <div class="card shadow-sm border-0">
                <div class="card-body p-0">

                    <!-- TABLE VIEW (desktop / tablet) -->
                    <div id="devices-table-wrapper">
                        <div class="table-responsive">
                            <table class="table table-bordered align-middle mb-0" id="devices-table">
                                <thead class="table-light">
                                <tr>
                                    <th style="width:40px;">#</th>
                                    <th>Device Name</th>
                                    <th>IP Address</th>
                                    <th class="d-none d-md-table-cell">API Username</th>
                                    <th class="d-none d-md-table-cell">API Port</th>
                                    <th class="d-none d-md-table-cell">API Port 8700</th>
                                    <th style="min-width:150px;">Actions</th>
                                    <th>Status</th>
                                </tr>
                                </thead>
                                <tbody>
                                <?php if (empty($devices)): ?>
                                    <tr>
                                        <td colspan="7" class="text-center text-muted">No MikroTik devices found.</td>
                                    </tr>
                                <?php else: ?>
                                    <?php foreach ($devices as $i => $device): ?>
                                        <?php
                                        $safeName = preg_replace('/[^a-zA-Z0-9_\-]/', '', $device['device_name']);
                                        ?>
                                        <tr id="device-row-<?= $safeName ?>">
                                            <td><?= $i + 1 ?></td>
                                            <td><?= htmlspecialchars($device['device_name']) ?></td>
                                            <td><?= htmlspecialchars($device['ip_address']) ?></td>
                                            <td class="d-none d-md-table-cell"><?= htmlspecialchars($device['api_username']) ?></td>
                                            <td class="d-none d-md-table-cell"><?= htmlspecialchars($device['api_port']) ?></td>
                                            <td class="d-none d-md-table-cell"><?= htmlspecialchars($device['api_port_8700']) ?></td>

                                            <td>
                                                <div class="action-btns d-flex flex-wrap gap-1">
                                                    <button class="btn btn-info btn-sm"
                                                            onclick="testConnection('<?= htmlspecialchars($device['device_name'], ENT_QUOTES) ?>')"
                                                            id="test-btn-<?= $safeName ?>"
                                                            title="Test Connection">
                                                        <i class="fas fa-plug"></i>
                                                    </button>
                                                    <button class="btn btn-primary btn-sm"
                                                            data-bs-toggle="modal"
                                                            data-bs-target="#editDeviceModal"
                                                            data-id="<?= $device['id'] ?>"
                                                            data-name="<?= htmlspecialchars($device['device_name']) ?>"
                                                            data-ip="<?= htmlspecialchars($device['ip_address']) ?>"
                                                            data-username="<?= htmlspecialchars($device['api_username']) ?>"
                                                            data-port="<?= htmlspecialchars($device['api_port']) ?>"
                                                            title="Edit Device">
                                                        <i class="fas fa-edit"></i>
                                                    </button>
                                                    <button class="btn btn-danger btn-sm"
                                                            data-bs-toggle="modal"
                                                            data-bs-target="#deleteDeviceModal"
                                                            data-id="<?= $device['id'] ?>"
                                                            data-name="<?= htmlspecialchars($device['device_name']) ?>"
                                                            title="Delete Device">
                                                        <i class="fas fa-trash"></i>
                                                    </button>
                                                </div>
                                            </td>
                                            <td id="status-<?= $safeName ?>">
                                                <span class="text-muted">Not tested</span>
                                            </td>
                                        </tr>
                                    <?php endforeach; ?>
                                <?php endif; ?>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- CARD VIEW (mobile) -->
                    <div id="devices-cards-wrapper" class="p-3">
                        <?php if (empty($devices)): ?>
                            <p class="text-center text-muted mb-0">No MikroTik devices found.</p>
                        <?php else: ?>
                            <div class="row g-3">
                                <?php foreach ($devices as $i => $device): ?>
                                    <?php
                                    $safeName = preg_replace('/[^a-zA-Z0-9_\-]/', '', $device['device_name']);
                                    ?>
                                    <div class="col-12" id="device-card-<?= $safeName ?>">
                                        <div class="card border">
                                            <div class="card-body">
                                                <div class="d-flex justify-content-between align-items-start mb-2">
                                                    <div>
                                                        <h6 class="card-title mb-1">
                                                            #<?= $i + 1 ?> - <?= htmlspecialchars($device['device_name']) ?>
                                                        </h6>
                                                        <small class="text-muted">IP: <?= htmlspecialchars($device['ip_address']) ?></small>
                                                    </div>
                                                    <span id="status-<?= $safeName ?>" class="ms-2 small text-muted">
                                                        Not tested
                                                    </span>
                                                </div>
                                                <div class="mb-2">
                                                    <small class="d-block">
                                                        <strong>API User:</strong> <?= htmlspecialchars($device['api_username']) ?>
                                                    </small>
                                                    <small class="d-block">
                                                        <strong>API Port:</strong> <?= htmlspecialchars($device['api_port']) ?>
                                                    </small>
                                                </div>



<small class="d-block">
    <strong>API Port 8700:</strong> <?= htmlspecialchars($device['api_port_8700']) ?>
</small>







                                                <div class="action-btns d-flex flex-wrap gap-1 mt-2">

                                                    <button class="btn btn-primary btn-sm"
                                                            data-bs-toggle="modal"
                                                            data-bs-target="#editDeviceModal"
                                                            data-id="<?= $device['id'] ?>"
                                                            data-name="<?= htmlspecialchars($device['device_name']) ?>"
                                                            data-ip="<?= htmlspecialchars($device['ip_address']) ?>"
                                                            data-username="<?= htmlspecialchars($device['api_username']) ?>"
                                                            data-port="<?= htmlspecialchars($device['api_port']) ?>"
                                                            data-port8700="<?= htmlspecialchars($device['api_port_8700']) ?>"

                                                            title="Edit Device">
                                                        <i class="fas fa-edit"></i> Edit
                                                    </button>








<div class="mb-3">
  <label for="add-api-port-8700" class="form-label">API Port 8700</label>
  <input
    type="number"
    class="form-control"
    id="add-api-port-8700"
    name="api_port_8700"
    value="<?php echo isset($_GET['api_port_8700']) ? (int)$_GET['api_port_8700'] : 8700; ?>"
  >
</div>







                                                    <button class="btn btn-danger btn-sm"
                                                            data-bs-toggle="modal"
                                                            data-bs-target="#deleteDeviceModal"
                                                            data-id="<?= $device['id'] ?>"
                                                            data-name="<?= htmlspecialchars($device['device_name']) ?>"
                                                            title="Delete Device">
                                                        <i class="fas fa-trash"></i> Delete
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                <?php endforeach; ?>
                            </div>
                        <?php endif; ?>
                    </div>

                    <div class="px-3 py-2">
                        <small class="text-muted">
                            Edit, delete or test each MikroTik device connection. Passwords are not shown for security.
                        </small>
                    </div>
                </div>
            </div>
        </div>
    </div>
</main>

<!-- Add Device Modal -->
<div class="modal fade" id="addDeviceModal" tabindex="-1" aria-labelledby="addDeviceModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <form class="modal-content" action="add_mikrotik_device.php" method="POST" autocomplete="off">
      <div class="modal-header">
        <h5 class="modal-title" id="addDeviceModalLabel">
          <i class="fas fa-plus"></i> Add MikroTik Device
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>

      <div class="modal-body">
        <?php if (!empty($_GET['error'])): ?>
          <div class="alert alert-danger py-2">
            <?php echo htmlspecialchars($_GET['error']); ?>
          </div>
        <?php endif; ?>

        <div class="mb-3">
          <label for="add-device-name" class="form-label">Device Name</label>
          <input
            type="text"
            class="form-control"
            id="add-device-name"
            name="device_name"
            required
            value="<?php echo isset($_GET['device_name']) ? htmlspecialchars($_GET['device_name']) : ''; ?>"
          >
        </div>

        <div class="mb-3">
          <label for="add-ip-address" class="form-label">IP Address</label>
          <input
            type="text"
            class="form-control"
            id="add-ip-address"
            name="ip_address"
            required
            value="<?php echo isset($_GET['ip_address']) ? htmlspecialchars($_GET['ip_address']) : ''; ?>"
          >
        </div>

        <div class="mb-3">
          <label for="add-api-username" class="form-label">API Username</label>
          <input
            type="text"
            class="form-control"
            id="add-api-username"
            name="api_username"
            required
            value="<?php echo isset($_GET['api_username']) ? htmlspecialchars($_GET['api_username']) : ''; ?>"
          >
        </div>

        <div class="mb-3">
          <label for="add-api-password" class="form-label">API Password</label>
          <input
            type="password"
            class="form-control"
            id="add-api-password"
            name="api_password"
            required
          >
        </div>

        <div class="mb-3">
          <label for="add-api-port" class="form-label">API Port</label>
          <input
            type="number"
            class="form-control"
            id="add-api-port"
            name="api_port"
            required
            value="<?php echo isset($_GET['api_port']) ? (int)$_GET['api_port'] : 8728; ?>"
          >
        </div>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="submit" class="btn btn-success">
          <i class="fas fa-save"></i> Add Device
        </button>
      </div>
    </form>
  </div>
</div>

<!-- Edit Device Modal -->
<div class="modal fade" id="editDeviceModal" tabindex="-1" aria-labelledby="editDeviceModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <form class="modal-content" action="edit_mikrotik_device.php" method="POST" autocomplete="off">
      <div class="modal-header">
        <h5 class="modal-title" id="editDeviceModalLabel"><i class="fas fa-edit"></i> Edit Device</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <input type="hidden" name="id" id="edit-device-id">
        <div class="mb-3">
          <label for="edit-device-name" class="form-label">Device Name</label>
          <input type="text" class="form-control" id="edit-device-name" name="device_name" required>
        </div>
        <div class="mb-3">
          <label for="edit-ip-address" class="form-label">IP Address</label>
          <input type="text" class="form-control" id="edit-ip-address" name="ip_address" required>
        </div>
        <div class="mb-3">
          <label for="edit-api-username" class="form-label">API Username</label>
          <input type="text" class="form-control" id="edit-api-username" name="api_username" required>
        </div>
        <div class="mb-3">
          <label for="edit-api-port" class="form-label">API Port</label>
          <input type="number" class="form-control" id="edit-api-port" name="api_port" required>
        </div>
        <div class="mb-3">
          <label for="edit-api-password" class="form-label">
              API Password <small class="text-muted">(leave blank to keep current)</small>
          </label>
          <input type="password" class="form-control" id="edit-api-password" name="api_password">
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Save Changes</button>
      </div>
    </form>
  </div>
</div>

<!-- Delete Device Modal -->
<div class="modal fade" id="deleteDeviceModal" tabindex="-1" aria-labelledby="deleteDeviceModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <form class="modal-content" action="delete_mikrotik_device.php" method="POST">
      <div class="modal-header">
        <h5 class="modal-title" id="deleteDeviceModalLabel"><i class="fas fa-trash"></i> Delete Device</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <input type="hidden" name="id" id="delete-device-id">
        <p>Are you sure you want to delete <strong id="delete-device-name"></strong>?</p>
        <div class="alert alert-danger mb-0 py-2 px-3 small">
            <i class="fas fa-exclamation-triangle"></i> This action cannot be undone.
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="submit" class="btn btn-danger"><i class="fas fa-trash"></i> Delete</button>
      </div>
    </form>
  </div>
</div>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
function testConnection(deviceName) {
    var safeName = deviceName.replace(/[^a-zA-Z0-9_\-]/g, '');
    var statusTd = $('#status-' + safeName);
    var btn = $('#test-btn-' + safeName);

    statusTd.html('<span class="text-info"><i class="fas fa-spinner fa-spin"></i> Testing...</span>');
    btn.prop('disabled', true);

    $.ajax({
        url: '', // Same file
        type: 'POST',
        data: { device_name: deviceName },
        success: function(response) {
            btn.prop('disabled', false);
            var data = typeof response === 'string' ? JSON.parse(response) : response;
            if (data.status === 'success') {
                statusTd.html('<span class="badge bg-success"><i class="fas fa-check-circle"></i> Connected</span>');
            } else {
                statusTd.html('<span class="badge bg-danger"><i class="fas fa-times-circle"></i> Not Connected</span><br><span class="text-danger small">' + data.error + '</span>');
            }
        },
        error: function() {
            btn.prop('disabled', false);
            statusTd.html('<span class="badge bg-warning">AJAX error</span>');
        }
    });
}

$('#editDeviceModal').on('show.bs.modal', function (event) {
    var button = $(event.relatedTarget);
    $('#edit-device-id').val(button.data('id'));
    $('#edit-device-name').val(button.data('name'));
    $('#edit-ip-address').val(button.data('ip'));
    $('#edit-api-username').val(button.data('username'));
    $('#edit-api-port').val(button.data('port'));
    $('#edit-api-port-8700').val(button.data('port8700'));
    $('#edit-api-password').val('');
});

$('#deleteDeviceModal').on('show.bs.modal', function (event) {
    var button = $(event.relatedTarget);
    $('#delete-device-id').val(button.data('id'));
    $('#delete-device-name').text(button.data('name'));
});

(function () {
    const params = new URLSearchParams(window.location.search);
    if (params.get('error')) {
        const addModal = new bootstrap.Modal(document.getElementById('addDeviceModal'));
        addModal.show();
    }
})();
</script>

<?php
$toastType = $_GET['toast_type'] ?? '';
$toastMsg  = $_GET['toast_msg'] ?? '';
?>
<?php if ($toastMsg !== ''): ?>
    <div aria-live="polite" aria-atomic="true"
         class="position-fixed bottom-0 end-0 p-3"
         style="z-index: 1080;">
        <div id="globalToast"
             class="toast align-items-center text-bg-<?php
                 echo $toastType === 'success'
                     ? 'success'
                     : ($toastType === 'warning' ? 'warning' : 'danger');
             ?> border-0"
             role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <?php echo htmlspecialchars($toastMsg); ?>
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function () {
            var toastEl = document.getElementById('globalToast');
            if (toastEl) {
                var t = new bootstrap.Toast(toastEl, {delay: 4000});
                t.show();
            }
        });
    </script>
<?php endif; ?>
</body>
</html>
