import discord
from discord.ext import commands
from aiohttp import web
import asyncio

CHANNEL_ID = 1478822210985656415  # ID kanału Discord
SECRET_TOKEN = "tajny_token_xyz"  # zabezpieczenie

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Endpoint HTTP ---
async def handle_minecraft(request: web.Request):
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {SECRET_TOKEN}":
        return web.Response(status=401, text="Unauthorized")

    data = await request.json()
    message = data.get("message", "")

    channel = bot.get_channel(CHANNEL_ID)
    if channel and message:
        await channel.send(message)
        return web.Response(text="OK")

    return web.Response(status=400, text="Bad request")

async def start_http_server():
    app = web.Application()
    app.router.add_post("/minecraft", handle_minecraft)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)  # port 8080
    await site.start()

@bot.event
async def on_ready():
    print(f"Bot gotowy: {bot.user}")
    await start_http_server()
    print("Serwer HTTP działa na porcie 8080")

bot.run("TWÓJ_TOKEN_DISCORD")