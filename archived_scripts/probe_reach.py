import socket

targets = [
    ("ccr2116.v2 - uptown", "172.30.120.2"),
    ("ccr2116.v1 - patag", "172.30.120.1"),
    ("ccr2116.v3 - patag_carmen", "172.30.120.3"),
    ("Mikrotik A", "192.168.88.2"),
]
PORTS = [8728, 8729, 700, 8700]

print("=== TCP reachability from the web container ===")
for name, ip in targets:
    results = []
    for p in PORTS:
        s = socket.socket()
        s.settimeout(2.0)
        try:
            s.connect((ip, p))
            results.append("{}:OPEN".format(p))
        except socket.timeout:
            results.append("{}:timeout".format(p))
        except OSError as e:
            results.append("{}:{}".format(p, e.__class__.__name__))
        finally:
            s.close()
    print("{} {} -> {}".format(name.ljust(24), ip.ljust(15), "  ".join(results)))