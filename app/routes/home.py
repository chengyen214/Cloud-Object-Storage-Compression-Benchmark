from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.storage import get_available_methods

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def home(request: Request):

    # 從 MinIO 自動取得壓縮方式
    methods = get_available_methods()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "methods": methods,
            "method_count": len(methods)
        }
    )