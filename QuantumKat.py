from asyncio import run
from datetime import datetime, timedelta
from os import environ
from random import choice, randint
from sys import exit
from subprocess import CalledProcessError

from helpers import MiscHelper
import discord
from discord.ext import commands
from dotenv import load_dotenv
from num2words import num2words
from threading import Thread
import pubapi

from sql import models, schemas
from sql.database import engine, AsyncSessionLocal
from sql import crud
from cogs.utils._logger import quantumkat_logger
from cogs.utils.utils import get_field_from_1password
from cogs.utils.utils import DiscordHelper


async def init_models():
    async with engine.begin() as conn:
        # For testing purposes, drop all tables
        # await conn.run_sync(models.Base.metadata.drop_all)
        await conn.run_sync(models.Base.metadata.create_all)


misc_helper = MiscHelper()


# If False, will exit if a required program is missing
# Can be set to True for debugging without needing them installed
ignoreMissingExe = True

# List of required executables
executables = ["ffmpeg", "ffprobe", "youtube-dl"]

# Load .env file which contains bot token and my user ID
# and store in OS user environment variables
load_dotenv()

# Get the bot token and my user ID from the environment variables
OWNER_ID = environ.get("OWNER_ID")
token_type = environ.get("TOKEN_TYPE", "Main")
references = f"op://Programming and IT security/QuantumKat Discord bot/{token_type} token"  # The tokens are stored in 1Password, separated by sections matching the token type, allowing us to have multiple tokens and quickly switch between them
try:
    TOKEN = get_field_from_1password(references)
except CalledProcessError:
    quantumkat_logger.error(
        f"Error: Unable to retrieve token from 1Password. Reference: {references}",
        exc_info=True,
    )
    exit(1)

# If the bot token or my user ID is not set, exit the program
if OWNER_ID is None or OWNER_ID == "":
    quantumkat_logger.error(
        "Error: The OWNER_ID environment variable is not set or is empty."
    )
    exit(1)

if TOKEN is None or TOKEN == "":
    quantumkat_logger.error(
        "Error: The TOKEN environment variable is not set or is empty."
    )
    exit(1)

# Gives the bot default access as well as access
# to contents of messages and managing members
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Sets the bot's command prefix, help command, intents, and adds my ID to owner_ids
bot = commands.Bot(
    command_prefix="?",
    help_command=commands.DefaultHelpCommand(
        sort_commands=False, show_parameter_descriptions=False, width=100
    ),
    intents=intents,
    owner_ids=[int(OWNER_ID)],
)

bot.reboot_scheduled = False


async def setup(bot: commands.Bot):
    if not ignoreMissingExe:
        for executable in executables:
            if not misc_helper.is_installed(executable):
                quantumkat_logger.error(f"Error: {executable} is not installed.")
                exit(1)

    await DiscordHelper.first_load_cogs(bot, "./cogs")
    await bot.start(TOKEN, reconnect=True)


async def is_authenticated(ctx: commands.Context) -> bool:
    if ctx.author.id in bot.owner_ids:
        return True
    if not ctx.command.name.casefold() == "request_auth":
        authenticated_server_ids = await crud.get_authenticated_servers(
            AsyncSessionLocal
        )
        authenticated_server_ids = [server[0] for server in authenticated_server_ids]
        if DiscordHelper.is_dm(ctx):
            # If the command is run in a DM, check if the user is in an authenticated server
            for guild in bot.guilds:
                if guild.id in authenticated_server_ids:
                    if DiscordHelper.user_in_guild(ctx.author, guild):
                        return True
            await ctx.send(
                "You need to be in an at least one authenticated server to interact with me in DMs."
            )
            return False
        if ctx.guild.id in authenticated_server_ids:
            return True
        else:
            await ctx.send(
                "This server is not authenticated. Please run the `?auth` command to authenticate this server."
            )
            return False
    return True


async def is_reboot_scheduled(ctx: commands.Context) -> bool:
    if ctx.author.id in bot.owner_ids:
        return True
    if bot.reboot_scheduled:
        await ctx.reply(
            "A reboot has been scheduled. Commands are disabled until the reboot is complete.",
            silent=True,
        )
        return False
    return True


async def is_banned(ctx: commands.Context) -> bool:
    if ctx.author.id in bot.owner_ids:
        return True
    user = await crud.get_user(
        AsyncSessionLocal, schemas.User.Get(user_id=ctx.author.id)
    )
    if user and user.is_banned:
        await ctx.reply(
            "You have been banned from using QuantumKat. Please contact the bot owner for more information.",
            silent=True,
        )
        return False

    if not DiscordHelper.is_dm(ctx):
        server = await crud.get_server(
            AsyncSessionLocal, schemas.Server.Get(server_id=ctx.guild.id)
        )
        if server and server.is_banned:
            await ctx.reply(
                "This server has been banned from using QuantumKat. Please contact the bot owner for more information.",
                silent=True,
            )
            return False
    return True


# Triggered whenever the bot joins a server. We use this to add the server to the database.
@bot.event
async def on_guild_join(guild):
    await crud.add_server(
        AsyncSessionLocal,
        schemas.Server.Add(server_id=guild.id, server_name=guild.name),
    )


@bot.event
async def on_ready():
    # await init_models()

    # Add all servers the bot is in to the database on startup in case the bot was added while offline
    for guild in bot.guilds:
        try:
            if not await crud.check_server_exists(
                AsyncSessionLocal, schemas.Server.Get(server_id=guild.id)
            ):
                await crud.add_server(
                    AsyncSessionLocal,
                    schemas.Server.Add(server_id=guild.id, server_name=guild.name),
                )
        except Exception as e:
            print(e)
    # Check if the bot was rebooted and edit the message to indicate it was successful
    reboot = await crud.get_reboot_status(AsyncSessionLocal)
    if reboot and reboot.is_reboot_scheduled:
        msg_id, channel_id, guild_id = reboot.message_location
        channel = bot.get_channel(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)
        message: discord.Message = await channel.fetch_message(msg_id)
        # if reboot was more than 5 minutes ago, assume it was not successful
        if reboot.reboot_time < datetime.now() - timedelta(minutes=5):
            await message.edit(content=f"{message.content} Reboot was not successful.")
        else:
            await message.edit(content=f"{message.content} Rebooted successfully!")
        await crud.unset_reboot(AsyncSessionLocal)

    bot.appinfo = await bot.application_info()
    quantum = ["reality", "universe", "dimension", "timeline"]
    message = f"""
----------info----------
Application ID: {bot.appinfo.id}
Application name: {bot.appinfo.name}
Application owner: {bot.appinfo.owner}
Application owner IDs: {bot.owner_ids}
Latency to Discord: {int(bot.latency * 1000)}ms.
Discord.py version: {discord.__version__}
\nStarted at {datetime.now()}\n
{bot.user} has appeared from the {num2words(randint(1, 1000),
                                            to="ordinal_num")} {choice(quantum)}!"""
    quantumkat_logger.info(message)
    print(message)

    bot.add_check(is_banned)
    bot.add_check(is_reboot_scheduled)
    bot.add_check(is_authenticated)

    Thread(target=pubapi.start_api).start()


if __name__ == "__main__":
    run(setup(bot))
