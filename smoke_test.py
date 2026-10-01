"""Full-site smoke test: hit every GET-able URL as a staff user, report 500s.

Run inside the container. Writes results to /app/smoke.txt.
"""
import re
import traceback

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import URLPattern, URLResolver, get_resolver

from django.http import Http404, HttpResponse

User = get_user_model()
rf = RequestFactory()
user = User.objects.filter(is_staff=True).order_by("-id").first()
superuser = User.objects.filter(is_superuser=True).first() or user


def walk(resolver, prefix="", depth=0, out=None):
    if out is None:
        out = []
    if depth > 6:
        return out
    for p in resolver.url_patterns:
        if isinstance(p, URLResolver):
            walk(p, prefix + str(p.pattern), depth + 1, out)
        elif isinstance(p, URLPattern):
            out.append((prefix + str(p.pattern), p))
    return out


# Values substituted for the converter args so we hit a real code path.
SAMPLES = {
    "int": "1",
    "str": "test",
    "slug": "test",
    "uuid": "00000000-0000-0000-0000-000000000000",
    "path": "test",
}


def build(pattern):
    """Return (concrete_url, arg_count) or (None, 0) if it needs an arg we don't have."""
    pat = pattern
    n = 0
    def sub(m):
        nonlocal n
        conv, name = m.group(1) or "", m.group(2)
        n += 1
        return "/" + SAMPLES.get(conv, "1")
    pat = re.sub(r"<([^:>]+):([^>]+)>", sub, pat)
    pat = re.sub(r"<([^>]+)>", lambda m: "/" + SAMPLES.get(m.group(1).split(":")[0], "1"), pat)
    if "(" in pat:      # regex routes, skip
        return None, 0
    if not pat.startswith("/"):
        pat = "/" + pat
    return pat, n


results = []
patterns = walk(get_resolver())
seen = set()

for pat, p in patterns:
    url, nargs = build(pat)
    if url is None or url in seen:
        continue
    seen.add(url)

    # Only GET routes without required kwargs we couldn't fill.
    if getattr(p.callback, "methods", None) and "GET" not in p.callback.methods:
        continue
    if nargs == 0 and pat.endswith("/") is False and "<" not in pat:
        pass

    req = rf.get(url)
    req.user = superuser
    try:
        resp = p.callback(req, **{}) if nargs == 0 else None
        if resp is None:
            # needs an arg -> resolve real object ids per view is hard; skip
            results.append(("SKIP", url, "needs arg"))
            continue
        code = resp.status_code
        body = ""
        if hasattr(resp, "content"):
            try:
                body = resp.content.decode("utf-8", "ignore")
            except Exception:
                body = ""
        results.append((str(code), url, ""))
    except Http404 as e:
        results.append(("404", url, str(e)[:60]))
    except Exception as e:
        results.append(("EXC", url, "%s: %s" % (type(e).__name__, str(e)[:110])))

lines = ["SMOKE TEST - %d urls" % len(results), ""]
bad = 0
for code, url, note in sorted(results, key=lambda x: (x[0] not in ("200", "302", "SKIP"), x[0])):
    flag = ""
    if code in ("500", "EXC"):
        flag = "  <<<<<< PROBLEM"
        bad += 1
    lines.append("  %-6s %-70s %s%s" % (code, url[:70], note[:70], flag))

lines.append("")
lines.append("TOTAL=%d  PROBLEMS=%d" % (len(results), bad))
open("/app/smoke.txt", "w").write("\n".join(lines))
print("PROBLEMS=%d of %d" % (bad, len(results)))
