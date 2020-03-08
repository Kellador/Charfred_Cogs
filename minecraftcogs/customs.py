from discord.ext import commands
from discord.utils import find
import re
import logging
from utils import Config, permission_node
from .utils import isUp, sendCmd

log = logging.getLogger('charfred')


class Customs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.servercfg = bot.servercfg
        self.customcmds = Config(
            f'{bot.dir}/configs/customCmds.json',
            loop=self.bot.loop,
            load=True
        )

    @commands.group(invoke_without_command=True, aliases=['cc'])
    @permission_node(f'{__name__}.custom')
    async def custom(self, ctx):
        """Custom Minecraft server commands commands.

        This returns a list of all currently registered custom console
        commands, if no subcommand was given.
        """

        msg = ['Custom Console Commands Library',
               '===============================']
        for name, cmd in self.customcmds.items():
            msg.append(name)
            msg.append(f"\t{cmd['role']}")
            msg.append(f"\t{cmd['cmd']}\n")
        msg = '\n'.join(msg)
        await ctx.sendmarkdown(msg)

    @custom.command(aliases=['edit', 'modify'])
    @permission_node(f'{__name__}.customEdit')
    async def add(self, ctx, name: str, minRole: str, *, cmd: str):
        """Add a custom command to the library.

        Takes a name to save the command under,
        a minimum required Discord role, and
        a variable length console command.
        Anything after the name parameter becomes
        part of the command.
        If you want your command to take arguments,
        you can place them anywhere in the command,
        by putting {} in their place.
        These will later be replaced in order from
        left to right, with the given arguments,
        when the command is ran.
        """
        if minRole not in self.bot.cfg['hierarchy']:
            await ctx.sendmarkdown(f'< {minRole} is not in the role hierarchy. >\n'
                                   '> Please try again!')
            return

        self.customcmds[name] = {'role': minRole, 'cmd': cmd}
        log.info(f'Added \"{cmd}\" to custom console commands library as \"{name}\".')
        await ctx.sendmarkdown(f'# Added \"{cmd}\" to your custom console commands'
                               ' library as \"{name}\".')
        await self.customcmds.save()

    @custom.command(aliases=['delete'])
    @permission_node(f'{__name__}.customEdit')
    async def remove(self, ctx, name: str):
        """Remove a custom command from the library.

        Takes the name the command to delete is
        registered under.
        """
        del self.customcmds[name]
        log.info(f'Removed \"{name}\" from your custom console commands library.')
        await ctx.sendmarkdown(f'# Removed \"{name}\" from your custom console commands library.')
        await self.customcmds.save()

    @custom.command(aliases=['execute', 'exec'])
    async def run(self, ctx, cmd: str, server: str, *args: str):
        """Runs a custom command from the library.

        Takes the name the command to run is registered
        under, a name of the target server and a variable
        number of arguments, which will be applied, if the
        custom command supports them.
        Target server can also be the \'all\' keyword,
        to iterate over all known servers, sending the
        command to each one.
        """
        msg = ['Command Log', '===========']
        if cmd not in self.customcmds:
            log.warning(f'\"{cmd}\" is undefined!')
            await ctx.sendmarkdown(f'< \"{cmd}\" is undefined! >')
            return
        _cmd = self.customcmds[cmd]['cmd']
        role = self.customcmds[cmd]['role']
        minRole = find(lambda r: r.name == role, ctx.guild.roles)
        if minRole:
            hierarchy = set(self.bot.cfg['hierarchy'])
            roles = [r for r in ctx.author.roles if r.name in hierarchy]
            if (not roles) or (roles[-1] < minRole):
                log.warning(f'User is missing permissions for {cmd}!')
                await ctx.sendmarkdown(f'< You are not permitted to run {cmd}! >\n'
                                       f'< Minimum required role is {str(minRole)}. >')
                return
        else:
            log.warning(f'Required role "{role}" does not exist!')
            await ctx.sendmarkdown(f'< Required role "{role}" does not exist! Abort! >')
            return
        log.info(f'Required: {str(minRole)}; User has: {str(roles[-1])}')

        if args:
            try:
                _cmd = _cmd.format(*args)
            except IndexError:
                await ctx.sendmarkdown(f'< Incorrect number of arguments given! Abort! >')
                return
        msg.append(f'# Executing \"{_cmd}\"...')

        if re.match('^all$', server, flags=re.I):
            for server in self.servercfg['servers']:
                if isUp(server):
                    log.info(f'Executing \"{cmd}\" on {server}.')
                    await sendCmd(self.loop, server, _cmd)
                    msg.append(f'# on {server};')
                else:
                    log.warning(f'Could not execute \"{cmd}\", {server} is offline!')
                    msg.append(f'< {server} is offline! >')
        else:
            if isUp(server):
                log.info(f'Executing \"{cmd}\" on {server}.')
                await sendCmd(self.loop, server, _cmd)
                msg.append(f'# on {server};')
            else:
                log.warning(f'Could not execute \"{cmd}\", {server} is offline!')
                msg.append(f'< {server} is offline! >')
        await ctx.sendmarkdown('\n'.join(msg))


def setup(bot):
    permission_nodes = ['custom', 'customEdit']
    bot.register_nodes([f'{__name__}.{node}' for node in permission_nodes])
    bot.add_cog(Customs(bot))
