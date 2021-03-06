from discord.ext import commands
import re
import asyncio
import logging
from utils import permission_node, Flipbook

log = logging.getLogger('charfred')

cronpat = re.compile('^(?P<disabled>#)*((?P<reboot>@reboot)|(?P<min>(\*/\d+|\*|(\d+,?)+))\s(?P<hour>(\*/\d+|\*|(\d+,?)+))\s(?P<day>(\*/\d+|\*|(\d+,?)+)))\s.*spiffy\s(?P<cmd>\w+)\s(?P<server>\w+)\s(?P<args>.*)>>')
every = '*/'
always = '*'


class CronReader(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.servercfg = bot.servercfg

    def _parseCron(self, crontab):
        parsedlines = []
        for l in crontab:
            if 'spiffy' not in l:
                continue
            match = cronpat.match(l)
            if not match:
                continue
            disabled, reboot, min, hour, day, cmd, server, args = match.group('disabled',
                                                                              'reboot',
                                                                              'min', 'hour',
                                                                              'day', 'cmd',
                                                                              'server', 'args')
            state = '# ' if disabled else ''
            if reboot:
                condition = 'Runs at reboot:'
                output = f'{state}{condition} {cmd} {server}'
                if args:
                    output += f' {args}'
                parsedlines.append(output)
            else:
                condition = 'Runs'
                if every in min:
                    m = f'every {min[2:]} minutes'
                elif always in min:
                    m = 'every minute'
                else:
                    m = f'at {min} minutes'

                if every in hour:
                    h = f'every {hour[2:]} hours'
                elif always in hour:
                    h = 'every hour'
                else:
                    h = f'at {hour} hours'

                if every in day:
                    d = f'every {day[2:]} days'
                elif always in day:
                    d = 'every day'
                else:
                    d = f'on these days: {day}'

                output = f'{state}{condition} {m}, {h}, {d}: {cmd} {server}'
                if args:
                    output += f' {args}'
                parsedlines.append(output)

        return parsedlines

    @commands.group(invoke_without_command=True)
    @permission_node(f'{__name__}.read')
    async def cron(self, ctx):
        """Crontab commands.

        This returns an overview of cronjobs that apply to any known minecraft
        servers managed by Charfreds \'spiffy\' script, if no subcommand was given.
        """

        log.info('Fetching current crontab...')
        proc = await asyncio.create_subprocess_exec(
            'crontab',
            '-l',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            log.info('Crontab retrieved successfully.')
        else:
            log.warning('Failed to retrieve crontab!')
            return
        crontab = stdout.decode().strip().split('\n')
        log.info('Parsing crontab...')
        spiffycron = await self.loop.run_in_executor(None, self._parseCron, crontab)
        cronFlip = Flipbook(ctx, spiffycron, entries_per_page=8, title='Spiffy Cronjobs',
                            close_on_exit=True)
        await cronFlip.flip()


def setup(bot):
    bot.register_nodes([f'{__name__}.read'])
    bot.add_cog(CronReader(bot))
