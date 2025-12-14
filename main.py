from fastapi import FastAPI
from fastapi.responses import FileResponse
import os

app = FastAPI()


@app.get("/hello")
async def hello():
    """Return a simple hello world message.

    This endpoint responds with a small JSON message to verify the FastAPI app is running.
    """
    return {"message": "hello world"}


@app.get('/')
async def index():
    """Return the simple HTML page that fetches `/hello`.

    Serving from the same origin avoids CORS issues when the HTML uses a relative fetch.
    """
    here = os.path.dirname(__file__)
    return FileResponse(os.path.join(here, 'index.html'))
