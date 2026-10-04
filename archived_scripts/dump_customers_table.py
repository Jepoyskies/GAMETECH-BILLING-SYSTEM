"""Print the actual My Customers table markup so the render can be eyeballed."""
import re

from django.contrib.auth import get_user_model
from django.test import Client

from billing.models import Agent

U = get_user_model()
martin = Agent.objects.get(user__username="Martin")

c = Client()
c.force_login(U.objects.get(username="Jep"))
html = c.get(f"/staff/agents/portal/{martin.id}/").content.decode()

# Isolate the My Customers card.
start = html.find("My Customers")
end = html.find("Payout History")
block = html[start - 400:end] if start != -1 else ""

rows = re.findall(r"<tr>(.*?)</tr>", block, re.S)
print("=" * 74)
print(f"My Customers table -- {len(rows)} <tr> found")
print("=" * 74)
for i, r in enumerate(rows):
    cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)

    def clean(x):
        x = re.sub(r"<[^>]+>", " ", x)
        return re.sub(r"\s+", " ", x).strip()

    cells = [clean(x) for x in cells]
    if not any(cells):
        continue
    print(f"\nrow {i}:")
    for cell in cells:
        if cell:
            print(f"   - {cell[:90]}")

print()
print("=" * 74)
for probe in ("Juan Dela Cruz", "Awaiting install", "Unpaid", "No expiry set",
              "Not dispatched yet", "Customer", "Technician / Job",
              "Next Expiry", "Balance"):
    print(f"  {'FOUND  ' if probe in html else 'MISSING'} {probe}")
print("=" * 74)
print(f"raw template text leaked into the page: "
      f"{'{#' in html or '%}' in html}")
print("=" * 74)
