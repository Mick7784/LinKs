#!/usr/bin/env python3
"""Exercise the repository's Nginx config through real Traefik on loopback."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
NGINX = ROOT / "ops" / "nginx"
OVH = ROOT / "ops" / "ovh"
DESTINATION = "https://merchant.invalid/offer?tag=test-21&value=a%2Fb#details"
REDIRECT = "/go/st_fixture"
CLIENT_A, CLIENT_B, DIRECT = ("127.0.0.2", "127.0.0.3", "127.0.0.4")


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(204)
        # Test-only observation of what Traefik forwarded.
        self.send_header("X-Lab-Forwarded-For", self.headers.get("X-Forwarded-For", ""))
        self.end_headers()

    def do_GET(self):
        if self.path in (REDIRECT, "/abcd12345"):
            self.send_response(302)
            self.send_header("Location", DESTINATION)
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_response(200 if self.path == "/healthz" else 404)
        self.end_headers()


def ports():
    with socket.socket() as public, socket.socket() as edge, socket.socket() as traefik:
        for entry in (public, edge, traefik):
            entry.bind(("127.0.0.1", 0))
        return tuple(entry.getsockname()[1] for entry in (public, edge, traefik))


def fetch(port, path, client, forged=None, method=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=5, source_address=(client, 0))
    headers = {"Host": "links.lab.test"}
    if forged:
        headers.update({"X-Forwarded-For": forged, "X-Real-IP": forged,
                        "Forwarded": f"for={forged}"})
    try:
        method = method or ("POST" if path == "/metrics" else "GET")
        if method == "POST":
            headers["Content-Type"] = "application/json"
            connection.request("POST", path, '{"kind":"view"}', headers)
        else:
            connection.request("GET", path, headers=headers)
        with connection.getresponse() as response:
            response.read()
            return response.status, response.headers
    finally:
        connection.close()


@contextmanager
def process(command, directory, log):
    with (directory / log).open("wb") as output:
        child = subprocess.Popen(command, cwd=directory, stdout=output, stderr=subprocess.STDOUT,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            yield child
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def configure(directory, nginx_port, edge_port, traefik_port, upstream_port, edge):
    # Exercise the shipped policies. Adapt local paths and listener addresses.
    snippet_dir = directory / "links-metrics"
    snippet_dir.mkdir()
    (directory / "logs").mkdir()
    policy = OVH / "public-policy.conf.example" if edge else NGINX / "public-policy.conf"
    (snippet_dir / "public-policy.conf").write_bytes(policy.read_bytes())
    upstream = (NGINX / "upstream.conf").read_text(encoding="utf-8")
    (snippet_dir / "upstream.conf").write_text(upstream.replace("127.0.0.1:3003", f"127.0.0.1:{upstream_port}"))
    if edge:
        listener = (OVH / "edge-listener.conf.example").read_text(encoding="utf-8")
        listener = listener.replace("listen 8082;", f"listen 127.0.0.1:{edge_port};")
        listener = listener.replace("192.0.2.10/32", "127.0.0.1/32").replace("/etc/nginx/links-metrics/", "links-metrics/")
        (snippet_dir / "edge-listener.conf").write_text(listener, encoding="utf-8")
    config = (ROOT / "nginx.conf").read_text(encoding="utf-8")
    for source, target in {
        "worker_processes auto;": "worker_processes 1;",
        "/tmp/": "./", "/dev/stderr": "error.log", "/dev/stdout": "access.log",
        "include /etc/nginx/mime.types;": "types {}",
        "/usr/share/nginx/html": ".", "/data/public-fallback.json": "public-fallback.json",
        "/etc/nginx/links-metrics/": "links-metrics/",
        "listen 8080;": f"listen 127.0.0.1:{nginx_port};",
        "127.0.0.1:3003": f"127.0.0.1:{upstream_port}",
    }.items():
        config = config.replace(source, target)
    (directory / "nginx.conf").write_text(config, encoding="utf-8")
    (directory / "traefik.yml").write_text(f"""entryPoints:
  web:
    address: "127.0.0.1:{traefik_port}"
    forwardedHeaders:
      insecure: false
providers:
  file:
    directory: {json.dumps(directory.as_posix() + '/routes')}
""", encoding="utf-8")
    routes = directory / "routes"
    routes.mkdir()
    (routes / "public.yml").write_text(f"""http:
  routers:
    links:
      rule: "Host({chr(96)}links.lab.test{chr(96)})"
      entryPoints: [web]
      service: links
  services:
    links:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:{nginx_port}"
""", encoding="utf-8")
    if edge:
        route = (OVH / "traefik-metrics.yml.example").read_text(encoding="utf-8")
        route = route.replace("links.domotik-studio.fr", "links.lab.test").replace("websecure", "web")
        route = route.replace("      tls: {}\n", "").replace("192.0.2.20:8082", f"127.0.0.1:{edge_port}")
        (routes / "metrics.yml").write_text(route, encoding="utf-8")


def ready(port, children):
    last = None
    for _ in range(60):
        if any(child.poll() is not None for child in children):
            break
        try:
            last = fetch(port, "/healthz", CLIENT_A)[0]
            if last == 200:
                return
        except OSError as error:
            last = error
        time.sleep(0.1)
    raise AssertionError(f"Proxy ou Nginx indisponible - dernier résultat {last!r}, "
                         f"processus {[child.poll() for child in children]}")


def check(edge, nginx, traefik, directory, upstream_port):
    nginx_port, edge_port, traefik_port = ports()
    configure(directory, nginx_port, edge_port, traefik_port, upstream_port, edge)
    prefix = directory.as_posix() + "/"
    subprocess.run([nginx, "-t", "-p", prefix, "-c", "nginx.conf"], cwd=directory, check=True)
    nginx_command = [nginx, "-p", prefix, "-c", "nginx.conf", "-g", "daemon off; master_process off;"]
    with process(nginx_command, directory, "nginx.log") as n, process(
        [traefik, f"--configFile={directory.joinpath('traefik.yml').as_posix()}"], directory, "traefik.log"
    ) as t:
        ready(traefik_port, (n, t))
        for client in (CLIENT_A, CLIENT_B):
            status, headers = fetch(traefik_port, "/metrics", client, "198.51.100.1")
            assert status == 204 and headers.get_all("X-Lab-Forwarded-For") == [client]
        direct = fetch(nginx_port, "/metrics", DIRECT, CLIENT_A)[0]
        assert direct == (403 if edge else 204), direct
        if edge:
            assert fetch(edge_port, "/metrics", DIRECT, "127.0.0.1")[0] == 403
            assert fetch(edge_port, "/healthz", "127.0.0.1")[0] == 404
            assert fetch(nginx_port, "/metrics", "127.0.0.1")[0] == 403
            for path in ("/met%72ics", "//metrics", "/x/../metrics", "/metrics?fixture=1"):
                status, _ = fetch(nginx_port, path, DIRECT, CLIENT_B, method="POST")
                assert status in (400, 403, 404), (path, status)
        second = None
        with ThreadPoolExecutor(max_workers=12) as pool:
            jobs = {pool.submit(fetch, traefik_port, "/metrics", CLIENT_A, f"192.0.2.{i}") for i in range(1, 201)}
            counts = Counter()
            for job in as_completed(jobs):
                counts[job.result()[0]] += 1
                if counts[429] and second is None:
                    second = fetch(traefik_port, "/metrics", CLIENT_B, CLIENT_A)[0]
                    assert second == (204 if edge else 429), second
                    assert fetch(traefik_port, "/healthz", CLIENT_A)[0] == 200
                    assert fetch(traefik_port, "/nginx-healthz", CLIENT_A)[0] == 200
                    for path in (REDIRECT, "/abcd12345"):
                        status, headers = fetch(traefik_port, path, CLIENT_A)
                        assert status == 302 and headers.get_all("Location") == [DESTINATION]
                        assert headers.get_all("Referrer-Policy") == ["no-referrer"]
                        assert headers.get_all("Cache-Control") == ["no-store"]
                        assert headers.get_all("X-Content-Type-Options") == ["nosniff"]
                        assert len(headers.get_all("Content-Security-Policy")) == 1
            assert set(counts) == {204, 429}, counts
        print(f"{'Traefik' if edge else 'Nginx seul'} | A {dict(sorted(counts.items()))} | B {second}"
              f" | direct {direct} | santé 200 | redirections 302", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nginx", required=True, type=lambda path: str(Path(path).resolve(strict=True)))
    parser.add_argument("--traefik", required=True, type=lambda path: str(Path(path).resolve(strict=True)))
    parser.add_argument("--work-dir", type=Path, help="Parent directory for the temporary test fixture")
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="links-metrics-", dir=options.work_dir) as work, ThreadingHTTPServer(
        ("127.0.0.1", 0), Upstream
    ) as upstream:
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        try:
            for name, edge in (("baseline", False), ("edge", True)):
                directory = Path(work) / name
                directory.mkdir()
                try:
                    check(edge, options.nginx, options.traefik, directory, upstream.server_port)
                except Exception:
                    for log in ("nginx.log", "error.log", "traefik.log"):
                        path = directory / log
                        if path.exists():
                            print(path.read_text(errors="replace")[-3000:], flush=True)
                    raise
        finally:
            upstream.shutdown()
            thread.join()


if __name__ == "__main__":
    main()
