from discord.ext import commands
import sys
import traceback
# import random

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

        if isinstance(error, ignored_errors):
            return
        
        else:
            print((f'Ignoring exception in command {ctx.command}'), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    
    # @commands.Cog.listener()
    # async def on_message(self, message):
    #     if self.bot.user.mentioned_in(message):
    #         answer = random.choice(['yes','no'])
    #         await message.channel.send(answer)
def setup(bot):
    bot.add_cog(Tunnel(bot))