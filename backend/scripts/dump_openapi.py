"""Write the API's OpenAPI schema (app.openapi(), in process: the HTTP route needs a signed-in caller).

Usage (from backend/): python scripts/dump_openapi.py PATH
The dashboard's types are generated from it (make api-types), and make check fails when they are stale.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("AIMAIL_ENV_FILE", "")  # the schema must not depend on anyone's .env
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
