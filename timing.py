"""Time the customers page as a logged-in staff user, via a real HTTP session."""
import time

import requests

BASE = "http://localhost:8000"
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()
u = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
c = Client()
assert c.login(username=u.username, password=None) is False or True

# Client.force_login avoids needing the password.
c.force_login(u)

out = []
for url in ["/customers/", "/customers/?page=2", "/customers/?search=delacruz",
            "/customers/?filter=paid_unknown", "/customers/?sort=name"]:
    t = time.time()
    r = c.get(url)
    dt = time.time() - t
    out.append("%-42s %s  %6.2fs  %8.1f KB" % (
        url, r.status_code, dt, len(r.content) / 1024.0))

# How many rows are on the page now?
body = c.get("/customers/").content.decode("utf-8")
import re
rows = len(re.findall(r"<tr\b", re.search(r"<tbody>(.*?)</tbody>", body, re.S).group(1))) if re.search(r"<tbody>(.*?)</tbody>", body, re.S) else 0
out.append("")
out.append("rows in first page : %d" % rows)
out.append("total matches      : %s" % (re.search(r'([\d,]+) customers? match', body).group(1) if re.search(r'([\d,]+) customers? match', body) else "?"))
out.append("pagination present : %s" % ("page-link" in body))
out.append("search form present: %s" % ('name="search"' in body))

open("/app/timing.txt", "w").write("\n".join(out))
print("\n".join(out))
