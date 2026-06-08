import re
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import aiorcon
from aiorcon.messages import RCONMessage
from cogs.config import Config


def _split_player_names(raw_players: str) -> list[str]:
    players = []
    for player in raw_players.split(','):
        clean_player = player.strip()
        if clean_player and re.fullmatch(r"[A-Za-z0-9_]{3,16}", clean_player):
            players.append(clean_player)
    return players


def _normalize_rcon_line(raw_line: str) -> str:
    line = raw_line.strip()
    if line.startswith("[") and "]:" in line:
        return line.rsplit("]:", 1)[-1].strip()
    return strip_minecraft_colors(line)


def strip_minecraft_colors(text: str) -> str:
    return re.sub(r'§.', '', text)


def _extract_list_players(response_text: str) -> list[str]:
    players = []
    seen_players = set()

    for raw_line in response_text.splitlines():
        line = _normalize_rcon_line(raw_line)
        if not line:
            continue

        summary_match = re.search(r"players?\s+online:\s*(?P<players>.+)$", line, re.IGNORECASE)
        if summary_match:
            candidate_players = _split_player_names(summary_match.group("players"))
        elif ":" in line:
            _, players_block = line.split(":", 1)
            candidate_players = _split_player_names(players_block)
        else:
            continue

        for player in candidate_players:
            if player not in seen_players:
                seen_players.add(player)
                players.append(player)

    return players


def _extract_seen_online_since(response_text: str) -> str | None:
    for raw_line in response_text.splitlines():
        line = _normalize_rcon_line(raw_line)
        match = re.search(r"Player\s+.+?\s+has\s+been\s+online\s+since\s+(?P<duration>.+?)\.$", line, re.IGNORECASE)
        if match:
            return match.group("duration").strip()
    return None


async def _create_rcon_client(host: str, port: int, password: str):
    RCONMessage.ENCODING = "utf-8"
    return await aiorcon.RCON.create(
        host,
        port,
        password,
        loop=asyncio.get_running_loop(),
        multiple_packet=False,
        timeout=5.0,
    )


async def _fetch_player_online_since(client, player: str) -> str | None:
    response = await client.execute(f"seen {player}")
    return _extract_seen_online_since(response)

class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @app_commands.command(name="list", description="Sprawdź listę graczy na serwerze.")
    async def list_command(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        configs = Config.load_server_configs()
        server_setting = configs.get(guild_id)

        if not server_setting or "rcon_password" not in server_setting:
            await interaction.response.send_message(
                "❌ Ten serwer Discord nie ma jeszcze skonfigurowanego hasła RCON!\nUżyj najpierw komendy `/config-rcon-password`.", 
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        host = server_setting.get("ip", "127.0.0.1")
        port = int(server_setting.get("rcon_port", 25575))
        password = server_setting["rcon_password"]
        client = None

        try:
            client = await _create_rcon_client(host, port, password)

            response_list = await client.execute("list")
            players = _extract_list_players(response_list)

            if players:
                player_rows = []
                for player in players:
                    try:
                        online_since = await _fetch_player_online_since(client, player)
                    except Exception:
                        online_since = None

                    if online_since:
                        player_rows.append(f"{player} — online od {online_since}")
                    else:
                        player_rows.append(f"{player} — czas online niedostępny")

                players_list_str = "\n".join(player_rows)

                embed = discord.Embed(
                    title="🟢 Gracze online",
                    description=f"Aktualnie na serwerze ({len(players)}):\n\n{players_list_str}",
                    color=discord.Color.green(),
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("ℹ️ Na serwerze nie ma obecnie nikogo online.")

        except Exception as e:
            await interaction.followup.send(f"❌ Błąd połączenia z RCON (`{host}:{port}`): `{e}`")
        finally:
            if client is not None:
                client.close()
    @app_commands.command(name="ranking", description="Sprawdź ranking graczy na serwerze.")
    async def ranking_command(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        configs = Config.load_server_configs()
        server_setting = configs.get(guild_id)

        if not server_setting or "rcon_password" not in server_setting:
            await interaction.response.send_message(
                "❌ Ten serwer Discord nie ma jeszcze skonfigurowanego hasła RCON!\nUżyj najpierw komendy `/config-rcon-password`.", 
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        host = server_setting.get("ip", "127.0.0.1")
        port = int(server_setting.get("rcon_port", 25575))
        password = server_setting["rcon_password"]
        client = None

        try:
            client = await _create_rcon_client(host, port, password)

            response_list = await client.execute("rankingconsole")

            embed = discord.Embed(
                    title="Ranking graczy",
                    description=f"```text\n{strip_minecraft_colors(response_list)}```",
                    color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Błąd połączenia z RCON (`{host}:{port}`): `{e}`")
        finally:
            if client is not None:
                client.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Minecraft(bot))