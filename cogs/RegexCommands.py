from discord.ext import commands

class RegexCommands(commands.cog):
    def __init__(self, bot):
        self.bot = bot

    async def regexChecks(self, message):
        com = message.content.split(' ', 1)

        if len(com) > 1:
            dest = com[1].strip()
            destLC = com[1].lower().strip()
        else:
            dest = message.author.display_name
            destLC = ''

        if message.content