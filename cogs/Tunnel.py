import sys
import traceback
from datetime import datetime

from discord.ext import commands


class Tunnel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return
        
        ignored_errors = (commands.CommandNotFound, commands.CheckFailure, commands.UnexpectedQuoteError, commands.InvalidEndOfQuotedStringError)

        error = getattr(error, 'original', error)

        if isinstance(error, (commands.NotOwner, commands.PrivateMessageOnly)):
            await ctx.send(f"I'm sorry {ctx.author.mention}. I'm afraid I can't do that.")
        if isinstance(error, ignored_errors):
            return
        
        else:
            print((f'''
Exception caused in command {ctx.command}
User: {ctx.author}, {ctx.author.id}
Message ID: {ctx.message.id}
Time: {datetime.now()}
            '''), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    print('Started Tunnel!')
async def setup(bot):
    await bot.add_cog(Tunnel(bot))
