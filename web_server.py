from aiohttp import web
import logging

log = logging.getLogger("VoiceBot")

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><title>Bot Dashboard</title></head>
<body><h1>Dashboard đang chạy</h1><p>Bot đang online 24/7.</p></body>
</html>"""

routes = web.RouteTableDef()

@routes.get("/")
async def index(_): 
    return web.Response(text=DASHBOARD_HTML, content_type="text/html") 

async def start_web_server(bot, port: int):
    app = web.Application()
    app.add_routes(routes)
    
    # Bạn có thể lưu bot vào app để các API sau này gọi được bot
    app['bot'] = bot 
    
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info(f"🌐 Web Dashboard đang chạy tại port {port}")