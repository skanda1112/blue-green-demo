"""Run and inspect the blue-green demo.

python demo.py up       start blue, green and the router (Ctrl+C stops)
python demo.py apply    deploy: copy deploy.json to the running environments
python demo.py probe    ask the router which environment is live
python demo.py traffic  send 6 shop requests through the router
python demo.py smoke green  health check and smoke test of one environment
"""

import http.client
import json
import os
import shutil
import sys
import threading
import time

from app import HERE, MANIFEST, load_manifest, make_router, make_server

ROUTER_PORT = 8080
DEPLOYED = os.path.join(HERE, ".deployed", "deploy.json")

SHOP_TRAFFIC = (
    ["/checkout?items=2&user=asha"] * 3
    + ["/checkout?items=2"] * 3
)


def get(port, path):
    connection = http.client.HTTPConnection(
        "127.0.0.1", port, timeout=3
    )

    try:
        connection.request("GET", path)
        answer = connection.getresponse()
        body = json.loads(answer.read() or b"{}")

        return (
            answer.status,
            body,
            answer.getheader("X-Served-By")
        )

    finally:
        connection.close()


def apply():
    os.makedirs(os.path.dirname(DEPLOYED), exist_ok=True)
    shutil.copyfile(MANIFEST, DEPLOYED)

    manifest = load_manifest(DEPLOYED)
    envs = manifest["environments"].items()

    versions = " ".join(
        f"{name}={cfg['version']}" for name, cfg in envs
    )

    print(
        f"Applied deploy.json: live={manifest['live']} {versions}",
        flush=True
    )

    return 0


def up():
    apply()
    manifest = load_manifest(DEPLOYED)

    servers = [make_router(ROUTER_PORT, DEPLOYED)]

    for name in manifest["environments"]:
        servers.append(
            make_server(name, manifest_path=DEPLOYED)
        )

    for server in servers:
        threading.Thread(
            target=server.serve_forever,
            daemon=True
        ).start()

    print(
        f"Router on http://127.0.0.1:{ROUTER_PORT} (Ctrl+C to stop)",
        flush=True
    )

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Stopped.")

    return 0


def probe():
    status, info, _ = get(ROUTER_PORT, "/info")

    if status != 200:
        print(f"Router answered HTTP {status}")
        return 1

    print(
        f"live: {info['env']} version {info['version']} "
        f"flags {info['flags']}"
    )

    return 0


def traffic():
    ok = errors = 0
    served = set()

    for path in SHOP_TRAFFIC:
        status, _, served_by = get(ROUTER_PORT, path)
        served.add(served_by)

        if status == 200:
            ok += 1
        else:
            errors += 1

    summary = (
        f"{ok} ok, {errors} errors "
        f"(served by: {', '.join(sorted(served))})"
    )

    print(
        f"{len(SHOP_TRAFFIC)} requests via router: {summary}"
    )

    return 0 if errors == 0 else 1


def smoke(name):
    config = load_manifest(DEPLOYED)["environments"][name]
    port = config["port"]

    problems = []

    if get(port, "/health")[0] != 200:
        problems.append("health check failed")

    if get(port, "/info")[1].get("version") != config["version"]:
        problems.append("wrong version")

    status, order, _ = get(
        port, "/checkout?items=2&user=asha"
    )

    if status != 200 or order.get("total") != 200:
        problems.append("checkout failed")

    if problems:
        print(
            f"SMOKE FAIL: {name}: " + "; ".join(problems)
        )
        return 1

    print(
        f"SMOKE PASS: {name} {config['version']} "
        f"flags {config.get('flags', {})}"
    )

    return 0


def main(argv):
    command = argv[1] if len(argv) > 1 else ""

    try:
        if command == "up":
            return up()

        if command == "apply":
            return apply()

        if command == "probe":
            return probe()

        if command == "traffic":
            return traffic()

        if command == "smoke" and len(argv) > 2:
            return smoke(argv[2])

    except OSError:
        print(
            "Cannot reach the demo. Start it first with: "
            "python demo.py up"
        )
        return 1

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))