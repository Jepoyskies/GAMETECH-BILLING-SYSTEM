<?php
// log_system_action.php

function log_system_action($conn, $table, $record_id, $action, $changed_by, $old_data = null, $new_data = null) {
    $sql = "INSERT INTO system_logs (table_name, record_id, action, changed_by, changed_at, old_data, new_data)
            VALUES (:table_name, :record_id, :action, :changed_by, NOW(), :old_data, :new_data)";
    $stmt = $conn->prepare($sql);
    $stmt->execute([
        ':table_name' => $table,
        ':record_id'  => $record_id,
        ':action'     => $action,
        ':changed_by' => $changed_by,
        ':old_data'   => $old_data ? json_encode($old_data, JSON_UNESCAPED_UNICODE) : null,
        ':new_data'   => $new_data ? json_encode($new_data, JSON_UNESCAPED_UNICODE) : null
    ]);
}
?>
