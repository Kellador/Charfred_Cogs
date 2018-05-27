import logging
import random
import asyncio
from discord.ext import commands

log = logging.getLogger('charfred')

dances = [
    [u"└|ﾟεﾟ|┐", [u"┌|ﾟзﾟ|┘", u"└|ﾟεﾟ|┐", u"┌|ﾟзﾟ|┘", u"└|ﾟεﾟ|┐", u"┌|ﾟзﾟ|┘"]],
    [u"└|∵┌|", [u"|┐∵|┘", u"└|∵┌|", u"|┐∵|┘", u"└|∵┌|", u"|┐∵|┘"]],
    [u"(o^^)o", [u"o(^^o)", u"(o^^)o", u"o(^^o)", u"(o^^)o", u"o(^^o)"]],
    [u"|o∵|o", [u"o|∵o|", u"|o∵|o", u"o|∵o|", u"|o∵|o", u"o|∵o|"]],
    [u"(ノ￣ー￣)ノ", [u"(〜￣△￣)〜", u"(ノ￣ω￣)ノ", u"(ノ￣ー￣)ノ", u"(〜￣△￣)〜", u"(ノ￣ω￣)ノ"]]
]


class entertain:
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop

    @commands.command(aliases=['partytime'])
    async def dance(self, ctx):
        dance = random.choice(dances)
        step = await ctx.send(dance[0])
        await asyncio.sleep(2, loop=self.loop)
        for move in dance[1]:
            await step.edit(content=move)
            await asyncio.sleep(2, loop=self.loop)

    @commands.command(aliases=['flip', 'table'])
    async def tableflip(self, ctx):
        unflipped = await ctx.send(u"(ಠ_ಠ) ┳━┳")
        await asyncio.sleep(2, loop=self.loop)
        await unflipped.edit(content=u"(╯ಠ_ಠ)╯︵┻━┻")


def setup(bot):
    bot.add_cog(entertain(bot))