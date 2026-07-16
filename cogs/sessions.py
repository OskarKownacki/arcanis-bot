import os
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from discord import app_commands
from googleapiclient.discovery import build

from cogs.config import Config
from cogs.google_auth import GoogleAuth

SESSIONS_FILE = "sessions.json"
TIMEZONE = ZoneInfo("Europe/Warsaw")
SIGNUP_EMOJI = "✅"


class Sessions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    # ---------- Przechowywanie ----------
    @staticmethod
    def load_sessions():
        if not os.path.exists(SESSIONS_FILE):
            return {}
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def save_sessions(data):
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def _guild_bucket(data, guild_id: str):
        if guild_id not in data:
            data[guild_id] = {"next_id": 1, "sessions": {}}
        return data[guild_id]

    # ---------- Pomocnicze ----------
    @staticmethod
    def _parse_datetime(data_str: str, godzina_str: str) -> datetime | None:
        try:
            naive = datetime.strptime(f"{data_str} {godzina_str}", "%Y-%m-%d %H:%M")
            return naive.replace(tzinfo=TIMEZONE)
        except ValueError:
            return None

    @staticmethod
    def _extract_mentions(text: str) -> list[int]:
        return [int(uid) for uid in re.findall(r"<@!?(\d+)>", text or "")]

    def _build_embed(self, session: dict) -> discord.Embed:
        dt = datetime.fromisoformat(session["datetime"])
        narrators_str = ", ".join(f"<@{uid}>" for uid in session["narrators"])
        participants = session.get("participants", [])
        participants_str = ", ".join(f"<@{uid}>" for uid in participants) if participants else "Brak zapisanych"

        embed = discord.Embed(
            title=f"🎲 {session['title']}",
            description=session["description"],
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Data i godzina", value=f"<t:{int(dt.timestamp())}:F>", inline=False)
        embed.add_field(name="Narrator(zy)", value=narrators_str, inline=False)
        embed.add_field(name=f"Uczestnicy ({len(participants)})", value=participants_str, inline=False)
        embed.set_footer(text=f"ID sesji: {session['id']} • Zareaguj {SIGNUP_EMOJI}, aby dołączyć")
        return embed

    async def _update_message(self, guild: discord.Guild, session: dict):
        channel = guild.get_channel(session["channel_id"])
        if channel is None:
            return
        try:
            message = await channel.fetch_message(session["message_id"])
            await message.edit(embed=self._build_embed(session))
        except discord.NotFound:
            pass

    # ---------- Google Calendar ----------
    @staticmethod
    def _calendar_event_body(session: dict) -> dict:
        start = datetime.fromisoformat(session["datetime"])
        end = start + timedelta(hours=3)  # domyślny czas trwania sesji, edytowalny ręcznie w kalendarzu
        return {
            "summary": session["title"],
            "description": session["description"],
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }

    @staticmethod
    def _sync_calendar_for_narrator(session: dict, narrator_id: int):
        """Tworzy lub aktualizuje wydarzenie w kalendarzu narratora, jeśli ma połączone konto."""
        creds = GoogleAuth.get_credentials(narrator_id)
        if creds is None:
            return

        service = build("calendar", "v3", credentials=creds)
        event_id = session.setdefault("calendar_events", {}).get(str(narrator_id))
        body = Sessions._calendar_event_body(session)

        if event_id:
            try:
                service.events().update(calendarId="primary", eventId=event_id, body=body).execute()
                return
            except Exception:
                pass  # wydarzenie mogło zostać ręcznie usunięte — utwórz nowe

        created = service.events().insert(calendarId="primary", body=body).execute()
        session["calendar_events"][str(narrator_id)] = created["id"]

    @staticmethod
    def _remove_calendar_for_narrator(session: dict, narrator_id: int):
        creds = GoogleAuth.get_credentials(narrator_id)
        event_id = session.get("calendar_events", {}).pop(str(narrator_id), None)
        if creds is None or not event_id:
            return
        try:
            service = build("calendar", "v3", credentials=creds)
            service.events().delete(calendarId="primary", eventId=event_id).execute()
        except Exception:
            pass

    def _sync_calendar_all_narrators(self, session: dict):
        for narrator_id in session["narrators"]:
            try:
                self._sync_calendar_for_narrator(session, narrator_id)
            except Exception as e:
                print(f"Błąd synchronizacji kalendarza dla {narrator_id}: {e}")

    # ---------- Uprawnienia ----------
    @staticmethod
    def _can_edit(interaction: discord.Interaction, session: dict) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        return interaction.user.id in session["narrators"]

    # ---------- Komendy ----------
    @app_commands.command(name="plan-sesja", description="Planuje nową sesję.")
    @app_commands.describe(
        tytul="Tytuł sesji",
        opis="Opis sesji",
        data="Data w formacie RRRR-MM-DD",
        godzina="Godzina w formacie GG:MM",
        narratorzy="Dodatkowi narratorzy (wzmianki @, opcjonalnie)",
    )
    async def plan_sesja(
        self,
        interaction: discord.Interaction,
        tytul: str,
        opis: str,
        data: str,
        godzina: str,
        narratorzy: str = "",
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        dt = self._parse_datetime(data, godzina)
        if dt is None:
            await interaction.response.send_message(
                "❌ Nieprawidłowy format daty/godziny. Użyj RRRR-MM-DD oraz GG:MM.", ephemeral=True
            )
            return

        guild_id = str(interaction.guild.id)
        configs = Config.load_server_configs()
        session_channel_id = configs.get(guild_id, {}).get("session_channel_id")
        if not session_channel_id:
            await interaction.response.send_message(
                "❌ Nie ustawiono jeszcze kanału ogłoszeń sesji. Użyj najpierw `/config-session-channel`.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(session_channel_id)
        if channel is None:
            await interaction.response.send_message("❌ Ustawiony kanał ogłoszeń sesji nie istnieje.", ephemeral=True)
            return

        narrator_ids = list(dict.fromkeys([interaction.user.id, *self._extract_mentions(narratorzy)]))

        data_all = self.load_sessions()
        bucket = self._guild_bucket(data_all, guild_id)
        session_id = bucket["next_id"]
        bucket["next_id"] += 1

        session = {
            "id": session_id,
            "title": tytul,
            "description": opis,
            "datetime": dt.isoformat(),
            "narrators": narrator_ids,
            "participants": [],
            "channel_id": channel.id,
            "message_id": None,
            "calendar_events": {},
            "reminder_sent": False,
        }

        await interaction.response.defer(ephemeral=True)

        message = await channel.send(embed=self._build_embed(session))
        await message.add_reaction(SIGNUP_EMOJI)
        session["message_id"] = message.id

        self._sync_calendar_all_narrators(session)

        bucket["sessions"][str(session_id)] = session
        self.save_sessions(data_all)

        await interaction.followup.send(f"✅ Sesja utworzona (ID: {session_id}) na kanale {channel.mention}.", ephemeral=True)

    @app_commands.command(name="sesja-lista", description="Pokazuje zaplanowane sesje na tym serwerze.")
    async def sesja_lista(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        bucket = self.load_sessions().get(guild_id, {"sessions": {}})
        sessions = sorted(bucket["sessions"].values(), key=lambda s: s["datetime"])

        if not sessions:
            await interaction.response.send_message("ℹ️ Brak zaplanowanych sesji.", ephemeral=True)
            return

        lines = []
        for s in sessions:
            dt = datetime.fromisoformat(s["datetime"])
            lines.append(f"**#{s['id']}** {s['title']} — <t:{int(dt.timestamp())}:f>")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="sesja-usun", description="Usuwa zaplanowaną sesję.")
    @app_commands.describe(session_id="ID sesji")
    async def sesja_usun(self, interaction: discord.Interaction, session_id: int):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        data_all = self.load_sessions()
        bucket = data_all.get(guild_id, {"sessions": {}})
        session = bucket["sessions"].get(str(session_id))

        if not session:
            await interaction.response.send_message("❌ Nie znaleziono sesji o takim ID.", ephemeral=True)
            return

        if not self._can_edit(interaction, session):
            await interaction.response.send_message("❌ Tylko narrator tej sesji lub administrator może ją usunąć.", ephemeral=True)
            return

        for narrator_id in list(session.get("calendar_events", {}).keys()):
            self._remove_calendar_for_narrator(session, int(narrator_id))

        channel = interaction.guild.get_channel(session["channel_id"])
        if channel:
            try:
                message = await channel.fetch_message(session["message_id"])
                await message.delete()
            except discord.NotFound:
                pass

        del bucket["sessions"][str(session_id)]
        self.save_sessions(data_all)

        await interaction.response.send_message(f"✅ Sesja #{session_id} została usunięta.", ephemeral=True)

    async def _edit_field(self, interaction: discord.Interaction, session_id: int, apply_fn):
        if interaction.guild is None:
            await interaction.response.send_message("Tej komendy możesz użyć tylko na serwerze!", ephemeral=True)
            return None

        guild_id = str(interaction.guild.id)
        data_all = self.load_sessions()
        bucket = data_all.get(guild_id, {"sessions": {}})
        session = bucket["sessions"].get(str(session_id))

        if not session:
            await interaction.response.send_message("❌ Nie znaleziono sesji o takim ID.", ephemeral=True)
            return None

        if not self._can_edit(interaction, session):
            await interaction.response.send_message("❌ Tylko narrator tej sesji lub administrator może ją edytować.", ephemeral=True)
            return None

        apply_fn(session)
        await self._update_message(interaction.guild, session)
        self.save_sessions(data_all)
        return session

    @app_commands.command(name="sesja-edytuj-tytul", description="Zmienia tytuł sesji.")
    @app_commands.describe(session_id="ID sesji", nowy_tytul="Nowy tytuł")
    async def sesja_edytuj_tytul(self, interaction: discord.Interaction, session_id: int, nowy_tytul: str):
        session = await self._edit_field(interaction, session_id, lambda s: s.__setitem__("title", nowy_tytul))
        if session:
            self._sync_calendar_all_narrators(session)
            self.save_sessions(self.load_sessions() | {})  # no-op safeguard removed below
            await interaction.response.send_message(f"✅ Zmieniono tytuł sesji #{session_id}.", ephemeral=True)

    @app_commands.command(name="sesja-edytuj-opis", description="Zmienia opis sesji.")
    @app_commands.describe(session_id="ID sesji", nowy_opis="Nowy opis")
    async def sesja_edytuj_opis(self, interaction: discord.Interaction, session_id: int, nowy_opis: str):
        session = await self._edit_field(interaction, session_id, lambda s: s.__setitem__("description", nowy_opis))
        if session:
            self._sync_calendar_all_narrators(session)
            await interaction.response.send_message(f"✅ Zmieniono opis sesji #{session_id}.", ephemeral=True)

    @app_commands.command(name="sesja-edytuj-termin", description="Zmienia datę i godzinę sesji.")
    @app_commands.describe(session_id="ID sesji", data="Nowa data RRRR-MM-DD", godzina="Nowa godzina GG:MM")
    async def sesja_edytuj_termin(self, interaction: discord.Interaction, session_id: int, data: str, godzina: str):
        dt = self._parse_datetime(data, godzina)
        if dt is None:
            await interaction.response.send_message("❌ Nieprawidłowy format daty/godziny.", ephemeral=True)
            return

        def apply(s):
            s["datetime"] = dt.isoformat()
            s["reminder_sent"] = False

        session = await self._edit_field(interaction, session_id, apply)
        if session:
            self._sync_calendar_all_narrators(session)
            await interaction.response.send_message(f"✅ Zmieniono termin sesji #{session_id}.", ephemeral=True)

    @app_commands.command(name="sesja-dodaj-narratora", description="Dodaje narratora do sesji.")
    @app_commands.describe(session_id="ID sesji", uzytkownik="Narrator do dodania")
    async def sesja_dodaj_narratora(self, interaction: discord.Interaction, session_id: int, uzytkownik: discord.Member):
        def apply(s):
            if uzytkownik.id not in s["narrators"]:
                s["narrators"].append(uzytkownik.id)

        session = await self._edit_field(interaction, session_id, apply)
        if session:
            self._sync_calendar_for_narrator(session, uzytkownik.id)
            self.save_sessions(self.load_sessions())
            await interaction.response.send_message(f"✅ Dodano {uzytkownik.mention} jako narratora sesji #{session_id}.", ephemeral=True)

    @app_commands.command(name="sesja-usun-narratora", description="Usuwa narratora z sesji.")
    @app_commands.describe(session_id="ID sesji", uzytkownik="Narrator do usunięcia")
    async def sesja_usun_narratora(self, interaction: discord.Interaction, session_id: int, uzytkownik: discord.Member):
        def apply(s):
            if uzytkownik.id in s["narrators"]:
                s["narrators"].remove(uzytkownik.id)

        session = await self._edit_field(interaction, session_id, apply)
        if session:
            self._remove_calendar_for_narrator(session, uzytkownik.id)
            self.save_sessions(self.load_sessions())
            await interaction.response.send_message(f"✅ Usunięto {uzytkownik.mention} z listy narratorów sesji #{session_id}.", ephemeral=True)

    # ---------- Zapisy przez reakcję ----------
    def _find_session_by_message(self, message_id: int):
        data_all = self.load_sessions()
        for guild_id, bucket in data_all.items():
            for session in bucket["sessions"].values():
                if session["message_id"] == message_id:
                    return data_all, guild_id, session
        return None, None, None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or str(payload.emoji) != SIGNUP_EMOJI:
            return

        data_all, guild_id, session = self._find_session_by_message(payload.message_id)
        if session is None:
            return

        if payload.user_id not in session["participants"]:
            session["participants"].append(payload.user_id)
            self.save_sessions(data_all)
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                await self._update_message(guild, session)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or str(payload.emoji) != SIGNUP_EMOJI:
            return

        data_all, guild_id, session = self._find_session_by_message(payload.message_id)
        if session is None:
            return

        if payload.user_id in session["participants"]:
            session["participants"].remove(payload.user_id)
            self.save_sessions(data_all)
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                await self._update_message(guild, session)

    # ---------- Przypomnienia ----------
    @tasks.loop(minutes=1)
    async def reminder_loop(self):
        data_all = self.load_sessions()
        now = datetime.now(TIMEZONE)
        changed = False

        for guild_id, bucket in data_all.items():
            for session in bucket["sessions"].values():
                if session.get("reminder_sent"):
                    continue

                dt = datetime.fromisoformat(session["datetime"])
                minutes_left = (dt - now).total_seconds() / 60

                if 0 <= minutes_left <= 15:
                    recipients = set(session["narrators"]) | set(session["participants"])
                    for user_id in recipients:
                        user = self.bot.get_user(user_id)
                        if user is None:
                            try:
                                user = await self.bot.fetch_user(user_id)
                            except discord.NotFound:
                                continue
                        try:
                            await user.send(
                                f"⏰ Przypomnienie: sesja **{session['title']}** zaczyna się za 15 minut!"
                            )
                        except discord.Forbidden:
                            pass

                    session["reminder_sent"] = True
                    changed = True

        if changed:
            self.save_sessions(data_all)

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Sessions(bot))