"""The API and the worker in one process, for a host that allows one small service (free-hosting.md).

Separate processes stay the default (make dev, the Docker image). Render's free tier gives 512 MB to one
web service, and two Python processes importing the same code would spend it twice.
"""

import asyncio
import os

import uvicorn

from app import worker
from app.events import events
from app.main import app

# Inside the container every interface is the container's own; Render routes $PORT to it.
ALL_INTERFACES = "0.0.0.0"
EXIT_POLL_SECONDS = 0.5


async def end_streams_on_exit(server: uvicorn.Server) -> None:
    """uvicorn drains open requests before it stops; an event stream never ends by itself, so it is ended here."""
    while not server.should_exit:
        await asyncio.sleep(EXIT_POLL_SECONDS)
    events.end_streams()


async def run() -> None:
    stop = asyncio.Event()
    jobs = asyncio.create_task(worker.run_until(stop))
    server = uvicorn.Server(uvicorn.Config(app, host=ALL_INTERFACES, port=int(os.environ["PORT"]),
                                           access_log=False))
    asyncio.create_task(end_streams_on_exit(server))
    # uvicorn handles SIGTERM: serve() returns once requests drain, then the worker stops the same way.
    await server.serve()
    stop.set()
    await jobs


if __name__ == "__main__":
    asyncio.run(run())
