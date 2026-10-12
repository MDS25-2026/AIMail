"""The API and the worker in one process, for a host that allows one small service (free-hosting.md).

Separate processes stay the default (make dev, the Docker image). Render's free tier gives 512 MB to one
web service, and two Python processes importing the same code would spend it twice.
"""

import asyncio
import os

import uvicorn

from app import worker
from app.main import app

# Inside the container every interface is the container's own; Render routes $PORT to it.
ALL_INTERFACES = "0.0.0.0"


async def run() -> None:
    stop = asyncio.Event()
    jobs = asyncio.create_task(worker.run_until(stop))
    server = uvicorn.Server(uvicorn.Config(app, host=ALL_INTERFACES, port=int(os.environ["PORT"]),
                                           access_log=False))
    # uvicorn handles SIGTERM: serve() returns once requests drain, then the worker stops the same way.
    await server.serve()
    stop.set()
    await jobs


if __name__ == "__main__":
    asyncio.run(run())
