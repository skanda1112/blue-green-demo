import json
import re
import threading
from http.client import HTTPConnection

from app import checkout, load_manifest, make_server


def fetch(server, path):
    connection = HTTPConnection(
        "127.0.0.1",
        server.server_address[1],
        timeout=3
    )

    connection.request("GET", path)
    answer = connection.getresponse()

    return answer.status, json.loads(answer.read())


def test_standard_checkout():
    assert checkout(2) == {"total": 200}


def test_manifest_is_valid():
    manifest = load_manifest()

    assert manifest["live"] in manifest["environments"]

    for config in manifest["environments"].values():
        assert re.fullmatch(r"\d+\.\d+\.\d+", config["version"])


def test_every_environment_passes_the_smoke_test():
    manifest = load_manifest()

    for name, config in manifest["environments"].items():
        server = make_server(name, port=0)

        threading.Thread(
            target=server.serve_forever,
            daemon=True
        ).start()

        try:
            assert fetch(server, "/health") == (
                200,
                {"status": "ok"}
            )

            assert fetch(server, "/info")[1]["version"] == config["version"]

            status, order = fetch(
                server,
                "/checkout?items=2&user=asha"
            )

            assert status == 200 and order["total"] == 200

        finally:
            server.shutdown()
            server.server_close()