from discord.ext import commands
import logging
from utils import Config, permission_node
from .utils import isUp, sendCmd

log = logging.getLogger('charfred')


class ConsoleCmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.servercfg = bot.servercfg
        if 'whitelistcategories' not in self.servercfg:
            self.servercfg['whitelistcategories'] = {}
        if 'defaultcategory' not in self.servercfg:
            self.servercfg['defaultcategory'] = ''

    @commands.group(aliases=['mc'], invoke_without_command=True)
    @permission_node(f'{__name__}.whitelist')
    async def minecraft(self, ctx):
        """Minecraft server console commands."""

        pass

    @minecraft.group(invoke_without_command=True)
    @permission_node(f'{__name__}.whitelist')
    async def whitelist(self, ctx, player: str, category: str=None):
        """Add a player to the whitelist.

        Optionally takes a category name, for whitelisting
        given player on servers in that category only.
        If a default category is set, it will be used, instead
        of defaulting to all known servers.
        """

        log.info('Whitelisting player.')
        if not category:
            category = self.servercfg['defaultcategory']
        if category:
            try:
                servers = self.servercfg['whitelistcategories'][category]
            except KeyError:
                log.warning('Category not found!')
                await ctx.sendmarkdown(f'< {category} does not exist! >')
                return
        else:
            servers = self.servercfg['servers']

        msg = ['Command Log', '==========', f'> Category: {category}' if category else '']
        for server in servers:
            if isUp(server):
                log.info(f'Whitelisting {player} on {server}.')
                await sendCmd(self.loop, server, f'whitelist add {player}')
                msg.append(f'# Whitelisted {player} on {server}.')
            else:
                log.warning(f'Could not whitelist {player} on {server}.')
                msg.append(f'< Unable to whitelist {player}, {server} is offline! >')
        await ctx.sendmarkdown('\n'.join(msg))

    @whitelist.command()
    @permission_node(f'{__name__}.whitelist')
    async def remove(self, ctx, player: str, category: str=None):
        """Remove a player from the whitelist."""

        log.info('Unwhitelisting player.')
        if not category:
            category = self.servercfg['defaultcategory']
        if category:
            try:
                servers = self.servercfg['whitelistcategories'][category]
            except KeyError:
                log.warning('Category not found!')
                await ctx.sendmarkdown(f'< {category} does not exist! >')
                return
        else:
            servers = self.servercfg['servers']

        msg = ['Command Log', '==========', f'> Category: {category}' if category else '']
        for server in servers:
            if isUp(server):
                log.info(f'Unwhitelisting {player} on {server}.')
                await sendCmd(self.loop, server, f'whitelist remove {player}')
                msg.append(f'# Unwhitelisting {player} on {server}.')
            else:
                log.warning(f'Could not unwhitelist {player} on {server}.')
                msg.append(f'< Unable to unwhitelist {player}, {server} is offline! >')
        await ctx.sendmarkdown('\n'.join(msg))

    @whitelist.command()
    @permission_node(f'{__name__}.whitelist')
    async def check(self, ctx, player: str):
        """Check if a player is on the whitelist."""

        msg = ['Command Log', '==========']
        for server in self.servercfg['servers']:
            try:
                with open(
                    self.servercfg['serverspath'] + f'/{server}/whitelist.json', 'r'
                ) as whitelist:
                    if player in whitelist.read():
                        msg.append(f'# {player} is whitelisted on {server}.')
                    else:
                        msg.append(f'< {player} is NOT whitelisted on {server}. >')
            except FileNotFoundError:
                msg.append(f'< {server} does not have a whitelist.json file! >')
        await ctx.sendmarkdown('\n'.join(msg))

    @whitelist.group(invoke_without_command=True)
    @permission_node(f'{__name__}.categories')
    async def category(self, ctx):
        """Whitelist category commands.

        Returns a list of all currently defined
        categories, if no subcommand is given.
        """

        msg = ['Whitelist Categories', '============']
        try:
            for category, servers in self.servercfg['whitelistcategories'].items():
                msg.append(f'# {category}:')
                for server in servers:
                    msg.append(f'\t{server}')
        except KeyError:
            msg.append('> No Categories defined!')
        await ctx.sendmarkdown('\n'.join(msg))

    @category.command()
    @permission_node(f'{__name__}.categories')
    async def setdefault(self, ctx, category: str):
        """Sets a defined category to be the default for whitelisting.

        If a default is set, whitelist commands will use it instead
        of defaulting to all known servers.
        """

        if category not in self.servercfg['whitelistcategories']:
            log.warning('Category not found!')
            await ctx.sendmarkdown(f'< {category} does not exist! >')
        else:
            self.servercfg['defaultcategory'] = category
            log.info('Set default whitelisting category!')
            await self.servercfg.save()
            await ctx.sendmarkdown(f'# {category} set as default whitelisting category.')

    @category.command()
    @permission_node(f'{__name__}.categories')
    async def add(self, ctx, category: str, *servers):
        """Add a new whitelist category.

        Takes a name for the new category and the names
        of all servers that should be a part of it.
        If category exists, given servers will be added to it.
        """

        if category not in self.servercfg['whitelistcategories']:
            log.info('Adding new whitelist category.')
            self.servercfg['whitelistcategories'][category] = []
        if servers:
            for server in servers:
                log.info(f'Added {server} to {category}.')
                self.servercfg['whitelistcategories'][category].append(server)
        await self.servercfg.save()
        await ctx.sendmarkdown(f'Done!')

    @category.command(name='remove')
    @permission_node(f'{__name__}.categories')
    async def _remove(self, ctx, category: str, server: str=None):
        """Removes a whitelist category or a given server from a category."""

        if server:
            log.info(f'Removing {server} from {category}.')
            try:
                self.servercfg['whitelistcategories'][category].remove(server)
            except KeyError:
                log.warning('Category not found!')
                await ctx.sendmarkdown(f'< {category} does not exist! >')
            except ValueError:
                log.warning('Server not found!')
                await ctx.sendmarkdown(f'> {server} is not in {category}!')
            else:
                await ctx.sendmarkdown(f'# {server} removed from {category}.')
            finally:
                return
        log.info(f'Removing {category}.')
        try:
            del self.servercfg['whitelistcategories'][category]
        except KeyError:
            log.warning('Category not found!')
            await ctx.sendmarkdown(f'< {category} does not exist! >')
        else:
            await ctx.sendmarkdown(f'# {category} removed!')
        await self.servercfg.save()

    @minecraft.command()
    @permission_node(f'{__name__}.kick')
    async def kick(self, ctx, server: str, player: str):
        """Kick a player from a specified server.

        Takes a servername and playername, in that order.
        """

        msg = ['Command Log', '==========']
        if isUp(server):
            log.info(f'Kicking {player} from {server}.')
            await sendCmd(self.loop, server, f'kick {player}')
            msg.append(f'# Kicked {player} from {server}.')
        else:
            msg.append(f'< {server} is not online! >')
        await ctx.sendmarkdown('\n'.join(msg))

    @minecraft.command()
    @permission_node(f'{__name__}.ban')
    async def ban(self, ctx, player: str):
        """Bans a player, and unwhitelists just to be safe."""

        msg = ['Command Log', '==========']
        for server in self.servercfg['servers']:
            if isUp(server):
                log.info(f'Banning {player} on {server}.')
                await sendCmd(self.loop, server, f'ban {player}')
                log.info(f'Unwhitelisting {player} on {server}.')
                await sendCmd(self.loop, server, f'whitelist remove {player}')
                msg.append(f'# Banned {player} from {server}.')
            else:
                log.warning(f'Could not ban {player} from {server}.')
                msg.append(f'< Unable to ban {player}, {server} is offline! >')
        await ctx.sendmarkdown('\n'.join(msg))

    @minecraft.command(aliases=['pass'])
    @permission_node(f'{__name__}.relay')
    async def relay(self, ctx, server: str, *, command: str):
        """Relays a command to a servers\' console.

        Takes a servername and a command, in that order.
        """

        msg = ['Command Log', '==========']
        if isUp(server):
            log.info(f'Relaying \"{command}\" to {server}.')
            await sendCmd(self.loop, server, command)
            msg.append(f'# Relayed \"{command}\" to {server}.')
        else:
            log.warning(f'Could not relay \"{command}\" to {server}.')
            msg.append(f'< Unable to relay command, {server} is offline! >')
        await ctx.sendmarkdown('\n'.join(msg))


def setup(bot):
    if not hasattr(bot, 'servercfg'):
        default = {
            "servers": {}, "serverspath": "NONE", "backupspath": "NONE", "oldTimer": 1440
        }
        bot.servercfg = Config(f'{bot.dir}/configs/serverCfgs.toml',
                               default=default,
                               load=True, loop=bot.loop)
    permission_nodes = ['whitelist', 'categories', 'kick', 'ban', 'relay']
    bot.register_nodes([f'{__name__}.{node}' for node in permission_nodes])
    bot.add_cog(ConsoleCmds(bot))
