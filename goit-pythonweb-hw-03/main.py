import json
import mimetypes
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
DATA_FILE = STORAGE_DIR / "data.json"
TEMPLATES_DIR = BASE_DIR / "templates"

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def ensure_storage() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("{}", encoding="utf-8")


def read_messages() -> dict:
    ensure_storage()
    try:
        payload = DATA_FILE.read_text(encoding="utf-8").strip() or "{}"
        data = json.loads(payload)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {}


def write_messages(messages: dict) -> None:
    ensure_storage()
    DATA_FILE.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/":
            self.send_html_file(BASE_DIR / "index.html")
        elif parsed_url.path == "/message.html":
            self.send_html_file(BASE_DIR / "message.html")
        elif parsed_url.path == "/read":
            self.send_read_page()
        elif parsed_url.path in {"/style.css", "/logo.png"}:
            self.send_static_file(BASE_DIR / parsed_url.path.lstrip("/"))
        else:
            self.send_html_file(BASE_DIR / "error.html", status=404)

    def do_POST(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/message":
            self.save_message()
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        self.send_html_file(BASE_DIR / "error.html", status=404)

    def save_message(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        parsed_body = parse_qs(body, keep_blank_values=True)

        message_data = {
            "username": parsed_body.get("username", [""])[0],
            "message": parsed_body.get("message", [""])[0],
        }

        messages = read_messages()
        messages[str(datetime.now())] = message_data
        write_messages(messages)

    def send_read_page(self) -> None:
        messages = read_messages()
        ordered_messages = list(reversed(messages.items()))

        template = jinja_env.get_template("read.html")
        content = template.render(messages=ordered_messages)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def send_html_file(self, file_path: Path, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        with file_path.open("rb") as fd:
            self.wfile.write(fd.read())

    def send_static_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_html_file(BASE_DIR / "error.html", status=404)
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.end_headers()

        with file_path.open("rb") as file:
            self.wfile.write(file.read())


def run(server_class=HTTPServer, handler_class=HttpHandler):
    server_address = ("", 3000)
    http = server_class(server_address, handler_class)
    try:
        print("Server started! On http://localhost:3000")
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http.server_close()


if __name__ == "__main__":
    ensure_storage()
    run()
