import logging
import asyncio

from pathlib import Path

from discord import File
from discord.ext import commands

from utils import permission_node
from .utils import isUp, sendCmd

log = logging.getLogger('charfred')


class TellmeHelper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.servercfg = bot.servercfg

    def gettellmereport(self, server):
        """Retrieves the filename of the nth latest tellme file
        for a given server, in addition to the date of last modification.
        """

        tellmedir = Path(self.servercfg['serverspath'] + f'/{server}/config/tellme')
        _, rpath = max((r.stat().st_mtime, r) for r in tellmedir.iterdir())
        return rpath

    async def uploadreport(self, ctx, server):
        rpath = await self.loop.run_in_executor(None, self.gettellmereport, server)
        if not rpath:
            log.warning('Failed to find report file!')
            await ctx.sendmarkdown('< No report file found! >')
        else:
            log.info('Uploading TellMe report to Discord...')
            rfile = File(rpath)
            await ctx.send('```markdown\n# Here\'s the report! o7 :\n```', file=rfile)

    async def tellmecommand(self, ctx, server, ttype, tid=None):
        """Runs the tellme command via screen."""

        if server not in self.servercfg['servers']:
            await ctx.sendmarkdown(f'< I have no knowledge of {server}! >')
            return

        if not isUp(server):
            await ctx.sendmarkdown(f'< {server} is not up! >')
            return

        if tid:
            cmd = f'tellme locate {ttype} dump all-loaded-chunks {tid}'
        else:
            cmd = f'tellme loaded {ttype}' + (' dump' if ttype == 'chunks' else ' all dump')

        async with ctx.typing():
            log.info(f'Running tellme command: \"{cmd}\" on {server}.')
            await sendCmd(self.loop, server, cmd)
            await ctx.sendmarkdown(f'# Running TellMe command:\n  \"{cmd}\"')
            await asyncio.sleep(2, loop=self.loop)
            await self.uploadreport(ctx, server)

    @commands.group(invoke_without_command=False, aliases=['giveittomenow'])
    @permission_node(f'{__name__}.tellme')
    async def tellme(self, ctx):
        """Tellme plugin commands."""

        pass

    @tellme.command(aliases=['te'])
    @permission_node(f'{__name__}.tellme')
    async def tileentities(self, ctx, server: str):
        """Retrieves list of all loaded tileentities via TellMe."""

        await self.tellmecommand(ctx, server, 'tileentities-all')

    @tellme.command(aliases=['e'])
    @permission_node(f'{__name__}.tellme')
    async def entities(self, ctx, server: str):
        """Retrieves list of all loaded entities via TellMe."""

        await self.tellmecommand(ctx, server, 'entities-all')

    @tellme.command(aliases=['c'])
    @permission_node(f'{__name__}.tellme')
    async def chunks(self, ctx, server: str):
        """Retrieves list of all loaded chunks via TellMe."""

        await self.tellmecommand(ctx, server, 'chunks')

    @tellme.command()
    @permission_node(f'{__name__}.tellme')
    async def locate(self, ctx, server: str, targettype: str, targetid: str):
        """Finds specified block, tile entity, or entity via TellMe.

        Requires the type: block | te | entity
        and the ingame-id.
        """

        if targettype not in ('block', 'te', 'entity'):
            await ctx.sendmarkdown(f'< {targettype} is not a valid target type! >')
            return

        await self.tellmecommand(ctx, server, targettype, targetid)

    @tellme.command()
    @permission_node(f'{__name__}.tellme')
    async def download(self, ctx, server: str):
        """Downloads the latest TellMe report from given server."""

        await self.uploadreport(ctx, server)


def setup(bot):
    bot.register_nodes([f'{__name__}.tellme'])
    bot.add_cog(TellmeHelper(bot))
