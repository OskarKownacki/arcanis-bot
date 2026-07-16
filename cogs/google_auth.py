import os
import time
import secrets
import json
import discord
from discord.ext import commands
from discord import app_commands
from aiohttp import web
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest

TOKENS_FILE = "google_tokens.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
OAUTH_PORT = int(os.getenv("GOOGLE_OAUTH_PORT", "8081"))

CLIENT_CONFIG = {
    "web": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI],
    }
}


class GoogleAuth(commands.Cog):
    """Logowanie narratorów do Google Calendar (OAuth2) + serwer odbierający przekierowanie."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.runner = None
        # state -> (discord_user_id, wygasa_timestamp)
        self.pending_states = {}

    async def cog_load(self):
        if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
            print("⚠️  Brak GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI w .env — integracja z Google Calendar wyłączona.")
            return

        app = web.Application()
        app.router.add_get("/oauth2callback", self.handle_oauth_callback)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", OAUTH_PORT)
        await site.start()
        print(f"Serwer OAuth Google działa na porcie {OAUTH_PORT}")

    async def cog_unload(self):
        if self.runner:
            await self.runner.cleanup()

    # ---------- Przechowywanie tokenów ----------
    @staticmethod
    def load_tokens():
        if not os.path.exists(TOKENS_FILE):
            return {}
        try:
            with open(TOKENS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def save_tokens(tokens):
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=4, ensure_ascii=False)

    @staticmethod
    def is_connected(user_id: int) -> bool:
        return str(user_id) in GoogleAuth.load_tokens()

    @staticmethod
    def get_credentials(user_id: int):
        """Zwraca ważne dane logowania (Credentials) danego użytkownika albo None, jeśli nie jest połączony."""
        tokens = GoogleAuth.load_tokens()
        data = tokens.get(str(user_id))
        if not data:
            return None

        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes"),
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            GoogleAuth._store_credentials(user_id, creds)

        return creds

    @staticmethod
    def _store_credentials(user_id: int, creds: Credentials):
        tokens = GoogleAuth.load_tokens()
        tokens[str(user_id)] = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }
        GoogleAuth.save_tokens(tokens)

    # ---------- Komendy ----------
    @app_commands.command(name="polacz-kalendarz", description="Połącz swoje konto Google Calendar z botem.")
    async def polacz_kalendarz(self, interaction: discord.Interaction):
        if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
            await interaction.response.send_message(
                "❌ Integracja z Google Calendar nie jest jeszcze skonfigurowana przez administratora bota.",
                ephemeral=True,
            )
            return

        state = secrets.token_urlsafe(24)
        self.pending_states[state] = (interaction.user.id, time.time() + 600)

        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )

        await interaction.response.send_message(
            f"🔗 Kliknij, aby połączyć swoje konto Google Calendar:\n{auth_url}\n\nLink jest ważny 10 minut.",
            ephemeral=True,
        )

    @app_commands.command(name="rozlacz-kalendarz", description="Odłącz swoje konto Google Calendar od bota.")
    async def rozlacz_kalendarz(self, interaction: discord.Interaction):
        tokens = GoogleAuth.load_tokens()
        if str(interaction.user.id) in tokens:
            del tokens[str(interaction.user.id)]
            GoogleAuth.save_tokens(tokens)
            await interaction.response.send_message("✅ Odłączono Twoje konto Google Calendar.", ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ Nie masz połączonego konta Google Calendar.", ephemeral=True)

    # ---------- Callback WWW ----------
    async def handle_oauth_callback(self, request: web.Request):
        state = request.query.get("state")
        code = request.query.get("code")

        if not state or not code:
            return web.Response(status=400, text="Brak wymaganych parametrów.")

        pending = self.pending_states.pop(state, None)
        if not pending:
            return web.Response(status=400, text="Nieprawidłowy lub wygasły link. Użyj ponownie /polacz-kalendarz.")

        user_id, expiry = pending
        if time.time() > expiry:
            return web.Response(status=400, text="Link wygasł. Użyj ponownie /polacz-kalendarz.")

        try:
            flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
            flow.fetch_token(code=code)
            GoogleAuth._store_credentials(user_id, flow.credentials)
        except Exception as e:
            return web.Response(status=500, text=f"Błąd podczas łączenia konta: {e}")

        return web.Response(
            text="✅ Konto Google Calendar zostało połączone! Możesz wrócić do Discorda.",
            content_type="text/html",
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GoogleAuth(bot))