from fastapi import FastAPI
from app.routes import home, methods

app = FastAPI(
    title="Cloud Object Storage Compression Benchmark"
)

app.include_router(home.router)
app.include_router(methods.router)