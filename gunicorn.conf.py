# Gunicorn configuration optimized for low memory usage
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5003"
backlog = 2048

# Worker processes - REDUCED for low memory
workers = 1  # Start with just 1 worker
worker_class = "sync"  # Use sync worker instead of gevent to reduce memory
worker_connections = 1000
max_requests = 100  # Restart workers after 100 requests to prevent memory leaks
max_requests_jitter = 10  # Add jitter to prevent all workers restarting at once

# Worker timeout
timeout = 120  # Increased timeout for AI operations
keepalive = 2
graceful_timeout = 30

# Memory management
preload_app = False  # Don't preload app to save memory
max_worker_memory = 200  # Kill worker if it uses more than 200MB (adjust as needed)

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" %(D)s'

# Process naming
proc_name = "blogcreator"

# Enable worker process memory monitoring
def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal"""
    import gc
    gc.collect()

def post_worker_init(worker):
    """Called after a worker has been initialized"""
    import gc
    gc.set_threshold(700, 10, 10)  # More aggressive garbage collection

def when_ready(server):
    """Called when the server is ready to serve requests"""
    server.log.info("Server is ready. Spawning workers")

def child_exit(server, worker):
    """Called when a worker exits"""
    import gc
    gc.collect()
    server.log.info("Worker %s exited", worker.pid)

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
