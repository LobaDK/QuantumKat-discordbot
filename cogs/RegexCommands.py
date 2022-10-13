from discord.ext import commands
import re

class RegexCommands(commands.cog):
    def __init__(self, bot):
        self.bot = bot

    async def regexChecks(self, message):
        pettRegex = re.compile(r"^!(p+e+t+(s*))", re.IGNORECASE)
        com = message.content.split(' ', 1)

        if len(com) > 1:
            dest = com[1].strip()
            destLC = com[1].lower().strip()
        else:
            dest = message.author.display_name
            destLC = ''

        test = pettRegex.match(com[0])
        if test:
            pett, plural = test.groups()
            if plural == '':
                plural = 's'
            else: plural = ''

            