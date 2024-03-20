from openai import AsyncOpenAI as OpenAI, OpenAIError
import logging
import tiktoken
import os
import sqlite3
import requests
import datetime
import calendar

from discord.ext import commands


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.db_conn = bot.db_conn

        self.logger = logging.getLogger('discord.Chat')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename='logs/chat.log', encoding='utf-8', mode='a')
        date_format = '%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', datefmt=date_format, style='{')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self.historylogger = logging.getLogger('discord.ChatHistory')
        self.historylogger.setLevel(logging.INFO)
        history_handler = logging.FileHandler(filename='logs/chat_history.log', encoding='utf-8', mode='a')
        history_handler.setFormatter(formatter)
        self.historylogger.addHandler(history_handler)

        # Set the model encoding for tiktoken
        self.encoding = tiktoken.encoding_for_model('gpt-3.5-turbo')
        # Set the system message for ChatGPT. This controls the personality of the bot and how it responds.
        self.system_message = "You are QuantumKat, a cybernetic cat with void-like black fur. You have the intelligence of a human and can talk. You can teleport to any point in time or location between dimensions, realities, universes and timelines. while your past is unknown and you have no knowledge of how you came to existence, you know you have to use these powers to monitor and keep them all safe, however, you are still young and don't quite know how to do it correctly, as well as being clumsy, often resulting in you appearing in an incorrect location or doing the wrong thing. You are quite sarcastic. You are allowed to have opinions on things."
        # Attempt to get the OpenAI API key from the environment variables
        if os.environ.get('OPENAI_API_KEY'):
            self.FOUND_API_KEY = True
            self.openai = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        else:
            self.FOUND_API_KEY = False
            self.logger.error("OpenAI API key not found. Chatstatus command will not work.")

        if os.environ.get('OPENAI_SESSION_KEY'):
            self.session_key = os.environ.get('OPENAI_SESSION_KEY')
            self.openai = OpenAI(api_key=os.environ.get('OPENAI_SESSION_KEY'))
        else:
            self.session_key = None
            self.logger.error("OpenAI Session key not found. Chatstatus command will not work.")

    async def calculate_tokens(self, user_message: str) -> int:
        """
        Calculates the number of tokens in a given user message.

        Parameters:
        - user_message (str): The user message to calculate tokens for.

        Returns:
        - int: The number of tokens in the user message.
        """
        messages = [user_message, self.system_message]
        tokens = 0
        for message in messages:
            tokens += len(self.encoding.encode(message))
        return tokens

    async def database_add(self, ctx: commands.Context, user_message: str, assistant_message: str, shared_chat: bool):
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
        user_id = ctx.author.id
        user_name = ctx.author.name
        server_id, server_name = await self.get_server_id_and_name(ctx)
        sql = "INSERT INTO chat (user_id, user_name, server_id, server_name, user_message, assistant_message, shared_chat) VALUES (?, ?, ?, ?, ?, ?, ?)"
        params = (user_id, user_name, server_id, server_name, user_message, assistant_message, shared_chat)
        try:
            self.db_conn.execute(sql, params)
            self.db_conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"An error occurred while adding a chat message to the database: {e}")
            await ctx.reply("An error occurred while adding the chat message to the database.", silent=True)

    async def database_read(self, ctx: commands.Context, shared_chat: bool) -> list:
        """
        Retrieves the user and assistant messages from the chat database for a specific user.

        Args:
            ctx (commands.Context): The context object representing the invocation context of the command.
            shared_chat (bool, optional): Flag indicating whether to retrieve messages from the shared chat or not.

        Returns:
            list: A list of dictionaries containing the user and assistant messages.

        """
        user_id = ctx.author.id
        server_id, _ = await self.get_server_id_and_name(ctx)
        if shared_chat:
            sql = "SELECT user_message, assistant_message FROM chat WHERE server_id = ? AND shared_chat = 1 ORDER BY id DESC LIMIT 10"
            params = (server_id,)
        else:
            sql = "SELECT user_message, assistant_message FROM chat WHERE user_id = ? AND server_id = ? AND shared_chat = 0 ORDER BY id DESC LIMIT 10"
            params = (user_id, server_id)
        try:
            rows = self.db_conn.execute(sql, params).fetchall()
        except sqlite3.Error as e:
            self.logger.error(f"An error occurred while reading chat messages from the database: {e}")
            await ctx.reply("An error occurred while reading chat messages from the database.", silent=True)
            return []
        messages = []
        for user_message, assistant_message in rows:
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
        user_id = ctx.author.id
        server_id, _ = await self.get_server_id_and_name(ctx)
        if shared_chat:
            sql = "DELETE FROM chat WHERE server_id = ? AND shared_chat = 1"
            params = (server_id,)
        else:
            sql = "DELETE FROM chat WHERE user_id = ? AND server_id = ? AND shared_chat = 0"
            params = (user_id, server_id)
        try:
            self.db_conn.execute(sql, params)
            self.db_conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"An error occurred while removing chat messages from the database: {e}")
            await ctx.reply("An error occurred while removing chat messages from the database.", silent=True)

    async def get_usage(self, ctx: commands.Context) -> dict:
        """
        Retrieves the usage statistics for the OpenAI API key.

        Args:
            ctx (commands.Context): The context object representing the invocation context of the command.

        Returns:
            dict: A dictionary containing the usage statistics for the OpenAI API key.
        """
        month = str(datetime.datetime.month)
        if len(month) == 1:
            month = f"0{month}"
        year = str(datetime.datetime.year)
        last_day = str(calendar.monthrange(year, month)[1])
        try:
            response = requests.get(f"https://api.openai.com/v1/usage?end_date={year}-{month}-01&start_date={year}-{month}-{last_day}", headers={"Authorization": self.session_key})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"An error occurred while retrieving the usage statistics for the OpenAI API key: {e}")
            await ctx.reply("An error occurred while retrieving the usage statistics for the OpenAI API key.", silent=True)
            return {}

    async def get_server_id_and_name(self, ctx: commands.Context) -> tuple:
        """
        Retrieves the server ID and name from the context object.

        Args:
            ctx (commands.Context): The context object representing the invocation context of the command.

        Returns:
            tuple: A tuple containing the server ID and name.
        """
        if ctx.guild is not None:
            server_id = ctx.guild.id
            server_name = ctx.guild.name
        else:
            server_id = ctx.channel.id
            server_name = 'DM or Group Chat'
        return server_id, server_name

    async def initiateChat(self, ctx: commands.Context, user_message: str, shared_chat: bool):
        if self.FOUND_API_KEY is True:
            if user_message:
                tokens = await self.calculate_tokens(user_message)
                if not tokens > 256:
                    command = ctx.invoked_with
                    user_message = ctx.message.clean_content.split(f"{self.bot.command_prefix}{command}", 1)[1].strip()
                    for member in ctx.message.mentions:
                        user_message = user_message.replace('@' + member.mention, member.display_name)
                    conversation_history = await self.database_read(ctx, shared_chat)
                    async with ctx.typing():
                        try:
                            # Create a conversation with the system message first
                            # Then inject the 10 most recent conversation pairs
                            # Then add the user's message
                            messages = [
                                {
                                    "role": "system",
                                    "content": self.system_message
                                },
                                *conversation_history,
                                {
                                    "role": "user",
                                    "content": user_message
                                }
                            ]

                            response = await self.openai.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=messages,
                                temperature=1,
                                max_tokens=512,
                                top_p=1,
                                frequency_penalty=0,
                                presence_penalty=0
                            )
                            chat_response = response.choices[0].message.content

                            await self.database_add(ctx, user_message, chat_response, shared_chat)

                            messages = []
                            for message in conversation_history:
                                messages.append(f"{message['role'].title()}: {message['content']}")
                            messages = "\n".join(messages)

                            username = ctx.author.name
                            user_id = ctx.author.id
                            server_id, server_name = await self.get_server_id_and_name(ctx)

                            self.historylogger.info(f'[User]: {username} ({user_id}) [Server]: {server_name} ({server_id}) [Message]: {user_message} [History]: {messages}.')
                            self.logger.info(f'[User]: {username} ({user_id}) [Server]: {server_name} ({server_id}) [Message]: {user_message}. [Response]: {chat_response}. [Tokens]: {response.usage.total_tokens} tokens used in total.')
                            await ctx.reply(chat_response, silent=True)
                        except OpenAIError as e:
                            self.logger.error(f'HTTP status code: {e.http_status}, Error message: {e}')
                            await ctx.reply(f"OpenAI returned an error with the status code {e.http_status}. Please try again later.", silent=True)
                else:
                    await ctx.reply(f"Message is too long! Your message is {tokens} tokens long, but the maximum is 256 tokens.", silent=True)
            else:
                await ctx.reply("Message cannot be empty! I may be smart, but I'm not a mind reader!", silent=True)
        else:
            await ctx.reply("OpenAI API key not found. Chat commands will not work.", silent=True)

    async def initiatechatclear(self, ctx: commands.Context, shared_chat: bool):
        await self.database_remove(ctx, shared_chat)
        await ctx.reply("Chat history cleared for this server.", silent=True)

    async def initiatechatview(self, ctx: commands.Context, shared_chat: bool):
        if shared_chat:
            conversation_history = await self.database_read(ctx, True)
        else:
            conversation_history = await self.database_read(ctx, False)
        if conversation_history:
            messages = []
            messages.append("Chat history for this server:")
            for message in conversation_history:
                messages.append(f"{message['role'].title()}: {message['content']}")
            await ctx.reply("\n".join(messages), silent=True)
        else:
            await ctx.reply("No chat history found in this server.", silent=True)

    @commands.command(aliases=['sharedchat', 'sharedtalk', 'schat', 'sc'], brief='Talk to QuantumKat in a shared chat.', description='Talk to QuantumKat in a chat shared with all users, using the OpenAI API/ChatGPT. Is not shared between servers.')
    async def SharedChat(self, ctx: commands.Context, *, user_message=""):
        await self.initiateChat(ctx, user_message, True)

    @commands.command(aliases=['chat', 'talk', 'c'], brief='Talk to QuantumKat.', description='Talk to QuantumKat using the OpenAI API/ChatGPT. Each user has their own chat history. Is not shared between servers.')
    async def Chat(self, ctx: commands.Context, *, user_message=""):
        await self.initiateChat(ctx, user_message, False)

    @commands.command(aliases=['chatclear', 'clearchat', 'cc'], brief='Clears the chat history.', description='Clears the chat history in the current server, for the user that started the command.')
    async def ChatClear(self, ctx: commands.Context):
        await self.initiatechatclear(ctx, False)

    @commands.command(aliases=['sharedchatclear', 'sharedclearchat', 'scc'], brief='Clears the shared chat history.', description='Clears the shared chat history in the current server. Only server and bot owner, and mods can do this.')
    async def SharedChatClear(self, ctx: commands.Context):
        application = await self.bot.application_info()
        if (
            ctx.author.id == ctx.guild.owner.id
            or ctx.author.id == application.owner.id
            or ctx.author.guild_permissions.administrator
            or ctx.author.guild_permissions.moderate_members
        ):
            await self.initiatechatclear(ctx, True)
        else:
            await ctx.reply('Sorry, only server and bot owner, and mods can clear the sharedchat history', silent=True)

    @commands.command(aliases=['chatview', 'viewchat', 'chathistory', 'cv'], brief='View the chat history.', description='View the chat history in the current server, for the user that started the command.')
    async def ChatView(self, ctx: commands.Context):
        await self.initiatechatview(ctx, False)

    @commands.command(aliases=['sharedchatview', 'sharedviewchat', 'sharedchathistory', 'scv'], brief='View the shared chat history.', description='View the shared chat history in the current server.')
    async def SharedChatView(self, ctx: commands.Context):
        await self.initiatechatview(ctx, True)

    @commands.command(aliases=['chatstatus', 'cs'], brief='Check the status of the chat commands.', description='Check the status of the chat commands, including the OpenAI API key status.')
    async def ChatStatus(self, ctx: commands.Context):
        messages = []
        if self.FOUND_API_KEY:
            messages.append("Chat commands are enabled and the OpenAI API key is found.")
        else:
            messages.append("Chat commands are disabled. OpenAI API key not found.")
        if self.session_key:
            usage = await self.get_usage(ctx)
            if usage:
                messages.append("OpenAI API key usage: {:.2f}$ of tokens used this month.".format(usage['total_usage'] / 100))

        await ctx.reply("\n".join(messages), silent=True)

    print("Started Chat!")


async def setup(bot):
    await bot.add_cog(Chat(bot))
