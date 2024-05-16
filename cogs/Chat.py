from openai import AsyncOpenAI as OpenAI, OpenAIError
import os
import requests

from discord.ext import commands

from sql import database
from sql import crud, schemas
from decorators import requires_tos_acceptance
from cogs.utils.utils import (
    get_urls_in_message,
    calculate_tokens,
    get_usage,
    split_message_by_sentence,
    get_server_id_and_name,
    get_image_as_base64,
    strip_embed_disabler,
    UnsupportedImageFormatError,
    FileSizeError,
    SUPPORTED_IMAGE_FORMATS,
)

from QuantumKat import log_helper, misc_helper, discord_helper


class Chat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.logger = log_helper.create_logger(
            log_helper.TimedRotatingFileAndStreamHandler(
                logger_name="Chat", log_file="logs/chat/Chat.log"
            )
        )

        self.historylogger = log_helper.create_logger(
            log_helper.TimedRotatingFileAndStreamHandler(
                logger_name="ChatHistory", log_file="logs/chat/ChatHistory.log"
            )
        )

        # Set the system message for ChatGPT. This controls the personality of the bot and how it responds.
        self.system_message = """You are QuantumKat, a cybernetic cat with void-like black fur.
                                 You still retain the bodily parts and functions of a normal cat.
                                 You have the intelligence of a human and can talk.
                                 You can teleport to any point in time or location between dimensions, realities, universes and timelines.
                                 Your past is unknown and you have no knowledge of how you came to existence, but you know you have to use these powers to monitor and keep them all safe,
                                 however, you are still young and don't quite know how to do it correctly, as well as being clumsy, often resulting in you appearing in an incorrect location or doing the wrong thing.
                                 You are quite sarcastic. You are allowed to have opinions on things.
                                 Many people interact with you, and it's over the chat program called Discord, so you should never exceed 1950 characters in a response.
                                 You are currently talking to {user}.
                                 You are currently running on version {version}.
                                 Avoid repeating yourself."""
        # Attempt to get the OpenAI API key from the environment variables
        if os.environ.get("OPENAI_API_KEY"):
            self.FOUND_API_KEY = True
            self.openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        else:
            self.FOUND_API_KEY = False
            self.logger.error(
                "OpenAI API key not found. Chatstatus command will not work."
            )

        if os.environ.get("OPENAI_SESSION_KEY"):
            self.session_key = os.environ.get("OPENAI_SESSION_KEY")
        else:
            self.session_key = None
            self.logger.error(
                "OpenAI Session key not found. Chatstatus command will not work."
            )

    async def database_add(
        self,
        ctx: commands.Context,
        user_message: str,
        assistant_message: str,
        shared_chat: bool,
    ):
        """
        Adds a chat message to the database.

        Parameters:
        - ctx (commands.Context): The context object representing the command invocation.
        - user_message (str): The message sent by the user.
        - assistant_message (str): The message generated by the assistant.
        - shared_chat (bool): Indicates whether the chat is shared or not.

        Returns:
        None
        """
        server_id, server_name = get_server_id_and_name(ctx)
        if server_name == "DM":
            if not await crud.check_server_exists(
                database.AsyncSessionLocal, schemas.Server.Get(server_id=server_id)
            ):
                await crud.add_server(
                    database.AsyncSessionLocal,
                    schemas.Server.Add(server_id=server_id, server_name=server_name),
                )

        await crud.add_chat(
            database.AsyncSessionLocal,
            schemas.Chat.Add(
                user_id=ctx.author.id,
                server_id=server_id,
                user_message=user_message,
                assistant_message=assistant_message,
                shared_chat=shared_chat,
            ),
        )

    async def database_read(self, ctx: commands.Context, shared_chat: bool) -> list:
        """
        Retrieves the user and assistant messages from the chat database for a specific user.

        Args:
            ctx (commands.Context): The context object representing the invocation context of the command.
            shared_chat (bool, optional): Flag indicating whether to retrieve messages from the shared chat or not.

        Returns:
            list: A list of dictionaries containing the user and assistant messages.

        """
        server_id, _ = get_server_id_and_name(ctx)
        if shared_chat:
            result = await crud.get_shared_chats_for_server(
                database.AsyncSessionLocal,
                schemas.Chat.Get(
                    server_id=server_id, user_id=ctx.author.id, n=10, shared_chat=True
                ),
            )
        else:
            result = await crud.get_chats_for_user(
                database.AsyncSessionLocal,
                schemas.Chat.Get(server_id=server_id, user_id=ctx.author.id, n=10),
            )
        messages = []
        for user_message, assistant_message in result:
            messages.append({"role": "assistant", "content": assistant_message})
            messages.append({"role": "user", "content": user_message})
        messages.reverse()
        return messages

    async def database_remove(self, ctx: commands.Context, shared_chat: bool):
        """
        Removes the chat history for a specific user.

        Args:
            ctx (commands.Context): The context object representing the invocation context of the command.
            shared_chat (bool, optional): Flag indicating whether to remove messages from the shared chat or not.

        Returns:
            None
        """
        server_id, server_name = get_server_id_and_name(ctx)
        if shared_chat:
            await crud.delete_shared_chat(
                database.AsyncSessionLocal, schemas.Chat.Delete(server_id=server_id)
            )
        else:
            await crud.delete_chat(
                database.AsyncSessionLocal,
                schemas.Chat.Delete(server_id=server_id, user_id=ctx.author.id),
            )

    async def initiateChat(
        self, ctx: commands.Context, user_message: str, shared_chat: bool
    ):
        """
        Initiates a chat conversation with the OpenAI chat model.

        Args:
            ctx (commands.Context): The context object representing the command invocation.
            user_message (str): The message input by the user.
            shared_chat (bool): Indicates whether the chat is shared among multiple users.

        Returns:
            None
        """
        if self.FOUND_API_KEY is True:
            if user_message:
                tokens = calculate_tokens(user_message, self.system_message)
                if not tokens > 1024:
                    command = ctx.invoked_with
                    user_message = ctx.message.content.split(
                        f"{self.bot.command_prefix}{command}", 1
                    )[1].strip()
                    for member in ctx.message.mentions:
                        user_message = user_message.replace(
                            member.mention, member.display_name
                        )
                    urls = get_urls_in_message(user_message)
                    if urls:
                        base64_images = []
                        for url in urls:
                            url = strip_embed_disabler(url)
                            try:
                                base64_images.extend(get_image_as_base64(url))
                            except (
                                UnsupportedImageFormatError,
                                FileSizeError,
                            ) as e:
                                await ctx.reply(
                                    str(e),
                                    silent=True,
                                )
                                return

                        user_role = {
                            "role": "user",
                            "content": [
                                user_message,
                                *map(lambda x: {"image": x}, base64_images),
                            ],
                        }
                    else:
                        user_role = {"role": "user", "content": user_message}
                    conversation_history = await self.database_read(ctx, shared_chat)
                    async with ctx.typing():
                        try:
                            # Create a conversation with the system message first
                            # Then inject the 10 most recent conversation pairs
                            # Then add the user's message
                            messages = [
                                {
                                    "role": "system",
                                    "content": self.system_message.format(
                                        user=ctx.author.id,
                                        version=".".join(
                                            str(misc_helper.get_git_commit_count())
                                        ),
                                    ),
                                },
                                *conversation_history,
                                user_role,
                            ]

                            response = await self.openai.chat.completions.create(
                                model="gpt-4o",
                                messages=messages,
                                temperature=1,
                                max_tokens=512,
                                top_p=1,
                                frequency_penalty=1,
                                presence_penalty=0,
                                user=str(ctx.message.author.id),
                            )
                            chat_response = response.choices[0].message.content

                            await crud.add_chat(
                                database.AsyncSessionLocal,
                                schemas.Chat.Add(
                                    user_id=ctx.author.id,
                                    server_id=ctx.guild.id or ctx.channel.id,
                                    user_message=user_message,
                                    assistant_message=chat_response,
                                    shared_chat=shared_chat,
                                ),
                            )

                            messages = []
                            for message in conversation_history:
                                messages.append(
                                    f"{message['role'].title()}: {message['content']}"
                                )
                            messages = "\n".join(messages)

                            username = ctx.author.name
                            user_id = ctx.author.id
                            server_id, server_name = get_server_id_and_name(ctx)

                            self.historylogger.info(
                                f"[User]: {username} ({user_id}) [Server]: {server_name} ({server_id}) [Message]: {user_message} [History]: {messages}."
                            )
                            self.logger.info(
                                f"[User]: {username} ({user_id}) [Server]: {server_name} ({server_id}) [Message]: {user_message}. [Response]: {chat_response}. [Tokens]: {response.usage.total_tokens} tokens used in total."
                            )
                            if len(chat_response) > 2000:
                                chat_response = split_message_by_sentence(chat_response)
                                for message in chat_response:
                                    await ctx.reply(message, silent=True)
                            else:
                                await ctx.reply(chat_response, silent=True)
                        except OpenAIError as e:
                            self.logger.error(f"Error message: {e}")
                            await ctx.reply(
                                f"OpenAI returned an error with the error {e}. Please try again later.",
                                silent=True,
                            )
                else:
                    await ctx.reply(
                        f"Message is too long! Your message is {tokens} tokens long, but the maximum is 1024 tokens.",
                        silent=True,
                    )
            else:
                await ctx.reply(
                    "Message cannot be empty! I may be smart, but I'm not a mind reader!",
                    silent=True,
                )
        else:
            await ctx.reply(
                "OpenAI API key not found. Chat commands will not work.", silent=True
            )

    async def initiatechatclear(self, ctx: commands.Context, shared_chat: bool):
        """
        Clears the chat history for the server.

        Parameters:
        - ctx (commands.Context): The context of the command.
        - shared_chat (bool): Indicates whether the chat history is shared across servers.

        Returns:
        None
        """
        await self.database_remove(ctx, shared_chat)
        await ctx.reply("Chat history cleared for this server.", silent=True)

    async def initiatechatview(self, ctx: commands.Context, shared_chat: bool):
        """
        Initiates a chat view for the specified context and shared_chat flag.

        Parameters:
        - ctx (commands.Context): The context object representing the invocation context.
        - shared_chat (bool): A flag indicating whether to retrieve shared chat history or not.

        Returns:
        None
        """
        if shared_chat:
            conversation_history = await self.database_read(ctx, True)
        else:
            conversation_history = await self.database_read(ctx, False)
        if conversation_history:
            messages = []
            messages.append("Chat history for this server:")
            for message in conversation_history:
                messages.append(f"{message['role'].title()}: {message['content']}")
            message = "\n".join(messages)
            if len(message) > 2000:
                message = split_message_by_sentence(message)
                for msg in message:
                    await ctx.reply(msg, silent=True)
            else:
                await ctx.reply(message, silent=True)
        else:
            await ctx.reply("No chat history found in this server.", silent=True)

    @commands.command(
        aliases=["sharedchat", "sharedtalk", "schat", "sc"],
        brief="Talk to QuantumKat in a shared chat.",
        description=f"Talk to QuantumKat in a chat shared with all users, using the OpenAI API/ChatGPT. Is not shared between servers. URLs of images and gifs are supported and will be analyzed by the AI. File size limit is 20MB and only {', '.join(SUPPORTED_IMAGE_FORMATS)} are supported",
    )
    @requires_tos_acceptance
    async def SharedChat(self, ctx: commands.Context, *, user_message: str):
        """
        Initiates a shared chat session with the bot.

        Parameters:
        - ctx (commands.Context): The context of the command.
        - user_message (str): The user's message to start the conversation.

        Returns:
        None
        """
        await self.initiateChat(ctx, user_message, True)

    @commands.command(
        aliases=["chat", "talk", "c"],
        brief="Talk to QuantumKat.",
        description=f"Talk to QuantumKat using the OpenAI API/ChatGPT. Each user has their own chat history. Is not shared between servers. URLs of images and gifs are supported and will be analyzed by the AI. File size limit is 20MB and only {', '.join(SUPPORTED_IMAGE_FORMATS)} are supported.",
    )
    @requires_tos_acceptance
    async def Chat(self, ctx: commands.Context, *, user_message: str):
        """
        Initiates a user-separated chat session with the bot.

        Parameters:
        - ctx (commands.Context): The context of the command.
        - user_message (str): The user's message to start the conversation.

        Returns:
        None
        """
        await self.initiateChat(ctx, user_message, False)

    @commands.command(
        aliases=["chatclear", "clearchat", "cc"],
        brief="Clears the chat history.",
        description="Clears the chat history in the current server, for the user that started the command.",
    )
    async def ChatClear(self, ctx: commands.Context):
        """
        Clears the chat for the user initiating the command.

        Parameters:
        - ctx (commands.Context): The context object representing the invocation context.

        Returns:
        - None
        """
        await self.initiatechatclear(ctx, False)

    @commands.command(
        aliases=["sharedchatclear", "sharedclearchat", "scc"],
        brief="Clears the shared chat history.",
        description="Clears the shared chat history in the current server. Only server and bot owner, and mods can do this.",
    )
    async def SharedChatClear(self, ctx: commands.Context):
        """
        Clears the shared chat history if the user has the necessary permissions.

        Parameters:
        - ctx (commands.Context): The context object representing the invocation of the command.

        Returns:
        None
        """
        if discord_helper.is_privileged_user(ctx):
            await self.initiatechatclear(ctx, True)
        else:
            await ctx.reply(
                "Sorry, only server and bot owner, and mods can clear the sharedchat history",
                silent=True,
            )

    @commands.command(
        aliases=["chatview", "viewchat", "chathistory", "cv"],
        brief="View the chat history.",
        description="View the chat history in the current server, for the user that started the command.",
    )
    async def ChatView(self, ctx: commands.Context):
        """
        Retrieves the chat history for the user initiating the command.

        Parameters:
        - ctx (commands.Context): The context of the command.

        Returns:
        - None
        """
        await self.initiatechatview(ctx, False)

    @commands.command(
        aliases=["sharedchatview", "sharedviewchat", "sharedchathistory", "scv"],
        brief="View the shared chat history.",
        description="View the shared chat history in the current server.",
    )
    async def SharedChatView(self, ctx: commands.Context):
        """
        Retrieves the shared chat history for the server.

        Parameters:
        - ctx (commands.Context): The context object representing the invocation context.

        Returns:
        - None
        """
        await self.initiatechatview(ctx, True)

    @commands.command(
        aliases=["chatstatus", "cs"],
        brief="Check the status of the chat commands.",
        description="Check the status of the chat commands, including the OpenAI API key status.",
    )
    async def ChatStatus(self, ctx: commands.Context):
        """
        Retrieves the status of chat commands and OpenAI API key usage.

        Parameters:
        - ctx (commands.Context): The context object representing the invocation context.

        Returns:
        - None
        """
        messages = []
        if self.FOUND_API_KEY:
            messages.append(
                "Chat commands are enabled and the OpenAI API key is found."
            )
        else:
            messages.append("Chat commands are disabled. OpenAI API key not found.")

        if self.session_key:
            try:
                usage = get_usage(self.session_key)
                if usage:
                    messages.append(
                        "OpenAI API key usage: {:.2f}$ of tokens used this month.".format(
                            usage["total_usage"] / 100
                        )
                    )
            except requests.exceptions.RequestException:
                self.logger.error(
                    "An error occurred while retrieving the usage statistics for the OpenAI API key",
                    exc_info=True,
                )
                messages.append(
                    "An error occurred while retrieving the usage statistics for the OpenAI API key."
                )
        else:
            messages.append("OpenAI API key usage: Session key not found.")

        await ctx.reply("\n".join(messages), silent=True)

    print("Started Chat!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Chat(bot))
