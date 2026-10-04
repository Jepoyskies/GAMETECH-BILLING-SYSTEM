# Insert @billing_required above a curated list of billing/customer views that
# currently carry only @login_required. Mechanical, idempotent, and it refuses to
# touch a view that already has a role gate.
$targets = @{
    "billing\views_receipt.py"                                   = @("payment_receipt_view")
    "billing\views\cignal_dashboard.py"                          = @(
        "cignal_dashboard_view","process_cignal_payment","edit_cignal_subscription",
        "cancel_cignal_subscription","restore_cignal_subscription",
        "purge_cignal_subscription","purge_all_cancelled_cignal_subscriptions",
        "cignal_applications_view","cancel_cignal_application","cignal_logs_view",
        "cignal_export_csv_view")
    "billing\views\services.py"                                  = @(
        "subscription_plans_view","sync_plans_from_mikrotik","cignal_play_list_view",
        "add_on_payments_view","cignalplay_form_view","user_cignal_logs_view",
        "apply_cignal_addon","plan_list","add_plan","edit_plan","delete_plan")
    "billing\views\settings.py"                                  = @(
        "addon_plan_list","create_addon_plan","edit_addon_plan","delete_addon_plan")
    "billing\views\xendit.py"                                    = @("create_xendit_invoice")
}

$changed = @()
foreach ($file in $targets.Keys) {
    if (-not (Test-Path $file)) { Write-Host "MISSING: $file"; continue }
    $lines = [System.IO.File]::ReadAllLines((Resolve-Path $file))
    $out = New-Object System.Collections.Generic.List[string]
    $modded = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $l = $lines[$i]
        if ($l -match '^def\s+(\w+)\s*\(') {
            $fn = $Matches[1]
            if ($targets[$file] -contains $fn) {
                # look back at the contiguous decorator block already emitted
                $j = $out.Count - 1
                $block = @()
                while ($j -ge 0 -and $out[$j] -match '^\s*@') { $block = @($out[$j]) + $block; $j-- }
                $already = ($block -join ' ') -match 'role_required|billing_required|permission_required|module_required|user_passes_test|dispatch_permission_required|action_required'
                if (-not $already) {
                    $indent = ($l -replace '^(\s*).*','$1')
                    $out.Add("${indent}@billing_required")
                    $modded = $true
                }
            }
        }
        $out.Add($l)
    }
    if ($modded) {
        [System.IO.File]::WriteAllLines((Resolve-Path $file), $out)
        $changed += $file
        Write-Host "PATCHED: $file"
    }
}
Write-Host ""
Write-Host "files changed: $($changed.Count)"