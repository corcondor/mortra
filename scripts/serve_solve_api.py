"""Serve the Vercel Python solve function during local Next.js development."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from api.solve import handler


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8766), handler)
    print("MORTRA solve API ready at http://127.0.0.1:8766/api/solve", flush=True)
    server.serve_forever()
