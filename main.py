from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
import os
from dotenv import load_dotenv

from google import genai
from google.genai import types

# Load environment variables
load_dotenv()
client = None
try:
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
except Exception:
    client = None
import io
import base64
import json
import traceback
from PIL import Image, ImageDraw

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

    # If developer wants a mock generation mode (no real API or quota), use 'mock' key
    if api_key == 'mock':
        def _mock_generate(prompt_text: str) -> bytes:
            # Create a simple PNG with a green background and a yellow banana-like shape
            w, h = 640, 480
            img = Image.new('RGBA', (w, h), (0, 255, 0, 255))
            draw = ImageDraw.Draw(img)
            # draw a banana-like ellipse
            draw.ellipse([(w*0.25, h*0.35), (w*0.75, h*0.65)], fill=(255, 225, 25, 255))
            # add a little black outline
            draw.arc([(w*0.25, h*0.35), (w*0.75, h*0.65)], start=20, end=160, fill=(0,0,0), width=3)
            # add text of prompt for visibility
            try:
                draw.text((10, 10), prompt_text[:100], fill=(0,0,0))
            except Exception:
                pass
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return buf.read()

        try:
            mock_bytes = _mock_generate(prompt)
            out_buf = remove_green_screen_from_bytes(mock_bytes)
            return StreamingResponse(out_buf, media_type='image/png')
        except Exception as exc:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f'Mock image generation failed: {exc}')

    # The SDK client is instantiated once at module import. We'll ensure the API key is present.
    # If you prefer to use per-request client instantiation, you can uncomment the following:
    # client = genai.Client(api_key=api_key)

    system_instruction = (
        'Create an image containing the subject described in the prompt. Use a solid green screen background (pure green, hex #00FF00) so the background can be removed easily. ' 
        'Ensure the subject is in focus and there is clear contrast between subject and background. Return a single PNG image.'
    )
    combined_prompt = f"{system_instruction}\n\nPrompt: {prompt}"

    # use the shared `client` declared at module level; we need to declare it as global
    global client
    try:
        # Initialize the client lazily if not already available
        if client is None:
            try:
                client = genai.Client(api_key=api_key)
            except Exception:
                # genai client initialization failed; we'll try to proceed and let the SDK raise a helpful error
                client = None
        # Configure new GenAI SDK client if not created earlier
        if client is None:
            try:
                client = genai.Client(api_key=api_key)
            except Exception:
                pass

        if client is None:
            raise ValueError('GenAI client not available; no `google-genai` installed or client creation failed')

        response = client.models.generate_content(
            model='gemini-2.5-flash-image',
            contents=[combined_prompt],
        )

        image_bytes = None
        # Iterate over response.parts: prefer inline image via `as_image()` if available
        for part in getattr(response, 'parts', []) or []:
            # If part has inline_data, it can be rendered as an image via `as_image()` (SDK convenience)
            try:
                if getattr(part, 'inline_data', None) is not None and hasattr(part, 'as_image'):
                    img = part.as_image()
                    # Convert PIL image to bytes for chroma key removal
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    buf.seek(0)
                    image_bytes = buf.read()
                    break
            except Exception:
                # fallback to reading data directly
                try:
                    data = getattr(part.inline_data, 'data', None)
                    if isinstance(data, (bytes, bytearray)):
                        image_bytes = bytes(data)
                        break
                    elif isinstance(data, str):
                        image_bytes = base64.b64decode(data)
                        break
                except Exception:
                    pass

        # fallback: try recursively extracting base64 from the response structure
        if not image_bytes:
            image_b64 = _extract_b64(response)
            if image_b64:
                image_bytes = base64.b64decode(image_b64)

        if not image_bytes:
            raise ValueError('Could not locate image data in SDK response')
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
