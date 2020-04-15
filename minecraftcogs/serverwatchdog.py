from discord.ext import commands
from discord.utils import find
import asyncio
import logging
import re
from time import strftime, localtime, time
from threading import Event
from utils import Config, permission_node
from .utils import isUp, getProc, serverStart, getcrashreport, parsereport, formatreport

log = logging.getLogger('charfred')

cronpat = re.compile(r'^(?P<disabled>#)*((?P<reboot>@reboot)|(?P<min>(\*/\d+|\*|(\d+,?)+))\s(?P<hour>(\*/\d+|\*|(\d+,?)+))\s(?P<day>(\*/\d+|\*|(\d+,?)+)))\s.*spiffy\s(?P<cmd>\w+)\s(?P<server>\w+)\s(?P<args>.*)>>')
every = '*/'
always = '*'


class Watchdog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.servercfg = bot.servercfg
        self.watchdogs = {}
        self.watchcfg = Config(f'{bot.dir}/configs/watchcfg.json',
                               load=True, loop=self.loop)
        if 'notify' not in self.watchcfg:
            self.watchcfg['notify'] = '@here'

    def cog_unload(self):
        if self.watchdogs:
            for fut, event in self.watchdogs.values():
                event.set()

    @commands.group(invoke_without_command=True)
    @permission_node(f'{__name__}.watchdog')
    async def watchdog(self, ctx):
        """Server process watchdog commands.

        This returns a list of all active watchdogs,
        if no subcommand was given.
        """

        for server, wd in self.watchdogs.items():
            if wd[0].done():
                await ctx.sendmarkdown(f'< {server} watchdog inactive! >')
            else:
                await ctx.sendmarkdown(f'# {server} watchdog active!')

    @watchdog.command(aliases=['blame'])
    @permission_node(f'{__name__}.watchdog')
    async def setmention(self, ctx, mentionee: str):
        """Set who to mention for crash notification."""

        log.info(f'Setting role to mention to: {mentionee}.')

        role = find(lambda r: r.name == mentionee, ctx.guild.roles)
        if role:
            self.watchcfg['notify'] = role.mention
            await ctx.sendmarkdown(f'# Set role to mention to: {mentionee}!\n'
                                   '> They will be notified if a crash is suspected,\n'
                                   '> given that mentioning is enabled.')
            await self.watchcfg.save()
            log.info('Watchdog cfg saved!')
        else:
            await ctx.sendmarkdown(f'< {mentionee} is not a valid role! >')
            log.warning('Role could not be found, role to mention unchanged.')

    async def _wdstart(self, ctx, server):
        if server in self.watchdogs and not self.watchdogs[server][0].done():
            log.info(f'{server} watchdog active.')
            await ctx.sendmarkdown('# Watchdog already active!')
        else:
            if server not in self.servercfg['servers']:
                log.warning(f'{server} has been misspelled or not configured!')
                await ctx.sendmarkdown(f'< {server} has been misspelled or not configured! >')
                return

            if isUp(server):
                log.info('Starting watchdog on online server.')
                await ctx.sendmarkdown(f'# {server} is up and running.', deletable=False)
            else:
                log.info('Starting watchdog on offline server.')
                await ctx.sendmarkdown(f'< {server} is not running. >', deletable=False)

            async def serverGone(crashed, report=None):
                if crashed:
                    await ctx.send(
                        f'{self.watchcfg["notify"]}\n'
                        '```markdown\n'
                        f'< {strftime("%H:%M", localtime())} : {server} crashed! >\n'
                        '```',
                        deletable=False
                    )
                    for c in report:
                        await asyncio.sleep(1, loop=self.loop)
                        await ctx.sendmarkdown(c)
                else:
                    await ctx.sendmarkdown(f'> {strftime("%H:%M", localtime())} : {server} is gone!\n'
                                           '> Watching for it to return...', deletable=False)

            async def serverBack():
                await ctx.sendmarkdown('# ' + strftime("%H:%M") + f' {server} is back online!\n'
                                       '> Continuing watch!', deletable=False)

            async def watchGone():
                await ctx.sendmarkdown(f'> Ended watch on {server}!', deletable=False)

            async def startServer():
                # TODO: Remove message informing about the change from 'react to restart' to 'react to abort'
                abortPrompt = await ctx.sendmarkdown(
                    '< IMPORTANT NOTE: The purpose of this prompt has changed, please read it carefully! >\n\n'
                    f'# Attempting to start {server} back up again in 90 seconds!\n'
                    '< Please react to this message with ✋ to abort! >',
                    deletable=False
                )
                await abortPrompt.add_reaction('✋')

                def abortcheck(reaction, user):
                    if reaction.message.id != abortPrompt.id:
                        return False
                    return str(reaction.emoji) == '✋' and not user.bot

                log.info(f'Prompting {server} start abort... 90 seconds.')
                try:
                    await self.bot.wait_for('reaction_add', timeout=90, check=abortcheck)
                except asyncio.TimeoutError:
                    log.info('Prompt timed out.')
                    await abortPrompt.clear_reactions()
                    await abortPrompt.edit(content='```markdown\n> Prompt to abort'
                                           ' timed out!\n```')
                    await asyncio.sleep(5, loop=self.loop)
                    if isUp(server):
                        log.info(f'{server} is already back!')
                        await abortPrompt.edit(content=f'```markdown\n> {server} is already back!\n```')
                    else:
                        log.info(f'Starting {server}')
                        await abortPrompt.edit(content=f'```markdown\n> Starting {server}...\n```')
                        await serverStart(server, self.servercfg, self.loop)
                else:
                    await abortPrompt.clear_reactions()
                    await abortPrompt.edit(content=f'```markdown\n> Startup of {server} aborted!\n```')

            def watchDone(future):
                log.info(f'WD: Ending watch on {server}.')
                if future.exception():
                    log.warning(f'WD: Exception in watchdog for {server}!')
                    raise future.exception()
                asyncio.run_coroutine_threadsafe(watchGone(), self.loop)

            def watch(event):
                log.info(f'WD: Starting watch on {server}.')
                serverProc = getProc(server)
                if serverProc and serverProc.is_running():
                    lastState = True
                else:
                    lastState = False
                while not event.is_set():
                    if lastState:
                        if not serverProc.is_running():
                            log.info(f'WD: {server} is gone!')
                            lastState = False
                            now = time()
                            rpath, mtime = getcrashreport(server, self.servercfg['serverspath'])
                            if mtime > (now - 60):
                                crashed = True
                                ctime, desc, strace, flav, lev, bl, ph = parsereport(rpath)
                                report = formatreport(
                                    rpath, ctime, desc, flav, strace, lev, bl, ph
                                )
                                coro = serverGone(crashed, report)
                            else:
                                crashed = False
                                coro = serverGone(crashed)
                            asyncio.run_coroutine_threadsafe(coro, self.loop)
                            if crashed:
                                asyncio.run_coroutine_threadsafe(startServer(), self.loop)
                            event.wait(timeout=30)
                        event.wait(timeout=20)
                    else:
                        serverProc = getProc(server)
                        if serverProc and serverProc.is_running():
                            log.info(f'WD: {server} is back online!')
                            lastState = True
                            asyncio.run_coroutine_threadsafe(serverBack(), self.loop)
                            event.wait(timeout=20)
                        else:
                            event.wait(timeout=30)
                else:
                    return

            event = Event()
            watchFuture = self.loop.run_in_executor(None, watch, event)
            watchFuture.add_done_callback(watchDone)
            self.watchdogs[server] = (watchFuture, event)
            await ctx.sendmarkdown('# Watchdog activated!', deletable=False)

    @watchdog.command(name='activate', aliases=['start', 'watch'])
    @permission_node(f'{__name__}.watchdog')
    async def wdstart(self, ctx, *servers: str):
        """Start the process watchdog for a server."""

        for server in servers:
            await self._wdstart(ctx, server)

    @watchdog.command(name='deactivate', aliases=['stop', 'unwatch'])
    @permission_node(f'{__name__}.watchdog')
    async def wdstop(self, ctx, server: str):
        """Stop the process watchdog for a server."""

        if server in self.watchdogs and not self.watchdogs[server][0].done():
            watcher = self.watchdogs[server]
            watcher[1].set()
            await ctx.sendmarkdown(f'> Terminating {server} watchdog...', deletable=False)
        else:
            if server not in self.servercfg['servers']:
                log.warning(f'{server} has been misspelled or not configured!')
                await ctx.sendmarkdown(f'< {server} has been misspelled or not configured! >')
            else:
                await ctx.sendmarkdown('# Watchdog already inactive!', deletable=False)


def setup(bot):
    if not hasattr(bot, 'servercfg'):
        default = {
            "servers": {}, "serverspath": "NONE", "backupspath": "NONE", "oldTimer": 1440
        }
        bot.servercfg = Config(f'{bot.dir}/configs/serverCfgs.toml',
                               default=default,
                               load=True, loop=bot.loop)
    bot.register_nodes([f'{__name__}.watchdog'])
    bot.add_cog(Watchdog(bot))
