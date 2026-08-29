# Functional Audit Fixes

- [x] `network_manager/services.py`: Fix auto-suspend race condition by using `.update(mac_address=mac)`.
- [x] `billing/signals.py`: Implement global `post_save` audit tracker for the `Customer` model.
- [x] `customer_portal/views.py`: Remove redundant Mikrotik API calls in `portal_process_mock_payment`.
