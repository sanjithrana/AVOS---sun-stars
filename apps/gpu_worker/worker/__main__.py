"""python -m worker  →  the AVOS GPU worker on WORKER_PORT (default 8700)."""
import uvicorn

from worker import config

if __name__ == "__main__":
    uvicorn.run("worker.app:app", host=config.HOST, port=config.PORT, log_level="info")
