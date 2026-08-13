<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Past Due Customers</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css">
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
</head>
<body>
<main class="container py-4">
    <div class="card mt-2">
        <div class="card-body">
            <h5 class="card-title">Past Due Customers (Auto-Suspended)</h5>

            <div id="message-area"></div>

            <?php if (count($due_customers) > 0): ?>
                <form id="suspend-form" method="POST" action="" style="display:inline-block; margin-bottom:16px;">
                    <input type="hidden" name="action" value="suspend_expired">
                    <?php foreach ($due_customers as $c): ?>
                        <input type="hidden" name="usernames[]" value="<?= htmlspecialchars($c['username']) ?>">
                    <?php endforeach; ?>
                    <button type="button" class="btn btn-warning" id="suspend-button">
                        Suspend &amp; Disconnect All Expired Profiles
                    </button>
                </form>

                <table class="table table-striped table-sm table-bordered">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Username</th>
                            <th>Expires At</th>
                            <th>Mikrotik Profile</th>
                            <th>Mikrotik Devices</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="customer-table">
                        <?php foreach($due_customers as $c): ?>
                            <tr id="row-<?= htmlspecialchars($c['username']) ?>">
                                <td><?= htmlspecialchars($c['full_name']) ?></td>
                                <td><?= htmlspecialchars($c['username']) ?></td>
                                <td><?= htmlspecialchars($c['expires_at']) ?></td>
                                <td><?= htmlspecialchars($c['mikrotik_profile']) ?></td>
                                <td><?= htmlspecialchars($c['mikrotik_devices']) ?></td>
                                <td class="status-cell">Pending</td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php else: ?>
                <p class="text-success">No past due customers!</p>
            <?php endif; ?>
        </div>
    </div>
</main>

<script>
    $(document).ready(function() {
        $('#suspend-button').click(function() {
            const usernames = $("input[name='usernames[]']").map(function() {
                return $(this).val();
            }).get();

            const batchSize = 5; // Adjust as needed
            for (let i = 0; i < usernames.length; i += batchSize) {
                const batch = usernames.slice(i, i + batchSize);

                $.ajax({
                    type: 'POST',
                    url: 'suspend_process.php', // Create this script to handle suspension
                    data: { usernames: batch },
                    success: function(response) {
                        const results = JSON.parse(response);
                        results.forEach(user => {
                            $(`#row-${user.username} .status-cell`).text(user.status);
                        });
                    },
                    error: function() {
                        batch.forEach(username => {
                            $(`#row-${username} .status-cell`).text('Error');
                        });
                    }
                });

                sleep(500); // Mimic server delay
            }
        });
    });

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
</script>
</body>
</html>
