"""Blue-green demo: one shop environment (blue or green) and the router."""

import http.client
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "deploy.json")

SAVED_CARDS = {"asha": "card-ending-4242"}


def load_manifest(path=MANIFEST):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def checkout(items, user=None, express=False):
    """Return the order total (100 per item)."""
    return {"total": 100 * items}


def as_json(payload):
    return json.dumps(payload).encode("utf-8")


def send(handler, status, body, served_by):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Served-By", served_by)
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(env_name, manifest_path):

    class Environment(BaseHTTPRequestHandler):

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)

            config = load_manifest(manifest_path)["environments"][env_name]
            flags = config.get("flags", {})

            try:
                if url.path == "/health":
                    send(
                        self, 200,
                        as_json({"status": "ok"}),
                        env_name
                    )

                elif url.path == "/info":
                    info = {
                        "env": env_name,
                        "version": config["version"],
                        "flags": flags
                    }
                    send(self, 200, as_json(info), env_name)

                elif url.path == "/checkout":
                    items = int(query.get("items", ["1"])[0])
                    user = query.get("user", [None])[0]

                    order = checkout(
                        items,
                        user,
                        flags.get("express_checkout", False)
                    )

                    send(self, 200, as_json(order), env_name)

                else:
                    send(
                        self, 404,
                        as_json({"error": "not found"}),
                        env_name
                    )

            except ValueError:
                send(
                    self, 400,
                    as_json({"error": "bad request"}),
                    env_name
                )

            except Exception as error:
                # Any other failure is reported as HTTP 500
                send(
                    self, 500,
                    as_json({"error": type(error).__name__}),
                    env_name
                )

        def log_message(self, *args):
            pass

    return Environment


def make_router_handler(manifest_path):

    class Router(BaseHTTPRequestHandler):

        def do_GET(self):
            manifest = load_manifest(manifest_path)
            live = manifest["live"]
            port = manifest["environments"][live]["port"]

            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", port, timeout=3
                )

                connection.request("GET", self.path)
                answer = connection.getresponse()

                status, body = answer.status, answer.read()
                connection.close()

            except OSError:
                status, body = 502, as_json(
                    {"error": "environment unreachable"}
                )

            send(self, status, body, live)

        def log_message(self, *args):
            pass

    return Router


def make_server(env_name, port=None, manifest_path=MANIFEST):

    if port is None:
        port = load_manifest(manifest_path)["environments"][env_name]["port"]

    return ThreadingHTTPServer(
        ("127.0.0.1", port),
        make_handler(env_name, manifest_path)
    )


def make_router(port, manifest_path=MANIFEST):

    return ThreadingHTTPServer(
        ("127.0.0.1", port),
        make_router_handler(manifest_path)
    )