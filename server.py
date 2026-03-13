#!/usr/bin/env python3
import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent
WEB = ROOT / "web"
DATA = ROOT / "data" / "knowledge.json"

DEFAULT_DATA = {
    "documents": [
        {
            "id": "doc-001",
            "title": "Pricing Model 2025",
            "department": "Sales",
            "access": ["employee", "management"],
            "updated_at": "2026-01-05",
            "content": "Our pricing model includes Starter, Growth, and Enterprise tiers with annual discount options."
        },
        {
            "id": "doc-002",
            "title": "Client Onboarding SOP",
            "department": "Operations",
            "access": ["employee"],
            "updated_at": "2026-02-16",
            "content": "Onboarding includes kickoff, stakeholder mapping, implementation planning, and 30-day review."
        },
        {
            "id": "doc-003",
            "title": "HR Vacation Policy",
            "department": "HR",
            "access": ["hr", "employee"],
            "updated_at": "2026-01-22",
            "content": "Employees receive 20 PTO days annually, plus local public holidays, with manager approval workflow."
        },
        {
            "id": "doc-004",
            "title": "Quarterly Research Brief",
            "department": "Research",
            "access": ["employee", "management"],
            "updated_at": "2026-03-01",
            "content": "Latest research highlights growth in AI-assisted workflows and strong demand in regulated industries."
        }
    ],
    "logs": []
}


def ensure_data_file():
    DATA.parent.mkdir(parents=True, exist_ok=True)
    if not DATA.exists():
        DATA.write_text(json.dumps(DEFAULT_DATA, indent=2), encoding="utf-8")


def load_data():
    ensure_data_file()
    return json.loads(DATA.read_text(encoding="utf-8"))


def save_data(data):
    DATA.write_text(json.dumps(data, indent=2), encoding="utf-8")


def json_response(handler, status, payload):
    content = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def retrieve_docs(query, role, docs):
    nq = normalize(query)
    if not nq:
        return []
    tokens = [t for t in re.split(r"[^a-z0-9]+", nq) if t]
    scored = []
    for doc in docs:
        if role not in doc.get("access", []):
            continue
        haystack = normalize(f"{doc['title']} {doc['department']} {doc['content']}")
        score = sum(2 if t in normalize(doc["title"]) else 1 for t in tokens if t in haystack)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:3]]


def make_answer(query, role, docs):
    hits = retrieve_docs(query, role, docs)
    if not hits:
        return {
            "answer": "I couldn't find matching authorized knowledge for that query.",
            "supporting_points": ["Try rephrasing with document title, team, or policy name."],
            "citations": [],
            "confidence": 0.25,
        }

    supporting = [f"{d['title']}: {d['content']}" for d in hits]
    citations = [
        {
            "source_title": d["title"],
            "section": d["department"],
            "last_updated": d["updated_at"],
            "doc_id": d["id"],
        }
        for d in hits
    ]
    answer = f"Based on {len(hits)} internal source(s), here is what I found: {hits[0]['content']}"
    return {
        "answer": answer,
        "supporting_points": supporting,
        "citations": citations,
        "confidence": 0.8 if len(hits) > 1 else 0.65,
    }


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _serve_static(self, path):
        file_path = WEB / path.lstrip("/")
        if path == "/":
            file_path = WEB / "index.html"
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not found")
            return
        mime = "text/plain"
        if file_path.suffix == ".html":
            mime = "text/html"
        elif file_path.suffix == ".css":
            mime = "text/css"
        elif file_path.suffix == ".js":
            mime = "application/javascript"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/preview-link":
            host = self.headers.get("Host", "localhost:8000")
            proto = "https" if self.headers.get("X-Forwarded-Proto") == "https" else "http"
            return json_response(self, 200, {"preview_url": f"{proto}://{host}/"})
        if parsed.path.startswith("/api/admin/docs"):
            data = load_data()
            return json_response(self, 200, {"documents": data["documents"]})
        if parsed.path.startswith("/api/admin/logs"):
            data = load_data()
            return json_response(self, 200, {"logs": data["logs"][-50:]})
        return self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/chat":
            body = self._read_json()
            query = body.get("query", "")
            role = body.get("role", "employee")
            data = load_data()
            result = make_answer(query, role, data["documents"])
            data["logs"].append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "role": role,
                "query": query,
                "citations": [c["doc_id"] for c in result["citations"]],
                "confidence": result["confidence"],
            })
            save_data(data)
            return json_response(self, 200, result)

        if parsed.path == "/api/admin/docs":
            body = self._read_json()
            data = load_data()
            docs = data["documents"]
            doc_id = body.get("id")
            now = datetime.utcnow().date().isoformat()
            if doc_id:
                for doc in docs:
                    if doc["id"] == doc_id:
                        doc.update({
                            "title": body.get("title", doc["title"]),
                            "department": body.get("department", doc["department"]),
                            "access": body.get("access", doc["access"]),
                            "content": body.get("content", doc["content"]),
                            "updated_at": now,
                        })
                        save_data(data)
                        return json_response(self, 200, {"status": "updated", "doc": doc})
            new_doc = {
                "id": f"doc-{len(docs)+1:03d}",
                "title": body.get("title", "Untitled"),
                "department": body.get("department", "General"),
                "access": body.get("access", ["employee"]),
                "content": body.get("content", ""),
                "updated_at": now,
            }
            docs.append(new_doc)
            save_data(data)
            return json_response(self, 201, {"status": "created", "doc": new_doc})

        self.send_error(404, "Unknown endpoint")


def run():
    ensure_data_file()
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Server running on http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
