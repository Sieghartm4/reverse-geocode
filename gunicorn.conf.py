# gunicorn.conf.py
# Run with: gunicorn -c gunicorn.conf.py app:app

import multiprocessing
import os

# ── Workers ───────────────────────────────────────────────────────────────────
# gevent workers handle many concurrent I/O-bound requests per worker
worker_class       = "gevent"
worker_connections = 100                            # concurrent greenlets per worker
workers            = multiprocessing.cpu_count() * 2 + 1  # e.g. 4-core → 9 workers

# ── Binding ───────────────────────────────────────────────────────────────────
host = os.environ.get("FLASK_HOST", "0.0.0.0")
port = os.environ.get("FLASK_PORT", "5111")
bind = f"{host}:{port}"

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout           = 30    # kill worker if a request takes longer than 30 s
graceful_timeout  = 10    # seconds to finish in-flight requests on SIGTERM
keepalive         = 5     # keep connection alive for 5 s after response

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog  = "-"    # stdout
errorlog   = "-"    # stderr
loglevel   = "info"

# ── Process name ─────────────────────────────────────────────────────────────
proc_name = "reverse_geocoder"

# ── DB Pool sizing note ───────────────────────────────────────────────────────
# Each worker opens up to DB_POOL_MAX connections.
# Total max DB connections = workers * DB_POOL_MAX
# Make sure this stays under PostgreSQL's max_connections (default 100).
# With 9 workers and DB_POOL_MAX=5:  9 * 5 = 45 connections  ✓
# Adjust DB_POOL_MAX in .env accordingly.