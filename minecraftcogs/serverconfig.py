from discord.ext import commands
import discord
import logging
from utils import Config, permission_node, EmbedFlipbook

log = logging.getLogger('charfred')


class ServerConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.servercfg = bot.servercfg

    @commands.group(name='serverconfig')
    @permission_node(f'{__name__}.manage')
    async def config(self, ctx):
        """Minecraft server configuration commands."""

        pass

    @config.command()
    async def add(self, ctx, server: str):
        """Interactively add a server configuration."""

        if server in self.servercfg['servers']:
            await ctx.send(f'{server} is already listed!')
            return

        self.servercfg['servers'][server] = {}

        invocation, _, timedout = await ctx.promptinput(
            f'# Beginning configuration for {server}!'
            f'\nPlease enter the invocation for {server}:'
        )
        if timedout:
            return

        worldname, _, timedout = await ctx.promptinput(
            f'Please enter the name of the main world folder for {server}:'
        )
        if timedout:
            return

        questing, _, timedout = await ctx.promptconfirm_or_input(
            f'If {server} has questing, which you want to back up with Spiffy, '
            f'please enter the path from {worldname} to the quest directory.\n'
            '< If it has no questing or you don\'t want to back it up, just reply'
            ' with "no" >',
            confirm=False
        )
        if timedout:
            return

        confirmed, _, timedout = await ctx.promptconfirm(
            f'You have entered the following for {server}:\n'
            f'Invocation: {invocation}\n'
            f'Worldname: {worldname}\n'
            f'Questing: {questing}\n'
            '# Please confirm! [y/n]'
        )
        if timedout:
            return

        if confirmed:
            self.servercfg['servers'][server] = {
                'invocation': invocation,
                'worldname': worldname
            }
            if questing:
                self.servercfg['servers'][server]['questing'] = questing
            await self.servercfg.save()
            await ctx.sendmarkdown(f'# Serverconfigurations for {server} have been saved!')
        else:
            await ctx.sendmarkdown(f'< Pending entries for {server} have been discarded. >')

    @config.command(name='list')
    async def _list(self, ctx, server: str):
        """Lists all configurations for a given server."""

        if server not in self.servercfg['servers']:
            await ctx.sendmarkdown(f'< No configurations for {server} listed! >')
            return
        await ctx.sendmarkdown(f'# Configuration entries for {server}:\n')
        for k, v in self.servercfg['servers'][server].items():
            await ctx.sendmarkdown(f'{k}: {v}\n')

    def buildEmbeds(self):
        embeds = []
        for name, cfgs in self.servercfg['servers'].items():
            embed = discord.Embed(color=discord.Color.dark_gold())
            embed.description = f'Configurations for {name}:'
            for k, v in cfgs.items():
                embed.add_field(name=k, value=f'``` {v}```', inline=False)
            embeds.append(embed)
        return embeds

    @config.command()
    async def flip(self, ctx):
        """Lists all known server configurations,
        via Flipbook."""

        embeds = await self.loop.run_in_executor(None, self.buildEmbeds)
        cfgFlip = EmbedFlipbook(ctx, embeds, entries_per_page=1,
                                title='Server Configurations',
                                close_on_exit=True)
        await cfgFlip.flip()

    @config.command()
    async def edit(self, ctx, server: str):
        """Interactively edit the configurations for a given server."""

        if server not in self.servercfg['servers']:
            await ctx.sendmarkdown(f'< No configurations for {server} listed! >')
            return

        opt, _, timedout = await ctx.promptinput(
            f'Available options for {server}: ' +
            ' '.join(self.servercfg['servers'][server].keys()) +
            f'\n# Please enter the configuration option for {server}, that you want to edit:'
        )
        if timedout:
            return
        opt = opt.lower()

        if opt not in self.servercfg['servers'][server]:
            await ctx.sendmarkdown(f'< {opt} is not a valid entry! >')
            return

        val, _, timedout = await ctx.promptinput(
            f'Please enter the new value for {opt}:'
        )
        if timedout:
            return

        confirmed, _, timedout = await ctx.promptconfirm(
            f'You have entered the following for {server}:\n' +
            f'{opt}: {val}\n' +
            '# Please confirm! [y/n]'
        )
        if timedout:
            return

        if confirmed:
            self.servercfg['servers'][server][opt] = val
            await self.servercfg.save()
            await ctx.sendmarkdown(f'# Edit to {server} has been saved!')
        else:
            await ctx.sendmarkdown(f'< Edit to {server} has been discarded! >')

    @config.command()
    async def delete(self, ctx, server: str):
        """Delete the configuration of a given server."""

        if server not in self.servercfg['servers']:
            await ctx.sendmarkdown(f'< Nothing to delete for {server}! >')
            return

        confirmed, _, timedout = await ctx.promptconfirm(
            '< You are about to delete all configuration options '
            f'for {server}. >\n# Please confirm! [y/n]'
        )
        if timedout:
            return

        if confirmed:
            del self.servercfg['servers'][server]
            await self.servercfg.save()
            await ctx.sendmarkdown(f'# Configurations for {server} have been deleted!')
        else:
            await ctx.sendmarkdown(f'< Deletion of configurations aborted! >')

    @config.command()
    async def editopts(self, ctx):
        """Give the option of editing the various global server configurations!"""

        prompts = [
            ('serverspath',
             self.servercfg['serverspath'],
             'Current path to the directory where all minecraft server '
             'directories are located is:\n'),
            ('backupspath',
             self.servercfg['backupspath'],
             'Current path to the directory where backups are saved is:\n'),
            ('oldTimer',
             self.servercfg['oldTimer'],
             'Current maximum age for backups (in minutes) is:\n')
        ]

        changes = []

        for opt, val, prompt in prompts:
            new, _, timedout = await ctx.promptconfirm_or_input(
                f'{prompt}{val}\n'
                '< If you\'d like to change this, please enter the new'
                ' value now, otherwise just reply with "no" >',
                confirm=False
            )
            if timedout:
                return

            if new:
                changes.append((opt, val, new))

        if changes:
            confirmed, _, timedout = await ctx.promptconfirm(
                '# You have changed the following values:\n' +
                '\n'.join([f'{opt}: {old} to {new}' for opt, old, new in changes]) +
                '# Please confirm! [y/n]'
            )
            if timedout:
                return

            if confirmed:
                for opt, _, new in changes:
                    self.servercfg[opt] = new
                else:
                    await self.servercfg.save()
                    await ctx.sendmarkdown('# New values saved!')
                    return

        await ctx.sendmarkdown('< Edits have been discarded! >')


def setup(bot):
    if not hasattr(bot, 'servercfg'):
        default = {
            "servers": {}, "serverspath": "NONE", "backupspath": "NONE", "oldTimer": 1440
        }
        bot.servercfg = Config(f'{bot.dir}/configs/serverCfgs.toml',
                               default=default,
                               load=True, loop=bot.loop)
    bot.register_nodes([f'{__name__}.manage'])
    bot.add_cog(ServerConfig(bot))
