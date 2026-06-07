import discord
from discord.ext import commands
from aiohttp import web

CHANNEL_ID = 1478822210985656415
SECRET_TOKEN = "tajny_token_xyz"

class MinecraftBridge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.runner = None

    async def cog_load(self):
        """Uruchamia serwer HTTP gdy cog się ładuje."""
        app = web.Application()
        app.router.add_post("/minecraft", self.handle_minecraft)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", 8080)
        await site.start()
        print("Serwer HTTP (Minecraft bridge) działa na porcie 8080")

    async def cog_unload(self):
        """Zatrzymuje serwer HTTP gdy cog się wyładowuje."""
        if self.runner:
            await self.runner.cleanup()

    async def handle_minecraft(self, request: web.Request):
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {SECRET_TOKEN}":
            return web.Response(status=401, text="Unauthorized")

        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")

        message = data.get("message", "")
        channel = self.bot.get_channel(CHANNEL_ID)

        if channel and message:
            await channel.send(message)
            return web.Response(text="OK")

        return web.Response(status=400, text="Bad request")


async def setup(bot: commands.Bot):
    await bot.add_cog(MinecraftBridge(bot))