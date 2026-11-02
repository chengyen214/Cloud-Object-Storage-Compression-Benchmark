from fastapi import FastAPI
from app.routes import home, methods, files

app = FastAPI(
    title="Cloud Object Storage Compression Benchmark"
)

app.include_router(home.router)
app.include_router(methods.router)
app.include_router(files.router)