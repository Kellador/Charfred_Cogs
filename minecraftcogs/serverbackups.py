from discord.ext import commands
from discord import Color
import logging
import os
import tarfile
from shutil import rmtree
from utils import Config, permission_node, Flipbook
from .utils import isUp

log = logging.getLogger('charfred')


class ServerBackups(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.servercfg = bot.servercfg

    @commands.group()
    @permission_node(f'{__name__}.backup')
    async def backup(self, ctx):
        """Minecraft server backup commands."""

        pass

    @backup.command(aliases=['listAll'])
    async def list(self, ctx, server: str):
        """List available backups for a specified server."""

        if server not in self.servercfg['servers']:
            log.warning(f'{server} has been misspelled or not configured!')
            await ctx.sendmarkdown(f'< {server} has been misspelled or not configured! >')
            return
        bpath = self.servercfg['backupspath']
        availablebackups = [archive for archive in os.listdir(f'{bpath}/{server}')
                            if os.path.isfile(f'{bpath}/{server}/{archive}') and
                            archive.endswith('.tar.gz')]
        availablebackups.sort()
        backupsbook = Flipbook(ctx, availablebackups, entries_per_page=8,
                               title=f'Backups for {server}', color=Color.blurple())
        await backupsbook.flip()

    @backup.group()
    @permission_node(f'{__name__}.apply')
    async def apply(self, ctx):
        """Backup application commands."""

        pass

    def getbackupfile(self, server, part):
        bpath = self.servercfg['backupspath']
        backup = [file for file in os.listdir(f'{bpath}/{server}')
                  if os.path.isfile(f'{bpath}/{server}/{file}') and
                  file.endswith('.tar.gz') and part in file]
        if len(backup) > 1:
            return None
        else:
            return f'{bpath}/{server}/{backup[0]}'

    @apply.command()
    async def full(self, ctx, server: str, backup: str, world: str=None):
        """Applies a full world backup.

        All world files currently in place will be overwritten.

        The 'backup' argument takes the filename for the backup
        to be used, NOT the path to it!;
        However you do not need to put in the whole file name,
        any unique part of the file name will suffice,
        such as the datetime stamp of it.
        """

        backupfile = self.getbackupfile(server, backup)
        if backupfile is None:
            log.warning(f'{backup} did not match any backups for {server}!')
            await ctx.sendmarkdown(f'< {backup} did not match any backups for {server}! >')
            return
        log.info(f'Preparing for full backup application using {backupfile}!')
        await ctx.sendmarkdown(f'Using {backupfile}')
        r, _, timedout = await ctx.promptconfirm('Would you like to proceed?')
        if timedout:
            return
        if r:
            log.info('Confirmed!')
            if isUp(server):
                log.warning(f'{server} still up, cannot proceed!')
                await ctx.sendmarkdown(f'{server} is still up, cannot proceed!')
                return
            serverpath = self.servercfg['serverspath']
            if world is None:
                world = self.servercfg['servers'][server]['worldname']
            worldpath = f'{serverpath}/{server}/{world}'
            try:
                log.info(f'Deleting {worldpath}')
                rmtree(worldpath)
            except Exception as e:
                log.error(e + '\nBackup application failed!')
                return
            else:
                log.info(f'{worldpath} deleted!')
                await ctx.sendmarkdown('This next step might take some time...')

                def extracthelper():
                    with tarfile.open(backupfile, 'r:gz') as tf:
                        tf.extractall(f'{serverpath}/{server}/')

                await self.loop.run_in_executor(None, extracthelper)
                log.info('World folder extracted from backup and placed!')
                await ctx.sendmarkdown('World folder replaced, job done!')
        else:
            log.info('Aborted!')

    @apply.command()
    async def partial(self, ctx, server: str, backup: str, *regions):
        """Applies a partial world backup,
        replacing only specified regions.

        All specified region files currently in place will be
        overwritten.

        The 'backup' argument takes the filename for the backup
        to be used, NOT the path to it!;
        However you do not need to put in the whole file name,
        any unique part of the file name will suffice,
        such as the datetime stamp of it.

        The 'regions' argument takes one or many region file names;
        These need to be full filenames, such as 'r.1.1.mca'.
        """

        backupfile = self.getbackupfile(server, backup)
        if backupfile is None:
            log.warning(f'{backup} did not match any backups for {server}!')
            await ctx.sendmarkdown(f'< {backup} did not match any backups for {server}! >')
            return
        log.info(f'Preparing for partial backup application using {backupfile}!')
        await ctx.sendmarkdown(f'Using {backupfile}')
        log.info('Regions to be extracted:')
        for r in regions:
            log.info(r)
        await ctx.sendmarkdown('Regions that will be extracted:\n' +
                               '\n'.join(regions))
        r, _, timedout = await ctx.promptconfirm('Would you like to proceed?')
        if timedout:
            return
        if r:
            log.info('Confirmed!')
            if isUp(server):
                log.warning(f'{server} still up, cannot proceed!')
                await ctx.sendmarkdown(f'{server} is still up, cannot proceed!')
                return
            serverpath = self.servercfg['serverspath']
            world = self.servercfg['servers'][server]['worldname']
            regionpath = f'{serverpath}/{server}/{world}/region'
            deleted = []
            failed = False
            for r in regions:
                try:
                    os.remove(f'{regionpath}/{r}')
                    log.info(f'Deleting {regionpath}/{r}')
                except Exception as e:
                    log.error(e + f'\nDeletion of {r} failed!')
                    failed = True
                    await ctx.sendmarkdown(f'Deletion of {r} failed!')
                else:
                    deleted.append(r)
            if failed:
                await ctx.sendmarkdown('There were some errors encountered '
                                       'during deletion!\nThe following regions '
                                       'were deleted successfully however:\n' +
                                       '\n'.join(deleted) + '\nPartial backup '
                                       'application will continue, but only the '
                                       'successfully deleted regions will be '
                                       'replaced, please investigate why the '
                                       'other regions failed to be deleted '
                                       'manually!')
            else:
                await ctx.sendmarkdown('All specified regions successfully '
                                       'deleted! Continuing with replacement...')

            def extracthelper():
                with tarfile.open(backupfile, 'r:gz') as tf:
                    for r in regions:
                        tf.extract(f'{world}/region/{r}', path=f'{serverpath}/{server}')

            await self.loop.run_in_executor(None, extracthelper)
            log.info('Regions extracted from backup and placed!')
            await ctx.sendmarkdown('Regions replaced, job done!')
        else:
            log.info('Aborted!')


def setup(bot):
    if not hasattr(bot, 'servercfg'):
        default = {
            "servers": {}, "serverspath": "NONE", "backupspath": "NONE", "oldTimer": 1440
        }
        bot.servercfg = Config(f'{bot.dir}/configs/serverCfgs.toml',
                               default=default,
                               load=True, loop=bot.loop)
    permission_nodes = ['backup', 'apply']
    bot.register_nodes([f'{__name__}.{node}' for node in permission_nodes])
    bot.add_cog(ServerBackups(bot))
