#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from build_css import build_css

if __name__ == "__main__":
    import uvicorn

    build_css()

    host = settings.HOST
    port = settings.PORT

    print(f"Starting Paragonka CRM in development mode on {host}:{port}")
    print("Hot reload enabled")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="debug",
        access_log=True,
    )
