import sys
import traceback

# Test all major URL imports
errors = []

try:
    from billing import urls as billing_urls
    print("billing.urls: OK")
except Exception as e:
    errors.append(f"billing.urls: {e}")
    print(f"billing.urls ERROR: {e}")

try:
    from customer_portal import urls as portal_urls
    print("customer_portal.urls: OK")
except Exception as e:
    errors.append(f"customer_portal.urls: {e}")
    print(f"customer_portal.urls ERROR: {e}")

try:
    from network_manager import urls as nm_urls
    print("network_manager.urls: OK")
except Exception as e:
    errors.append(f"network_manager.urls: {e}")
    print(f"network_manager.urls ERROR: {e}")

try:
    from dispatch import urls as dispatch_urls
    print("dispatch.urls: OK")
except Exception as e:
    errors.append(f"dispatch.urls: {e}")
    print(f"dispatch.urls ERROR: {e}")

# Test views
try:
    from billing import views as billing_views
    print("billing.views: OK")
except Exception as e:
    errors.append(f"billing.views: {e}")
    print(f"billing.views ERROR: {e}")
    traceback.print_exc()

try:
    from customer_portal import views as portal_views
    print("customer_portal.views: OK")
except Exception as e:
    errors.append(f"customer_portal.views: {e}")
    print(f"customer_portal.views ERROR: {e}")
    traceback.print_exc()

try:
    from network_manager import views as nm_views
    print("network_manager.views: OK")
except Exception as e:
    errors.append(f"network_manager.views: {e}")
    print(f"network_manager.views ERROR: {e}")
    traceback.print_exc()

# Test analytics view specifically
try:
    from billing.views.analytics import analytics_view
    print("billing.views.analytics: OK")
except Exception as e:
    errors.append(f"billing.views.analytics: {e}")
    print(f"billing.views.analytics ERROR: {e}")
    traceback.print_exc()

try:
    from billing.views.xendit import xendit_webhook
    print("billing.views.xendit: OK")
except Exception as e:
    errors.append(f"billing.views.xendit: {e}")
    print(f"billing.views.xendit ERROR: {e}")
    traceback.print_exc()

print("\n=== SUMMARY ===")
if errors:
    print(f"ERRORS ({len(errors)}):")
    for err in errors:
        print(f"  - {err}")
else:
    print("All imports OK!")
