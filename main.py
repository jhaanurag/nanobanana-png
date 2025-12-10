from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
import os
import io
import base64
import json
import traceback
from PIL import Image
import google.generativeai as genai

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


def _extract_b64(obj):
    """Recursively walk an object (dict/list) looking for base64 image content.
    Accepts dicts, lists, objects with __dict__ and strings; returns first found string.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('b64_json', 'b64', 'base64') and isinstance(v, str):
                return v
            res = _extract_b64(v)
            if res:
                return res
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            res = _extract_b64(v)
            if res:
                return res
    elif hasattr(obj, '__dict__'):
        return _extract_b64(vars(obj))
    elif isinstance(obj, str):
        # crude heuristic: long base64 string with +/ and = padding
        if len(obj) > 100 and any(c in obj for c in ['+', '/', '=']):
            return obj
    return None


def remove_green_screen_from_bytes(img_bytes, g_threshold=120, diff_threshold=30):
    """Remove green screen by converting green pixels to transparent.
    - g_threshold: minimum G value to be considered green
    - diff_threshold: minimum difference between G and max(R,B)
    """
    with Image.open(io.BytesIO(img_bytes)) as im:
        im = im.convert('RGBA')
        w, h = im.size
        pixels = im.load()
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if g >= g_threshold and (g - max(r, b)) >= diff_threshold:
                    pixels[x, y] = (r, g, b, 0)
        out_buf = io.BytesIO()
        im.save(out_buf, format='PNG')
        out_buf.seek(0)
        return out_buf


@app.post('/generate')
async def generate_image(request: Request):
    """Generate an image using Gemini image model with a green-screen background, then remove the green background and return a transparent PNG.

    Accepts JSON body: { "prompt": "text" }
    Returns: image/png (PNG with transparency)
    """
    data = await request.json()
    prompt = (data or {}).get('prompt')
    if not prompt:
        raise HTTPException(status_code=400, detail='prompt is required')

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail='GEMINI_API_KEY not configured')

    # configure the official SDK client
    try:
        genai.configure(api_key=api_key)
    except Exception:
        # some versions expose a different function
        pass

    system_instruction = (
        'Create an image containing the subject described in the prompt. Use a solid green screen background (pure green, hex #00FF00) so the background can be removed easily. ' 
        'Ensure the subject is in focus and there is clear contrast between subject and background. Return a single PNG image.'
    )
    combined_prompt = f"{system_instruction}\n\nPrompt: {prompt}"

    try:
        # Try a couple of common SDK call signatures to locate the image bytes
        resp = None
        image_b64 = None
        try:
            # common pattern: genai.images.generate
            if hasattr(genai, 'images') and hasattr(genai.images, 'generate'):
                resp = genai.images.generate(model='gemini-2.5-flash-image', prompt=combined_prompt)
            elif hasattr(genai, 'generate_image'):
                resp = genai.generate_image(model='gemini-2.5-flash-image', prompt=combined_prompt)
            elif hasattr(genai, 'Image') and hasattr(genai.Image, 'generate'):
                resp = genai.Image.generate(model='gemini-2.5-flash-image', prompt=combined_prompt)
            else:
                # try top-level generate call
                resp = genai.generate(model='gemini-2.5-flash-image', prompt=combined_prompt)
        except Exception:
            # try fallback: some SDK versions use a different call signature
            resp = genai.generate_image(model='gemini-2.5-flash-image', prompt=combined_prompt)

        # extract base64 from response
        image_b64 = _extract_b64(resp)
        if not image_b64:
            # try converting to JSON
            try:
                resp_json = json.loads(json.dumps(resp, default=lambda o: getattr(o, '__dict__', str(o))))
                image_b64 = _extract_b64(resp_json)
            except Exception:
                pass

        if not image_b64:
            # If we don't have b64, raise error with raw repr of resp
            raise ValueError('Could not locate base64 image in SDK response')

        # decode bytes
        image_bytes = base64.b64decode(image_b64)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'Image generation failed: {exc}')

    # Remove green screen
    try:
        out_buf = remove_green_screen_from_bytes(image_bytes)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'Failed to process image: {exc}')

    return StreamingResponse(out_buf, media_type='image/png')
