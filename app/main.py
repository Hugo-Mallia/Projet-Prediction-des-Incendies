from fastapi import FastAPI
from app.api.endpoints import router as api_router
from app.api.middleware import setup_middleware
from app.core.logging import setup_logging
from app.interface.gradio_app import create_gradio_interface

app = FastAPI(title="Flaméo - Expert IA en Sécurité Incendie")

# Setup logging
setup_logging()

# Setup middleware
setup_middleware(app)

# Include API routers
app.include_router(api_router, prefix="/api")

# Mount static files and other configurations can be added here

# Initialize Gradio interface
gradio_app = create_gradio_interface()

# Mount Gradio app
app.mount("/audit", gradio_app)