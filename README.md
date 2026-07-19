# Arcanis Bot

A Discord bot integrated with a Minecraft server via RCON, providing features such as player lists, rankings, and session management.

## Features

- **Minecraft Integration**: Retrieve real-time information from the server using RCON.
    - List of online players with their login duration.
    - Server ranking stats.
    - Dynamic status updates showing the number of players online (including those in vanish).
- **Configuration Management**: Easy configuration of RCON details (IP, Port, Password) and session channels directly through Discord commands.
- **Logging**: Integrated logging for tracking bot activities and errors.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your_username/arcanis-bot.git
   cd arcanis-bot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the environment:
   Create a `.env` file in the root directory and add your Discord bot token:
   ```env
   DISCORD_TOKEN=your_token_here
   ```

4. Run the bot:
   ```bash
   python main.py
   ```

## Configuration Commands (Admin Only)

The following commands allow configuration of server settings directly from a Guild:
- `/config-ip`: Set the RCON IP address.
- `/config-rcon-port`: Set the RCON port.
- `/config-rcon-password`: Set the RCON password.
- `/config-session-channel`: Set the channel for session announcements.
- `/show-ip`: Display the currently configured IP.

## Project Structure
- `main.py`: Main entry point of the bot.
- `models.py`: Data models and backend logic.
- `cogs/`: Modular components (Minecraft, Config, etc.).
- `requirements.txt`: Python dependencies.
