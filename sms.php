<?php
include 'header.php';
require 'database.php';
require 'semaphore.php';

$semaphore_apikey = "a1be64e85146a946d40aeb1677d37a48";

// SMS log helper
function logSms($conn, $phone, $message, $response, $status='success') {
    $stmt = $conn->prepare("INSERT INTO sms_log (phone, message, response, status) VALUES (?, ?, ?, ?)");
    $stmt->execute([$phone, $message, $response, $status]);
}

// Handle SMS sending (bulk or single)
$sms_feedback = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (isset($_POST['bulk_send_sms'], $_POST['selected_phones'], $_POST['bulk_message'])) {
        $phones = explode(',', $_POST['selected_phones']);
        $bulk_message = $_POST['bulk_message'];
        foreach ($phones as $phone) {
            $response = sendSemaphoreSMS($semaphore_apikey, $phone, $bulk_message);
            $status = (stripos($response, 'success') !== false) ? 'success' : 'error';
            logSms($conn, $phone, $bulk_message, $response, $status);
        }
        $sms_feedback = "Bulk SMS sent to ".count($phones)." recipients.";
    } elseif (isset($_POST['send_sms_custom'], $_POST['phone'], $_POST['message'])) {
        $phone = $_POST['phone'];
        $message = $_POST['message'];
        $response = sendSemaphoreSMS($semaphore_apikey, $phone, $message);
        $status = (stripos($response, 'success') !== false) ? 'success' : 'error';
        logSms($conn, $phone, $message, $response, $status);
        $sms_feedback = "SMS sent to $phone. Response: $response";
    }
}

// Pagination setup
$limit = 10;
$page = isset($_GET['page']) && is_numeric($_GET['page']) ? (int)$_GET['page'] : 1;
$page = max($page, 1);
$offset = ($page - 1) * $limit;

// Search
$search = isset($_GET['search']) ? trim($_GET['search']) : '';
$params = [];
$where = "WHERE username IS NOT NULL AND username != ''";
if ($search !== '') {
    $where .= " AND (username LIKE :search OR full_name LIKE :search OR phone LIKE :search OR address LIKE :search OR status LIKE :search)";
    $params[':search'] = "%{$search}%";
}

// Count total for pagination
try {
    $count_sql = "SELECT COUNT(*) FROM customers $where";
    $stmt = $conn->prepare($count_sql);
    $stmt->execute($params);
    $total = $stmt->fetchColumn();
} catch (PDOException $e) {
    $total = 0;
}

// Fetch customers with pagination
try {
    $sql = "SELECT username, full_name, address, status, phone
            FROM customers
            $where
            ORDER BY full_name ASC
            LIMIT :limit OFFSET :offset";
    $stmt = $conn->prepare($sql);
    foreach ($params as $k => $v) {
        $stmt->bindValue($k, $v, PDO::PARAM_STR);
    }
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
} catch (PDOException $e) {
    $sms_feedback = "Database error: " . htmlspecialchars($e->getMessage());
    $rows = [];
}

$total_pages = max(ceil($total / $limit), 1);

// Fetch SMS Logs
$logs = [];
try {
    $stmt = $conn->query("SELECT * FROM sms_log ORDER BY sent_at DESC LIMIT 100");
    $logs = $stmt->fetchAll(PDO::FETCH_ASSOC);
} catch (PDOException $e) {}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <title>SMS Reminder</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        body { background: #f2f5fa; }
        .tab-pane { margin-top: 2rem; }
        .sms-preview { font-family: monospace; background: #f8f9fa; padding: 8px; border-radius: 4px; min-height: 50px;}
        .sms-counter { font-size: 0.95em; }
        .sms-counter.warn { color: #d9534f; font-weight: bold; }
        .toast-container { position: fixed; top: 1rem; right: 1rem; z-index: 1056; }
        .card-table { border-radius: 1rem; }
        .table th, .table td { vertical-align: middle !important; }
    </style>
</head>
<body>
<div class="container py-4">
    <div class="toast-container">
        <?php if ($sms_feedback): ?>
            <div class="toast show align-items-center text-white bg-info border-0 mb-2" role="alert">
                <div class="d-flex">
                    <div class="toast-body"><?php echo htmlspecialchars($sms_feedback); ?></div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        <?php endif; ?>
    </div>
    <h2 class="fw-bold text-primary mb-3">
        <i class="fa-solid fa-message"></i> Auto SMS Reminder
    </h2>
    <ul class="nav nav-tabs" id="smsTabs" role="tablist">
      <li class="nav-item" role="presentation">
        <button class="nav-link active" id="reminder-tab" data-bs-toggle="tab" data-bs-target="#reminder" type="button" role="tab"><i class="fa fa-user-clock"></i> Reminders</button>
      </li>
      <li class="nav-item" role="presentation">
        <button class="nav-link" id="log-tab" data-bs-toggle="tab" data-bs-target="#log" type="button" role="tab"><i class="fa fa-list"></i> SMS Log</button>
      </li>
    </ul>
    <div class="tab-content" id="smsTabsContent">
      <!-- Reminders Tab -->
      <div class="tab-pane fade show active" id="reminder" role="tabpanel">
        <!-- Search and Bulk Bar -->
        <div class="row my-3 align-items-center">
            <div class="col-md-8 mb-2 mb-md-0">
                <form class="input-group" method="get" action="">
                    <input type="search" name="search" class="form-control"
                           placeholder="Search by name, username, phone, address or status"
                           value="<?php echo htmlspecialchars($search); ?>">
                    <button class="btn btn-primary" type="submit">
                        <i class="fas fa-search me-1"></i> Search
                    </button>
                </form>
            </div>
            <div class="col-md-4 text-end">
                <button type="button" class="btn btn-outline-secondary" onclick="window.location.reload();">
                    <i class="fas fa-sync-alt"></i> Refresh
                </button>
            </div>
        </div>
        <!-- Bulk Form -->
        <form id="bulkForm" method="post">
            <input type="hidden" name="selected_phones" id="bulkPhones">
            <input type="hidden" name="bulk_message" id="bulkMessage">
            <div class="d-flex mb-2 gap-2" id="bulkBar" style="display:none;">
                <button type="button" class="btn btn-success" id="bulkSendBtn"><i class="fa fa-paper-plane"></i> Send to Selected</button>
                <div id="bulkCount" class="align-self-center"></div>
                <button type="button" class="btn btn-outline-danger btn-sm" id="bulkClearBtn">Clear Selection</button>
            </div>
        </form>
        <!-- Users Table with SMS -->
        <div class="card card-table shadow-sm border-0">
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="table-light">
                        <tr>
                            <th><input type="checkbox" id="selectAll"></th>
                            <th>Username</th>
                            <th>Full Name</th>
                            <th>Address</th>
                            <th>Status</th>
                            <th>Phone</th>
                            <th>Send SMS</th>
                        </tr>
                        </thead>
                        <tbody>
                        <?php if (!empty($rows)): ?>
                            <?php foreach($rows as $row): ?>
                                <?php $default_message = "Hello {$row['full_name']}! Kindly renew your subscription. Thank you!"; ?>
                                <tr>
                                    <td>
                                        <input type="checkbox" class="row-checkbox" data-phone="<?php echo htmlspecialchars($row['phone']); ?>">
                                    </td>
                                    <td><span class="fw-semibold text-primary"><?php echo htmlspecialchars($row['username']); ?></span></td>
                                    <td><?php echo htmlspecialchars($row['full_name']); ?></td>
                                    <td><?php echo htmlspecialchars($row['address']); ?></td>
                                    <td>
                                        <?php if (strtolower($row['status']) === 'active'): ?>
                                            <span class="badge bg-success"><?php echo htmlspecialchars($row['status']); ?></span>
                                        <?php elseif (strtolower($row['status']) === 'inactive'): ?>
                                            <span class="badge bg-secondary"><?php echo htmlspecialchars($row['status']); ?></span>
                                        <?php else: ?>
                                            <span class="badge bg-warning text-dark"><?php echo htmlspecialchars($row['status']); ?></span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <div class="d-flex align-items-center gap-2">
                                            <span class="badge bg-light text-dark border py-2 px-2" style="font-size:1em;">
                                                <i class="fa fa-phone text-success"></i>
                                                <a href="tel:<?php echo htmlspecialchars($row['phone']); ?>" class="text-decoration-none text-dark">
                                                    <?php echo htmlspecialchars($row['phone']); ?>
                                                </a>
                                            </span>
                                            <button type="button" class="btn btn-outline-secondary btn-sm btn-copy" data-phone="<?php echo htmlspecialchars($row['phone']); ?>" title="Copy phone">
                                                <i class="fa fa-copy"></i>
                                            </button>
                                        </div>
                                    </td>
                                    <td>
                                        <button type="button"
                                            class="btn btn-sm btn-primary btn-edit-sms"
                                            data-phone="<?php echo htmlspecialchars($row['phone']); ?>"
                                            data-full_name="<?php echo htmlspecialchars($row['full_name']); ?>"
                                            data-default_message="<?php echo htmlspecialchars($default_message); ?>">
                                                                                        <i class="fa fa-paper-plane"></i> Edit &amp; Send
                                        </button>
                                    </td>
                                </tr>
                            <?php endforeach; ?>
                        <?php else: ?>
                          <tr>
                              <td colspan="7" class="text-center text-muted py-4">
                                  <i class="fas fa-user-slash fa-2x mb-2"></i><br>
                                  No customers found
                              </td>
                          </tr>
                        <?php endif; ?>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <!-- Pagination -->
        <?php if ($total_pages > 1): ?>
            <nav class="mt-3">
                <ul class="pagination justify-content-center">
                    <li class="page-item<?php if ($page <= 1) echo ' disabled'; ?>">
                        <a class="page-link" href="?<?php echo http_build_query(array_merge($_GET, ['page'=>max($page-1,1)])); ?>">&laquo; Prev</a>
                    </li>
                    <?php
                    // Show up to 5 page links
                    $start = max(1, $page - 2);
                    $end = min($total_pages, $page + 2);
                    for ($i = $start; $i <= $end; $i++): ?>
                        <li class="page-item<?php if ($i == $page) echo ' active'; ?>">
                            <a class="page-link" href="?<?php echo http_build_query(array_merge($_GET, ['page'=>$i])); ?>"><?php echo $i; ?></a>
                        </li>
                    <?php endfor; ?>
                    <li class="page-item<?php if ($page >= $total_pages) echo ' disabled'; ?>">
                        <a class="page-link" href="?<?php echo http_build_query(array_merge($_GET, ['page'=>min($page+1,$total_pages)])); ?>">Next &raquo;</a>
                    </li>
                </ul>
            </nav>
        <?php endif; ?>
      </div>
      <!-- END Reminders Tab -->

      <!-- SMS Log Tab -->
      <div class="tab-pane fade" id="log" role="tabpanel">
          <div class="card shadow-sm border-0 mt-4">
              <div class="card-header bg-primary text-white">
                  <i class="fa fa-list"></i> SMS Log (last 100)
              </div>
              <div class="card-body p-0">
                  <div class="table-responsive">
                      <table class="table table-striped mb-0">
                          <thead class="table-light">
                              <tr>
                                  <th>Sent At</th>
                                  <th>Phone</th>
                                  <th>Message</th>
                                  <th>Response</th>
                              </tr>
                          </thead>
                          <tbody>
                              <?php if ($logs): ?>
                                  <?php foreach ($logs as $log): ?>
                                      <tr>
                                          <td><?php echo htmlspecialchars($log['sent_at']); ?></td>
                                          <td><?php echo htmlspecialchars($log['phone']); ?></td>
                                          <td><?php echo nl2br(htmlspecialchars($log['message'])); ?></td>
                                          <td style="max-width:200px; word-break:break-word;"><?php echo htmlspecialchars($log['response']); ?></td>
                                      </tr>
                                  <?php endforeach; ?>
                              <?php else: ?>
                                  <tr>
                                      <td colspan="4" class="text-center text-muted py-4">
                                          <i class="fas fa-inbox-open-text fa-2x mb-2"></i><br>
                                          No SMS logs yet.
                                      </td>
                                  </tr>
                              <?php endif; ?>
                          </tbody>
                      </table>
                  </div>
              </div>
          </div>
      </div>
      <!-- END SMS Log Tab -->
    </div>
</div>

<!-- SMS Edit Modal -->
<div class="modal fade" id="editSmsModal" tabindex="-1" aria-labelledby="editSmsModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <form id="editSmsForm" method="post">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="editSmsModalLabel"><i class="fa fa-paper-plane"></i> Edit and Send SMS</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <input type="hidden" name="phone" id="smsPhone">
          <div class="mb-2">
            <label for="smsTemplates" class="form-label">Templates</label>
            <select id="smsTemplates" class="form-select">
              <option value="">-- Choose a template --</option>
              <option value="Hello {name}! Kindly renew your subscription. Thank you!">Default</option>
              <option value="Dear {name}, please renew your account to continue services.">Polite</option>
              <option value="Hi {name}, renew now to avoid interruption.">Short</option>
            </select>
          </div>
          <div class="mb-2">
            <label for="smsMessage" class="form-label">Message</label>
            <textarea class="form-control" name="message" id="smsMessage" rows="4" required></textarea>
            <div class="d-flex justify-content-between mt-1">
              <span id="smsCharCount" class="sms-counter">0/160</span>
              <span id="smsCharWarning" class="sms-counter warn d-none"><i class="fa fa-exclamation-triangle"></i> Over 160 chars!</span>
            </div>
          </div>
          <div class="mb-2">
            <label class="form-label">Preview</label>
            <div class="sms-preview" id="smsPreview"></div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="submit" name="send_sms_custom" class="btn btn-primary"><i class="fa fa-paper-plane"></i> Send SMS</button>
        </div>
      </div>
    </form>
  </div>
</div>
<!-- END SMS Edit Modal -->

<!-- Bulk SMS Modal -->
<div class="modal fade" id="bulkSmsModal" tabindex="-1" aria-labelledby="bulkSmsModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <form id="bulkSmsForm" method="post">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="bulkSmsModalLabel"><i class="fa fa-paper-plane"></i> Send Bulk SMS</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <input type="hidden" name="selected_phones" id="bulkModalPhones">
          <div class="mb-2">
            <label for="bulkSmsTemplates" class="form-label">Templates</label>
            <select id="bulkSmsTemplates" class="form-select">
              <option value="">-- Choose a template --</option>
              <option value="Hello! Kindly renew your subscription. Thank you!">Default</option>
              <option value="Dear customer, please renew your account to continue services.">Polite</option>
              <option value="Hi, renew now to avoid interruption.">Short</option>
            </select>
          </div>
          <div class="mb-2">
            <label for="bulkSmsMessage" class="form-label">Message</label>
            <textarea class="form-control" name="bulk_message" id="bulkSmsMessage" rows="4" required></textarea>
            <div class="d-flex justify-content-between mt-1">
              <span id="bulkSmsCharCount" class="sms-counter">0/160</span>
              <span id="bulkSmsCharWarning" class="sms-counter warn d-none"><i class="fa fa-exclamation-triangle"></i> Over 160 chars!</span>
            </div>
          </div>
          <div class="mb-2">
            <label class="form-label">Preview</label>
            <div class="sms-preview" id="bulkSmsPreview"></div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="submit" name="bulk_send_sms" class="btn btn-success"><i class="fa fa-paper-plane"></i> Send Bulk SMS</button>
        </div>
      </div>
    </form>
  </div>
</div>
<!-- END Bulk SMS Modal -->

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
document.querySelectorAll('.btn-copy').forEach(function(btn) {
    btn.addEventListener('click', function() {
        var phone = btn.getAttribute('data-phone');
        navigator.clipboard.writeText(phone);
        btn.innerHTML = '<i class="fa fa-check"></i>';
        setTimeout(function() { btn.innerHTML = '<i class="fa fa-copy"></i>'; }, 1000);
    });
});

// Show modal and fill data for sending SMS
let lastSmsMessage = '';
document.querySelectorAll('.btn-edit-sms').forEach(function(btn) {
    btn.addEventListener('click', function() {
        var phone = btn.getAttribute('data-phone');
        var full_name = btn.getAttribute('data-full_name');
        var default_message = btn.getAttribute('data-default_message');
        document.getElementById('smsPhone').value = phone;
        let msg = lastSmsMessage || default_message;
        document.getElementById('smsMessage').value = msg;
        document.getElementById('smsPreview').innerText = msg;
        updateCharCount('smsMessage', 'smsCharCount', 'smsCharWarning');
        document.getElementById('smsMessage').dataset.fullName = full_name;
        document.getElementById('smsTemplates').selectedIndex = 0;
        new bootstrap.Modal(document.getElementById('editSmsModal')).show();
    });
});
document.getElementById('smsTemplates').addEventListener('change', function() {
    let template = this.value;
    let msgField = document.getElementById('smsMessage');
    let fullName = msgField.dataset.fullName || '';
    if (template) {
        template = template.replace('{name}', fullName);
        msgField.value = template;
        msgField.dispatchEvent(new Event('input'));
    }
});
document.getElementById('smsMessage').addEventListener('input', function() {
    updateCharCount('smsMessage', 'smsCharCount', 'smsCharWarning');
    document.getElementById('smsPreview').innerText = this.value;
    lastSmsMessage = this.value;
});

// Bulk selection logic
let selectedPhones = new Set();
document.querySelectorAll('.row-checkbox').forEach(function(cb) {
    cb.addEventListener('change', function() {
        let phone = cb.getAttribute('data-phone');
        if (cb.checked) selectedPhones.add(phone);
        else selectedPhones.delete(phone);
        updateBulkBar();
    });
});
document.getElementById('selectAll')?.addEventListener('change', function() {
    let allChecked = this.checked;
    document.querySelectorAll('.row-checkbox').forEach(function(cb) {
        cb.checked = allChecked;
        let phone = cb.getAttribute('data-phone');
        if (allChecked) selectedPhones.add(phone);
        else selectedPhones.delete(phone);
    });
    updateBulkBar();
});
function updateBulkBar() {
    let bar = document.getElementById('bulkBar');
    let count = document.getElementById('bulkCount');
    if (selectedPhones.size > 0) {
        bar.style.display = '';
        count.textContent = `${selectedPhones.size} selected`;
    } else {
        bar.style.display = 'none';
        count.textContent = '';
    }
}
document.getElementById('bulkClearBtn').addEventListener('click', function() {
    selectedPhones.clear();
    document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('selectAll') && (document.getElementById('selectAll').checked = false);
    updateBulkBar();
});
document.getElementById('bulkSendBtn').addEventListener('click', function() {
    document.getElementById('bulkModalPhones').value = Array.from(selectedPhones).join(',');
    let msg = localStorage.getItem('lastBulkMessage') || "Hello! Kindly renew your subscription. Thank you!";
    document.getElementById('bulkSmsMessage').value = msg;
    document.getElementById('bulkSmsPreview').innerText = msg;
    updateCharCount('bulkSmsMessage', 'bulkSmsCharCount', 'bulkSmsCharWarning');
    document.getElementById('bulkSmsTemplates').selectedIndex = 0;
    new bootstrap.Modal(document.getElementById('bulkSmsModal')).show();
});
document.getElementById('bulkSmsTemplates').addEventListener('change', function() {
    let template = this.value;
    let msgField = document.getElementById('bulkSmsMessage');
    if (template) {
        msgField.value = template;
        msgField.dispatchEvent(new Event('input'));
    }
});
document.getElementById('bulkSmsMessage').addEventListener('input', function() {
    updateCharCount('bulkSmsMessage', 'bulkSmsCharCount', 'bulkSmsCharWarning');
    document.getElementById('bulkSmsPreview').innerText = this.value;
    localStorage.setItem('lastBulkMessage', this.value);
});
function updateCharCount(textareaId, counterId, warningId) {
    let len = document.getElementById(textareaId).value.length;
    document.getElementById(counterId).textContent = len + '/160';
    if (len > 160) {
        document.getElementById(warningId).classList.remove('d-none');
    } else {
        document.getElementById(warningId).classList.add('d-none');
    }
}
setTimeout(function() {
    document.querySelectorAll('.toast').forEach(function(toast) {
        var bsToast = bootstrap.Toast.getOrCreateInstance(toast);
        bsToast.hide();
    });
}, 3000);
</script>
<?php include 'footer.php'; ?>
</body>
</html>
