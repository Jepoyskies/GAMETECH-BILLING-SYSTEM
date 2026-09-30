# Verification screenshots — UI design-system migration

Reference (the source of truth) and converted modals, captured on production
2026-09-30 at 1366×768 (mobile shot at 390×844). Light and dark for each.

## Reference — Customers Directory
| | |
|---|---|
| `customers-page-light.png` | Light mode. Hero header, KPI tiles, filter pills, table-card. The design every modal must match. |
| `customers-page-dark.png` | Dark mode (navy/indigo gradient cards, gold accents). |

## Enroll Customer in Cignal (Batch 0 — the reference conversion)
| | |
|---|---|
| `enroll-modal-light-full.png` | Full modal: 3 numbered sections, live summary card (Box installment + TV load = **Total due ₱399** in large gold), footer with blue `gt-btn-primary`. |
| `enroll-modal-light.png` | Light mode, scrolling view. |
| `enroll-modal-dark.png` | Dark parity — same structure, gold accents. |
| `enroll-modal-mobile.png` | 390px: full-screen sheet, single column. |

Verified live: total updates ₱399 → ₱3,149 when Hardware Setup changes to Cashout;
primary button disabled until a customer + device number are valid; Esc closes; 0 JS errors.

## Reload Cignal Subscription (Batch 1)
| | |
|---|---|
| `cignal-payment-light.png` | Token-based preset pills (gold when active), status card, live rollover preview. Green submit replaced by `gt-btn-primary`. |
| `cignal-payment-dark.png` | Dark parity. |

## Request Service → Dispatch Queue (Batch 3)
| | |
|---|---|
| `request-service-light.png` | Shared shell, gold active-order warning callout, subscriber summary card, blue primary. |
| `request-service-dark.png` | Dark parity. |

All pesos render as `₱` (the `â‚±` mojibake bug is fixed — see ERR-086).
See `../UI_MIGRATION_HANDOFF.md` for the full migration status.
