import logging
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

# Tworzymy klasę bota, aby móc wygodnie nadpisać setup_hook
class ArcanisBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    # To uruchamia się ZANIM bot połączy się z Discordem
    async def setup_hook(self):
        # Dynamicznie ładujemy każdy plik .py z folderu cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                # Zamieniamy nazwę np. 'general.py' na 'cogs.general'
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'Załadowano moduł: {filename}')

bot = ArcanisBot()

@bot.event
async def on_ready():
    print(f'------\nZalogowano jako {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Zsynchronizowano {len(synced)} komend slash globalnie.")
        game = discord.Game("Gra w Arcanis")
        await bot.change_presence(activity=game)
    except Exception as e:
        print(f"Błąd synchronizacji komend: {e}")

if TOKEN:
    bot.run(TOKEN)
else:
    print("BŁĄD: Brak tokenu w pliku .env!")

logging.basicConfig(level=logging.INFO)

@bot.event
async def on_command(ctx):
    logging.info(f"[COMMAND] {ctx.author} | {ctx.message.content} | #{ctx.channel} | {ctx.guild}")