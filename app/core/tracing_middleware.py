import time

from fastapi import Request
from firebase_admin import auth
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP request count",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "path"],
)


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        if request.scope.get("type") == "websocket":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                decoded = auth.verify_id_token(auth_header[7:])
                request.state.user_id = decoded.get("uid")
            except Exception:
                request.state.user_id = None
        else:
            request.state.user_id = None

        method = request.method
        raw_path = request.url.path

        http_requests_in_progress.labels(method=method, path=raw_path).inc()
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        status_code = str(response.status_code)

        route = request.scope.get("route")
        path_label = route.path if route else "<unknown>"

        http_requests_in_progress.labels(method=method, path=raw_path).dec()
        http_requests_total.labels(
            method=method, path=path_label, status_code=status_code
        ).inc()
        http_request_duration_seconds.labels(method=method, path=path_label).observe(
            duration
        )

        return response
