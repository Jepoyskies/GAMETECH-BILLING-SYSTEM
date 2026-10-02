"""Dump the rendered HTML of the first table row to find the bloat."""
import re

from django.contrib.auth import get_user_model
from django.test import RequestFactory

from billing.views.customers.list import customer_list

User = get_user_model()
rf = RequestFactory()
su = User.objects.filter(is_superuser=True).first()

req = rf.get("/customers/")
req.user = su
html = customer_list(req).content.decode("utf-8")

# Isolate the first <tr>...</tr> inside the customer table body.
m = re.search(r'<tbody>(.*?)</tbody>', html, re.S)
body = m.group(1) if m else ""
rows = re.findall(r'<tr\b.*?</tr>', body, re.S)
out = ["rows rendered      : %d" % len(rows),
       "body size          : %.2f MB" % (len(body) / 1048576.0)]
if rows:
    r0 = rows[0]
    out.append("first row bytes    : %d" % len(r0))
    out.append("avg row bytes      : %d" % (len(body) // max(len(rows), 1)))
    out.append("")
    out.append("--- per-attribute / per-tag contribution in row 0 ---")
    # biggest attributes
    attrs = re.findall(r'(\w[\w-]*)="([^"]*)"', r0)
    agg = {}
    for k, v in attrs:
        agg[k] = agg.get(k, 0) + len(k) + len(v) + 4
    for k, n in sorted(agg.items(), key=lambda x: -x[1])[:14]:
        out.append("   %-24s %6d bytes" % (k, n))
    out.append("")
    out.append("--- count of repeated class names ---")
    cls = re.findall(r'class="([^"]*)"', r0)
    cagg = {}
    for c in cls:
        for tok in c.split():
            cagg[tok] = cagg.get(tok, 0) + 1
    for k, n in sorted(cagg.items(), key=lambda x: -x[1])[:14]:
        out.append("   %-30s x%d" % (k, n))
    out.append("")
    out.append("--- first 1200 chars of row 0 ---")
    out.append(r0[:1200])

open("/app/rowprobe.txt", "w").write("\n".join(out))
print("rows=%d first_row=%d" % (len(rows), len(rows[0]) if rows else 0))
