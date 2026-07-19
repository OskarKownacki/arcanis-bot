# Agents Documentation

This project uses a modular structure with 'cogs' to manage Discord features and backend logic. Use the following guidelines when modifying or extending the bot.

## Core Capabilities
- **Discord Interaction**: Handling commands, events, and UI components in `main.py` and various files in `cogs/`.
- **Minecraft Integration**: Managing RCON connections and server state via `cogs/minecraft.py` (using information from `models.py`).
- **Configuration Management**: Handled in `cogs/config.py`, managing persistence of server settings.

## Task Guidance

### Adding New Features
- **New Commands**: Create a new file under `cogs/` if the feature is large enough to warrant its own cog. If it's a small extension, add it to an existing relevant cog.
- **Data Model Changes**: Update `models.py` before changing the logic that consumes these models in the cogs.

### Development Workflow
1. **Check Dependencies**: Add any new libraries to `requirements.txt`.
2. **Update Logging**: Ensure all significant state changes or errors are handled by the logger defined in `cogs/logs.py`.
3. **Validation**: When updating RCON parameters, ensure validation logic is performed before attempting a connection.

## Integration Points
- **RCON Connection**: Handled via standard libraries, settings pulled from `config.py`.
- **Session Management**: Logic resides in `cogs/sessions.py`.
