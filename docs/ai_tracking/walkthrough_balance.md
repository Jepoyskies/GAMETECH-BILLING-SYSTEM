# Advance Payment & Auto-Renew Feature

I have completely overhauled the billing logic to match your desired **Wallet / Advance Payment** workflow! It is now a true, powerful prepaid ISP system.

## 1. UI Terminology Fixed
- "Outstanding Balance" has been completely removed from the UI.
- It is now called **Advance Payment**.
- It will **always** be a positive number (e.g. ₱1,500). No more confusing negative numbers. If a customer owes money or hasn't paid, their balance simply stays at **₱0.00** and their internet gets suspended.

## 2. Smart Payment Splitting (Option B)
When you log a payment, the system now smartly splits the money between **Time** and **Wallet**:

*Example: Customer is on a ₱1,000 plan, and their internet is expired.*
- If they pay **₱2,000**, the system will use **₱1,000** to extend their internet exactly 1 month. The remaining **₱1,000** goes directly into their **Advance Payment** wallet!
- If they pay **₱500** (a partial payment), it just converts the ₱500 into prorated days (half a month) and their wallet stays at ₱0.

## 3. Automated Wallet Renewals
This is the most powerful part of the new system! 
The `auto_suspend` background job has been upgraded. Every time it runs to check for expired users, it now checks their wallets first.
- If a customer's internet expires today, but they have **₱1,000** in their Advance Payment wallet...
- The system will **automatically** deduct the ₱1,000, add 1 month to their internet expiration date, and keep them online!
- It will log the auto-renewal in the `System Logs` and `Payment Logs` so your staff can track it.
- If they don't have enough money in their wallet, it suspends them normally.

> [!TIP]
> This means customers can deposit ₱6,000 into their Advance Payment wallet, and the system will automatically pay their ₱1,000 bill every month for the next 6 months without your staff lifting a finger!

---
All of this is currently live on your Digital Ocean server! Feel free to test it out (create a test customer, give them an advance payment via the edit modal, and then set their expiration date to yesterday to watch the system auto-renew them). 

Whenever you are done testing and want to wipe the database fresh, just let me know!
