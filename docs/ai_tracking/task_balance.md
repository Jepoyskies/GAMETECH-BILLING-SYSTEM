# Advance Payment (Wallet) Implementation Tasks

- [ ] **1. Database & Models**
    - `outstanding_balance` field will conceptually become `advance_payment`. (Since it's just a rename, we can keep the DB field name `outstanding_balance` to avoid painful migrations, but we'll enforce it to only be >= 0).
    - Update `abs_outstanding_balance` to just return the balance.
    
- [ ] **2. Payment Logic (views.py `pay_customer_view`)**
    - When amount is paid:
        - Deduct exactly 1 month's price if the user is expired or expiring today.
        - The remainder of the payment goes into `outstanding_balance` (Wallet).
        - Update `calculate_new_expiration_date` to only grant time for what was actually consumed.
        - Ensure `outstanding_balance` increases when they overpay!

- [ ] **3. Auto-Renew Logic (auto_suspend.py)**
    - Before suspending an expired user, check if `customer.outstanding_balance >= customer.plan.price`.
    - If YES:
        - Deduct the plan price from `outstanding_balance`.
        - Extend `expires_at` by 1 month.
        - Create a SystemLog or Payment log for the auto-renewal.
        - Do not suspend.
    - If NO:
        - Suspend normally.

- [ ] **4. UI Updates (Templates)**
    - Replace "Outstanding Balance" text with "Advance Payment".
    - Remove the weird negative/positive inversion in `view_customer.html`. Just show the positive number.
    - Update `customer_list.html` and other tables to show "Advance Payment".
    - Update `editBalanceModal` text.
