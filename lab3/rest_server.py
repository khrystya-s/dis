# -*- coding: utf-8 -*-
"""REST-сервер (FastAPI + Uvicorn). Запуск:  python rest_server.py --port 8000

Обчислення виконуються у ProcessPoolExecutor (як у ЛР №2), тому:
  * цикл подій не блокується, а два клієнти можуть рахувати одночасно;
  * serverComputeMs міряється всередині процесу-виконавця — лише математичне ядро.
"""
import argparse
import asyncio
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config
import service
from core import core_api

POOL = None
WORKERS = 2


class ComputeRequest(BaseModel):
    requestId: str = "req"
    variant: int = config.VARIANT
    n: int
    seed: int = config.SEED
    branch: str = "FULL"
    generateOnServer: bool = True
    blockBegin: int = 0
    blockEnd: int = 0
    returnValues: bool = True


@asynccontextmanager
async def lifespan(app):
    global POOL
    POOL = ProcessPoolExecutor(max_workers=WORKERS)
    yield
    POOL.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="LR3 compute service (REST)", lifespan=lifespan)


@app.get("/api/v1/health")
async def health():
    return {"status": "OK", "node": service.NODE}


@app.get("/api/v1/info")
async def info():
    return service.server_info(WORKERS)


async def _handle(req: ComputeRequest, request: Request, branch: str):
    client = request.client.host if request.client else "?"
    try:
        service.validate(req.variant, req.n, branch, req.blockBegin, req.blockEnd,
                         req.generateOnServer)
    except ValueError as e:
        service.log_request("rest", client, req.requestId, req.variant, req.n, branch,
                            0.0, "INVALID_ARGUMENT", service.now_iso(), service.now_iso())
        return JSONResponse(status_code=400, content={
            "requestId": req.requestId, "status": "INVALID_ARGUMENT", "message": str(e)})

    start_ts = service.now_iso()
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(
        POOL, core_api.execute, branch, req.n, req.seed,
        req.blockBegin, req.blockEnd, req.returnValues)
    end_ts = service.now_iso()
    service.log_request("rest", client, req.requestId, req.variant, req.n, branch,
                        res["compute_ms"], "OK", start_ts, end_ts)
    return JSONResponse(content={
        "requestId": req.requestId,
        "status": "OK",
        "resultKind": res["kind"],
        "rows": res["rows"],
        "cols": res["cols"],
        "checksum": res["checksum"],
        "serverComputeMs": res["compute_ms"],
        "serverNode": service.NODE,
        "values": res["values"],
    })


@app.post("/api/v1/compute")
async def compute(req: ComputeRequest, request: Request):
    return await _handle(req, request, "FULL")


@app.post("/api/v1/branch")
async def branch(req: ComputeRequest, request: Request):
    return await _handle(req, request, req.branch)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="LR3 REST server")
    ap.add_argument("--host", default=config.BIND)
    ap.add_argument("--port", type=int, default=config.REST_PORT)
    ap.add_argument("--workers", type=int, default=2, help="процесів-виконавців (ProcessPoolExecutor)")
    a = ap.parse_args()
    WORKERS = a.workers
    print("REST сервер: http://%s:%d  (вузол %s, workers=%d)" % (a.host, a.port, service.NODE, WORKERS))
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
