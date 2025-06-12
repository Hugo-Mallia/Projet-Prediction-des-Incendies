from fastapi import Request, Response
import logging

logger = logging.getLogger(__name__)

async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response: Response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

async def add_custom_header(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Custom-Header"] = "Value"
    return response

# Add more middleware functions as needed.

def setup_middleware(app):
    # Ajoute ici tes middlewares FastAPI si besoin
    pass