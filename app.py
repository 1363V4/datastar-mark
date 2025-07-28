from sanic import Sanic
from datastar_py.sanic import datastar_response, read_signals, datastar_respond

import uuid
import base64
from pathlib import Path


app = Sanic("mark")
app.static('/static/', './static/')
app.static("/", "index.html", name="index")
app.static("/editor", "editor.html", name="editor")


@app.before_server_start
async def attach_db(app):
    app.ctx.cwd = Path.cwd()

@app.on_response
async def cookie(request, response):
    if not request.cookies.get("user_id"):
        user_id = uuid.uuid4().hex
        response.add_cookie('user_id', user_id)

# @datastar_response
@app.post('/test')
async def test(request):
    response = await datastar_respond(request)
    signals = await read_signals(request)
    print(signals)
    photo_names = signals.get('photoNames', [])
    photo_datas = signals.get('photo', [])

    if photo_names and photo_datas:
        name = photo_names[0]
        b64data = photo_datas[0]
        with open(app.ctx.cwd / 'photos' / name, 'wb') as f:
            f.write(base64.b64decode(b64data))
        response.add_cookie('photo', name)
    await response.send()
