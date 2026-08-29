# Fix Outstanding Balance & Prepaid Logic

The current system has a confusing mix of prepaid and postpaid logic. When you log a payment of ₱1,500, the system currently does **two** things:
1. It extends the customer's internet Expiration Date by ₱1,500 worth of time.
2. It subtracts ₱1,500 from their "Outstanding Balance" in the database, making it `-1500`.

The UI then sees `-1500`, gets confused, and displays `₱1500.00` next to the label **Outstanding Balance**, making it look like they owe ₱1,500 when they just paid!

## Proposed Changes

To make this a true, easy-to-understand **Prepaid System** as you requested, we need to change how the system handles payments and balances.

### 1. Rename to "Wallet / Advance Payment"
We will rename "Outstanding Balance" across the UI to **"Advance Payment"**. 
- A positive number (₱1,000) will mean the customer has extra money sitting in their account.
- ₱0 will mean they have no extra money.
- It will **never** go negative. If they don't pay, they just hit their expiration date and get suspended (staying at ₱0).

### 2. Fix the Payment Logic (The Double-Dip Bug)
Currently, if someone pays ₱2,000 on a ₱1,000 plan, they get 2 months of internet time. We need to decide how you want this handled. 

> [!IMPORTANT]
> **Open Question:** When a customer on a ₱1,000 plan pays ₱2,000, what should happen?
> 
> **Option A (Time-based):** The entire ₱2,000 is instantly converted into internet time (their expiration date extends by 2 months). Their "Advance Payment" balance remains ₱0 because they used all the money to buy time.
> 
> **Option B (Wallet-based, as you described):** ₱1,000 is used to extend their internet by 1 month. The remaining ₱1,000 is stored as "Advance Payment" (Wallet). *Note: If we choose this, we will need to build an automated background job that checks every day to see if they have enough Advance Payment to automatically buy another month when they expire.*

I strongly recommend **Option A** for simplicity, as it requires no automated monthly deduction scripts. The customer just buys time directly. If they pay ₱6,000 on a ₱1,000 plan, they instantly get 6 months of internet, and their balance is ₱0.

Please let me know if you prefer Option A or Option B, and I will implement the changes across all pages!
