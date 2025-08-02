from sanic import Sanic, exceptions
from datastar_py.sanic import read_signals, datastar_respond, ServerSentEventGenerator as SSE
from sanic.response import file

import uuid
import base64
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


app = Sanic("mark")
app.static('/static/', './static/')
app.static('/photos/', './photos/', name="photos")
app.static("/", "index.html", name="index")

# VIEWS

async def editor_view(filename):
    return f'''
<main id="main">
    <div id="editor-page" class="gc gq">
        <header class="gg10 gc">
            <h1 class="gt-l">Water Marc</h1>
            <img src="/static/img/marc.png">
        </header>
        <section class="gg01">
            <div id="editor" class="gc gp-m">
                <input data-bind-text type="text" placeholder="Watermark text" value="Confidential">
                <label>
                    Font size:
                    <select id="font-size" data-bind-font.size>
                        <option value="1px">Small</option>
                        <option value="2px" selected>Medium</option>
                        <option value="5px">Large</option>
                        <option value="10px">Extra Large</option>
                    </select>
                </label>
                <label>
                    Color:
                    <input data-bind-color type="color" id="color" value="#000000">
                </label>
                <label>
                    Outline:
                    <input data-bind-stroke type="color" id="color" value="#FFFFFF">
                </label>
                <label>
                    Angle:
                    <input data-bind-rotation type="number" id="angle" min="-50" max="50" value="45" step="1">°
                </label>
            </div>
            <div id="document" class="gc gz">
                <svg 
                viewBox="0 0 50 50"
                data-computed-textmax="Array(10).fill($text).join(' - ')"
                data-attr="{{'font-size': $font.size, 'fill': $color, 'stroke': $stroke}}"
                preserveAspectRatio="xMidYMid slice">
                    <defs>
                        <text id="watermark-text" data-text="$textmax" data-style-rotate="$rotation + 'deg'"></text>
                    </defs>
                    <use href="#watermark-text" x="25" y="-30" />
                    <use href="#watermark-text" x="25" y="-20" />
                    <use href="#watermark-text" x="25" y="-10" />
                    <use href="#watermark-text" x="25" y="0" />
                    <use href="#watermark-text" x="25" y="10" />
                    <use href="#watermark-text" x="25" y="20" />
                    <use href="#watermark-text" x="25" y="30" />
                    <use href="#watermark-text" x="25" y="40" />
                    <use href="#watermark-text" x="25" y="50" />
                    <use href="#watermark-text" x="25" y="60" />
                    <use href="#watermark-text" x="25" y="70" />
                    <use href="#watermark-text" x="25" y="80" />
                    <use href="#watermark-text" x="25" y="90" />
                </svg>
                <img src="/photos/{filename}"/>
            </div>
        </section>
        <button id="dl_button" class="gp-s gm-l" 
        data-on-pointerdown="@post('/download', {{filterSignals: {{exclude: /photo/}},}})">Download</button>
    </div>
</main>
'''

# UTILS

async def create_watermarked_image(photo_path, text, stroke, font_size, color, rotation, filename):
    image = Image.open(photo_path).convert('RGBA')
    width, height = image.size
    watermark_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    font = ImageFont.truetype("arial.ttf", int(font_size[:-2]) * 20)
    bbox = font.getbbox(text)
    textwidth, textheight = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_img = Image.new('RGBA', (textwidth, textheight), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((0, 0), text, font=font, fill=color, stroke_width=2, stroke_fill=stroke)
    rotated_text = text_img.rotate(float(rotation * -1) if rotation else 0, expand=1)
    rtw, rth = rotated_text.size
    for y in range(0, height, rth + 40):
        for x in range(0, width, rtw + 40):
            watermark_layer.alpha_composite(rotated_text, (x, y))
    watermarked = Image.alpha_composite(image, watermark_layer)
    download_filename = f"watermarked_{filename}.png"
    return watermarked, download_filename


# APP

@app.before_server_start
async def setup_ctx(app):
    app.ctx.cwd = Path.cwd()

@app.on_response
async def cookie(request, response):
    if not request.cookies.get("user_id"):
        user_id = uuid.uuid4().hex
        response.add_cookie('user_id', user_id)

@app.post('/send')
async def send(request):
    response = await datastar_respond(request)
    await response.send(SSE.patch_elements("<p id='home-input'>Processing file...</p>"))
    signals = await read_signals(request)
    print(signals)
    photo_names = signals.get('photoNames', [])
    photo_mimes = signals.get('photoMimes', [])
    photo_datas = signals.get('photo', [])

    if photo_names and photo_datas and photo_mimes[0] in ["image/png", "image/jpeg"]:
        b64data = photo_datas[0]
        decoded_data = base64.b64decode(b64data)
        if len(decoded_data) > 1024 * 1024:
            await response.send(SSE.patch_elements("<p id='home-input'>File too large! (max 1MB)</p>"))
        else:
            filename = f"{request.cookies.get('user_id')}"
            with open(app.ctx.cwd / 'photos' / filename, 'wb') as f:
                f.write(decoded_data)
            html = await editor_view(filename)
            await response.send(SSE.patch_elements(html))
    else:
        await response.send(SSE.patch_elements("<p id='home-input'>Bad file!</p>"))

@app.post('/download')
async def download(request):
    response = await datastar_respond(request)
    signals = await read_signals(request)
    print(signals)
    text = signals.get("text")
    stroke = signals.get("stroke")
    font_size = signals.get("font", {}).get("size")
    color = signals.get("color")
    rotation = signals.get("rotation")
    filename = request.cookies.get('user_id')
    photo_path = app.ctx.cwd / 'photos' / filename
    watermarked, download_filename = await create_watermarked_image(photo_path, text, stroke, font_size, color, rotation, filename)
    download_path = app.ctx.cwd / 'photos' / download_filename
    watermarked.convert('RGB').save(download_path, format='PNG')
    download_url = f"/download/file/{download_filename}"
    await response.send(SSE.patch_elements(
        f'''<button id="dl_button" class="gp-s gm-l"><a href='{download_url}' download>Download your watermarked image</a></button>'''
        ))
    await asyncio.sleep(3)
    await response.send(SSE.execute_script("dl_button.firstChild.click()"))


@app.get('/download/file/<filename>')
async def download_file(request, filename):
    if request.cookies.get('user_id') in filename:
        file_path = app.ctx.cwd / 'photos' / filename
        mime_type = "image/png" if filename.endswith(".png") else "image/jpeg"
        return await file(file_path, filename=filename, mime_type=mime_type)
    else:
        raise exceptions.Forbidden()
