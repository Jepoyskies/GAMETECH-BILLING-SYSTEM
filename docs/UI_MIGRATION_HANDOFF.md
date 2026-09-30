# UI Design-System Migration — Handoff

> **Purpose**: resume the "make everything look like the Customers page" work on a new device/session.
> **Started**: 2026-09-30 · **Status**: Batches 1–3 done, live on production. Batches 4–5 not started.
> **All work is committed and pushed to `origin/main`.** Nothing is only on one laptop.

---

## 1. The goal

Every modal and form should use the **shared Gametech design system** defined in
`static/css/gt/` so it looks like the **Customers Directory** page (`/customers/`) in **both
light and dark mode**. The Customers page is the source of truth. **No inline styles, no
hard-coded hex** — tokens and shared classes only.

### Rules that must hold
| Rule | Meaning |
|---|---|
| **Preserve hooks** | Never change element `id`s, `name`s, `data-*` attributes, JS function names, `onclick`/`onchange` handlers, or form actions. Presentation only. |
| **No red** | Red is only for genuine danger/destructive. Primary actions use `gt-btn-primary` (brand blue in light, brand gold in dark). |
| **No cyan, no purple** | Section titles use `--section-accent-text`. |
| **Gold = focus / selected / active** | |
| **Front-end only** | No backend logic changes. |
| **Zero-scan** | Use `gametech_filing_index.md` to find files; never scan directories. |

---

## 2. What is DONE (live on production)

### Batch 0 — the reference modal
| Modal | File |
|---|---|
| Enroll Customer in Cignal | `billing/templates/billing/partials/_cignal_enroll_modal.html` (full rebuild) |

### Batch 1 — Cignal
| Modal | File |
|---|---|
| Record Cignal Enrollment | `billing/templates/billing/partials/_cignal_activation_modal.html` |
| Edit Cignal Subscription | `billing/templates/billing/partials/_cignal_edit_modal.html` |
| Reload Cignal Subscription | `billing/templates/billing/partials/_cignal_payment_modal.html` |

### Batch 2 — plans
| Modal | File |
|---|---|
| Edit / Delete / Create Add-on Plan | `billing/templates/billing/addon_plans_list.html` |

### Batch 3 — customer + billing forms
| Modal | File |
|---|---|
| Force Reactivate, Customer Health, Edit Expiration, Edit Balance, Single SMS, Single Email | `billing/templates/billing/view_customer/_modals.html` |
| Confirm Customer Installation | `billing/templates/billing/view_customer/_modal_mark_installed.html` |
| Request Service (Dispatch Queue) | `billing/templates/billing/view_customer/_modal_customer_repair.html` |
| Choose Service Plan (Renew/Pay Bill) | `billing/templates/billing/pay_customer.html` |
| Record Applicant Policy Decline | `billing/templates/billing/add_customer.html` |

**Counts on a live customer profile page: 11 shared modal shells, 0 legacy `gt-modal-content`.**

---

## 3. Shared components added (all in `static/css/gt/`)

`surfaces.css`:
| Class | Purpose |
|---|---|
| `.gt-modal-card` | modal shell — same gradient/border/radius/shadow as the Customers table card |
| `.gt-modal-scroll` | fixed header/footer, scrollable body, `100dvh` max, full-screen sheet on mobile |
| `.gt-modal-icon` | circular gold icon badge for modal headers |
| `.gt-form-section`, `.gt-section-badge`, `.gt-section-title` | divider-separated numbered sections |
| `.gt-optional-tag` | small muted "Optional" tag |
| `.gt-avatar` | initials circle |
| `.gt-search` + `.gt-search-clear`, `.gt-search--clear` | search pill + inner clear button |
| `.gt-summary-card`, `.gt-summary-row/label/value/total/total-value` | live total card |
| `.gt-summary-balance` | warning badge for remaining balance / overpaid |
| `.gt-callout`, `.gt-callout--info/--success/--warning` | semantic banner (replaces inline-coloured boxes) |
| `.gt-count-badge` | neutral count pill |
| `.gt-input-error` | danger border + ring for invalid fields |
| `.gt-input-mono` | monospace for account/box numbers |
| `.enroll-picker-list`, `.enroll-cust-card`, `.enroll-check-badge`, `.enroll-selected-banner` | customer picker (note: these names are JS hooks — do not rename) |

`components.css`:
| Class | Purpose |
|---|---|
| `.gt-btn-primary:disabled` | dimmed primary with not-allowed cursor |
| `.gt-spinner` | inline loading spinner |
| `.gt-preset-btn` (+ `.active`/`.border-2`) | neutral preset pill, gold when active |
| backdrop `.modal-backdrop.show` | now `blur(4px)` |
| `.modal-header` gap fix | keeps close-button gap on narrow modals |

---

## 4. Two real bugs found and fixed

1. **Peso sign mojibake** — `₱` was double-encoded (`â‚±`, U+00E2 U+201A U+00B1) in **21 places across 6 files**. Source-level fix; no charset change needed. Logged as **ERR-086** in `gametech_error_runbook.md`. *Check any new file for this before shipping.*
2. **Unclosed `.modal` div** in `_cignal_activation_modal.html` (48 opens / 47 closes). It only rendered when a pending application existed, so the dashboard test never caught it. **Always run a div-balance check on any rewritten modal.**

---

## 5. What is NOT done

| Batch | Area | Files |
|---|---|---|
| **4** | Dispatch | `dispatch/pipeline/_queue_assign_modal.html`, `_queue_timer_modal.html`, `5_approval.html`, `4_qa.html`, `tech_mobile.html`, `_modals.html`, `_management_modals.html`, `_modal_add_monitoring_record.html`, `_modal_dispatch_detail.html`, `cignal_install.html`, `internet_install.html`, `client_concerns.html` |
| **5** | Admin | `manage_roles.html`, `partials/_modal_add_staff.html`, `agents/_add_agent_modal.html`, `prospects/detail.html`, `partials/update_health_modal.html`, `view_agent.html` |
| 6 (optional) | Misc | `customer_list/_modals.html` (bulk SMS/Email/Transfer), `subscription_plans.html`, `sms_messaging.html`, `payouts/index.html`, `network_manager/*` (7 modals) |
| 7 (optional) | Page-level | `addon_plans_list.html` still has 7 hard-coded hex in KPI icons (incl. purple `#9333ea`) |

### ⛔ DO NOT TOUCH (frozen — AGENTS.md rule 39 / PAGE_FREEZE_REGISTRY.md)
- `billing/templates/billing/login.html`
- `billing/templates/billing/live_monitoring/` (all 5 modals)
- `billing/templates/billing/dashboard/` and `dashboard.html`
  *(The Dashboard itself is the visual baseline and must never change.)*

---

## 6. ⚠️ Known infrastructure problem (unresolved)

**The droplet's containers are cleanly stopped/started every ~15–20 minutes.**
Observed repeatedly on 2026-09-30: `docker restart` on the host or a page load triggers the
whole stack to cycle. Symptoms: transient `502 Bad Gateway`, `site: 000`, and **DB rows created
via `manage.py shell` disappear** (a temp user was wiped 3×).

- `RestartCount` stays `0` — containers are **not** crash-looping
- no OOM kills, no cron job, no systemd timer, no watchdog process found
- `docker compose up -d` always recovers it
- `git pull` sometimes fails with `unable to update local ref` (retry; the pull often landed anyway)

**Before trusting any verification on this box: check `docker ps`, and re-create any temp rows.**

---

## 7. How to verify (headless, no display needed)

The production box has no display, so `browser.screenshot` fails there. **Playwright is already
installed on the droplet host** (not in the container) and works headlessly.

```bash
# 1. login + screenshot a page  (write the script locally, pipe it — see note below)
cmd /c type script.py | ssh root@143.198.207.144 "python3 -"
```

```python
from playwright.sync_api import sync_playwright
BASE, OUT = "http://143.198.207.144", "/root/shots"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1366, "height": 1050})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"{BASE}/login/", wait_until="domcontentloaded")
    pg.fill('input[name="username"]', "<user>"); pg.fill('input[name="password"]', "<pass>")
    pg.click('button[type="submit"]'); pg.wait_for_timeout(4000)
    pg.goto(f"{BASE}/customers/view/46/"); pg.wait_for_timeout(3500)
    pg.evaluate("() => bootstrap.Modal.getOrCreateInstance(document.getElementById('markInstalledModal')).show()")
    pg.wait_for_timeout(800); pg.screenshot(path=f"{OUT}/shot.png")
    print("PAGE_ERRORS:", len(errs))
    b.close()
```

Then pull the PNGs (base64, because `scp`/binary pipes are unreliable from PowerShell):
```bash
ssh root@143.198.207.144 "tar czf - -C /root/shots shot.png | base64 -w0" > s.b64
# decode locally: re.sub(rb'[^A-Za-z0-9+/=]', b'', raw) -> base64.b64decode -> tarfile
```

### Gotchas that cost time
- **`scp` from/to Windows mangles paths**; `ssh ... "cat > file" < file` is rejected by PowerShell. Use `cmd /c type file.py | ssh host "python3 -"`.
- **Pipe a here-string for `manage.py shell`**, never `python -c` (PowerShell eats `;` and parens).
- **Don't use `wait_for_url("**/cignal-dashboard/**")`** after login — it matches the *login* URL
  (the `next` param). Wait for a page element instead, e.g. `wait_for_selector("h1.gt-header-title")`.
- Customer profile URL is `/customers/view/<id>/`. Rows link to `/customer/<id>/cignal-logs/`
  (a sub-tab) — not the profile.
- Create the verify user, then screenshot **immediately** — the DB cycle will delete it.

### Render checks (fast, read-only, no browser)
```bash
# every converted modal: shared classes present, legacy absent, divs balanced
@'
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer
c = Client()
c.force_login(get_user_model().objects.filter(is_staff=True).first())
html = c.get(f"/customers/view/{Customer.objects.first().id}/").content.decode()
print("shells:", html.count("gt-modal-card"), "| legacy:", html.count("gt-modal-content"))
print("mojibake:", "\u00e2\u201a\u00b1" in html)
'@ | ssh root@143.198.207.144 "docker exec -i gametech-web python manage.py shell"
```

---

## 8. Standard deploy

```powershell
git add -A; git commit -m "feat(scope): ..."; git push origin main
ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"
ssh root@143.198.207.144 "docker exec gametech-web python manage.py collectstatic --noinput"   # if static/
ssh root@143.198.207.144 "docker restart gametech-web"
```
If Nginx returns 502: `ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && docker compose up -d"`
Chain with `;` — this is PowerShell (`&&` is a parse error).

---

## 9. Verification screenshots

Saved in `docs/ui-verify/` (on GitHub, viewable from any device):

| File | Shows |
|---|---|
| `customers-page-light.png` / `customers-page-dark.png` | the source-of-truth reference |
| `enroll-modal-light-full.png` | full Enroll modal incl. summary card + footer |
| `enroll-modal-light.png` / `enroll-modal-dark.png` | light/dark parity |
| `enroll-modal-mobile.png` | 390px full-screen single-column sheet |
| `cignal-payment-light.png` / `-dark.png` | preset pills, gold active state, live rollover |
| `request-service-light.png` / `-dark.png` | converted Dispatch Queue modal |

---

## 10. Suggested next step

Start **Batch 4 (dispatch)** with `dispatch/pipeline/_queue_timer_modal.html` (small, self-contained
→ validates the pattern) then `_queue_assign_modal.html` → `dispatch/_modals.html` (5 modals).
Batch 5 (admin) last. Then, only if asked, the page-level pass for the Cignal Play pages
(Dashboard / Applications / Activity Logs / Plans → hero header, KPI tiles, filter pills, table-card).
