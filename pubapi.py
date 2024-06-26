import uvicorn
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from pydantic import BaseModel
from glob import glob
from pathlib import Path

ABSOLUTE_PATH = "/var/www/aaaa/"

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(root_path="/api/public")

app.state.limiter = limiter
app.add_exception_handler(HTTPException, _rate_limit_exceeded_handler)

origins = [
    "http://lobadk.com",
    "https://lobadk.com",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

extensions = (
    "jpg",
    "jpeg",
    "png",
    "webp",
    "mp4",
    "gif",
    "mov",
    "mp3",
    "webm",
)


class Search(BaseModel):
    search: str


class SearchResponse(BaseModel):
    files: list[str]
    count: int


class AppendSearch(Search):
    pass


class AppendSearchResponse(BaseModel):
    file: str


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.get("/aaaasearch/", response_model=SearchResponse)
@limiter.limit("10/minute")
async def aaaasearch(request: Request, search: Search = Depends(Search)):
    try:
        files = glob(f"{ABSOLUTE_PATH}*")
        files = [str(Path(file).name) for file in files if search.search in file]
        if len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No files found"
            )
        return {
            "files": files,
            "count": len(files),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/a/", response_model=AppendSearchResponse)
@limiter.limit("10/minute")
async def a(request: Request, search: AppendSearch = Depends(AppendSearch)):
    try:
        files = glob(f"{ABSOLUTE_PATH}*")
        files = [str(Path(file).name) for file in files if search.search in file]
        if len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No files found"
            )
        if len(files) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Too many files found"
            )
        return {
            "file": files[0],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


def start_api():
    uvicorn.run(app, host="127.0.0.1", port=8000)
