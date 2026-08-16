# GameTech Unli Fiber: MikroTik Production Setup Guide

Before connecting a new production router to the Django Billing System, run the following commands in the MikroTik terminal to establish a secure API connection. **Do not use the default admin account for Django.**

### Step 1: Enable the API Service
`/ip service set api disabled=no`

### Step 2: Create a Secure API Group
Create a dedicated permissions group that allows full read/write via the API, but explicitly blocks WinBox, WebUI, SSH, and Reboot privileges to protect the core router.
`/user group add name=api_group policy=api,read,write,test,!local,!telnet,!ssh,!ftp,!reboot,!policy,!password,!web,!sniff,!romon,!rest-api`

### Step 3: Create the Dedicated Django Robot User
Create the actual user account that Django will use to log in. (Ensure you change the password below to a secure production password and update your Django `.env` variables accordingly).
`/user add name=django_billing group=api_group password="SecurePassword123" comment="Used by Django Billing System"`

### Step 4: (Optional) Lock Down the API to the Django Server IP
For ultimate security, restrict the API service so it only accepts connections from the Django server's specific IP address. (Replace `192.168.X.X` with the actual IP).
`/ip service set api address=192.168.X.X/32`

---
**Note on RouterOS Versions:** 
The Django suspension logic utilizes an L2 PADI drop via `/interface bridge filter`. On RouterOS v7, this strictly requires a MAC mask. The system will inject the rule as `src-mac-address=MAC/FF:FF:FF:FF:FF:FF`. If migrating to an older RouterOS v6 router, perform a manual test in WinBox to ensure it accepts the `/FF:FF:FF:FF:FF:FF` mask syntax without throwing an error.
