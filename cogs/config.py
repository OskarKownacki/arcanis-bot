import os
import json
import discord
from discord.ext import commands
from discord import app_commands

CONFIG_FILE = "server_configs.json"

class Config(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Dodany dekorator staticmethod i usunięte self, by inne pliki mogły z tego łatwo korzystać
    @staticmethod
    def load_server_configs():
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def save_server_configs(configs):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(configs, f, indent=4, ensure_ascii=False)

    @app_commands.command(name="config-ip", description="Ustawia adres IP serwera dla tego bota.")
    @app_commands.describe(ip_address="Adres IP serwera")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_ip(self, interaction: discord.Interaction, ip_address: str):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        configs = Config.load_server_configs()

        if guild_id not in configs:
            configs[guild_id] = {}

        configs[guild_id]["ip"] = ip_address
        Config.save_server_configs(configs)

        await interaction.response.send_message(f"✅ Pomyślnie ustawiono IP dla tego serwera na: `{ip_address}`")

    @app_commands.command(name="show-ip", description="Pokazuje zapisany adres IP dla tego serwera.")
    async def show_ip(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        configs = Config.load_server_configs()
        server_ip = configs.get(guild_id, {}).get("ip")

        if server_ip:
            await interaction.response.send_message(f"📌 Adres IP skonfigurowany dla tego serwera to: `{server_ip}`")
        else:
            await interaction.response.send_message("❌ Ten serwer nie ma jeszcze skonfigurowanego adresu IP.", ephemeral=True)

    @app_commands.command(name="config-rcon-port", description="Ustawia port RCON serwera dla tego bota.")
    @app_commands.describe(port="Port RCON serwera")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_rcon_port(self, interaction: discord.Interaction, port: int):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        configs = Config.load_server_configs()

        if guild_id not in configs:
            configs[guild_id] = {}

        configs[guild_id]["rcon_port"] = port
        Config.save_server_configs(configs)

        await interaction.response.send_message(f"✅ Pomyślnie ustawiono port RCON dla tego serwera na: `{port}`")

    @app_commands.command(name="config-rcon-password", description="Ustawia hasło RCON serwera dla tego bota.")
    @app_commands.describe(password="Hasło RCON serwera")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_rcon_password(self, interaction: discord.Interaction, password: str):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        configs = Config.load_server_configs()

        if guild_id not in configs:
            configs[guild_id] = {}

        configs[guild_id]["rcon_password"] = password
        Config.save_server_configs(configs)

        # Używamy ephemeral=True, żeby wpisane hasło nie wisiało publicznie na kanale tekstowym
        await interaction.response.send_message(f"✅ Pomyślnie ustawiono hasło RCON dla tego serwera.", ephemeral=True)

    @app_commands.command(name="config-session-channel", description="Ustawia kanał, na którym będą ogłaszane sesje.")
    @app_commands.describe(channel="Kanał do ogłoszeń sesji")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_session_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        configs = Config.load_server_configs()

        if guild_id not in configs:
            configs[guild_id] = {}

        configs[guild_id]["session_channel_id"] = channel.id
        Config.save_server_configs(configs)

        await interaction.response.send_message(f"✅ Kanał ogłoszeń sesji ustawiono na {channel.mention}")
async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))