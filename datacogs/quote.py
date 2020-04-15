import logging
import discord
from random import randrange
from discord.ext import commands
from utils import Config, Flipbook, permission_node

log = logging.getLogger('charfred')


class Quotator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.quotes = Config(f'{bot.dir}/data/quotes.json',
                             load=True, loop=self.loop)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if str(reaction.emoji) == '💾' and reaction.count == 1:
            if user.bot or reaction.message.author.bot:
                return

            log.info('Saving a quote!')
            quotee = reaction.message.author
            if reaction.message.attachments:
                urls = []
                for a in reaction.message.attachments:
                    urls.append(a.url)
                urls = '\n'.join(urls)
                quote = f'{reaction.message.content}\n{urls}'
            else:
                quote = reaction.message.content
                if not quote:
                    await reaction.message.add_reaction('🖕')
                    return

            id = str(quotee.id)

            if id not in self.quotes:
                self.quotes[id] = []

            self.quotes[id].append({'quote': quote,
                                    'savedBy': user.id})
            await self.quotes.save()
            await reaction.message.add_reaction('👌')

    @commands.group(invoke_without_command=True)
    @permission_node(f'{__name__}.quote')
    async def quote(self, ctx, member: discord.Member=None, _index: int=None):
        """User Quote commands.

        This returns a list of all users that are registered in the
        quote repository, if no subcommand was given.
        """

        if member and str(member.id) in self.quotes:
            id = str(member.id)
            if _index is None:
                log.info('Random quote!')
                _index = randrange(len(self.quotes[id]))
                q = self.quotes[id][_index]['quote']
            else:
                try:
                    log.info('Specific quote!')
                    q = self.quotes[id][_index]['quote']
                except (KeyError, IndexError):
                    log.info('No quote with that index!')
                    await ctx.send('Sorry sir, there is no quote under that number!')
                    return
            if member.nick:
                name = member.nick
            else:
                name = member.name
            await ctx.send(f'{q}\n\n_{name}; Quote #{_index}_')
        else:

            converter = commands.MemberConverter()

            async def getName(id):
                try:
                    member = await converter.convert(ctx, id)
                except commands.errors.BadArgument:
                    log.warning(f'{id} could not be resolved; removed from quotes!')
                    del self.quotes[id]
                    await self.quotes.save()
                    return None
                if member.nick:
                    return member.nick
                else:
                    return member.name

            members = '\n'.join(filter(None, [await getName(id) for id in list(self.quotes.keys())]))
            await ctx.send(f'I have quotes from these members:\n ```\n{members}\n```')

    @quote.command(aliases=['delete', 'unquote'])
    @permission_node(f'{__name__}.quote')
    async def remove(self, ctx, member: discord.Member, *, _index: int):
        """Remove a specific quote.

        Takes the user who was quoted, and
        the ID of the quote to be removed,
        which is shown at the bottom of each
        quote.

        Only the user who saved the quote,
        and the quoted user can do this.
        """

        if str(member.id) in self.quotes:
            id = str(member.id)
            log.info('Removing a quote!')
            try:
                if ctx.author.id == member.id or \
                        ctx.author.id == self.quotes[id][_index]['savedBy']:
                    del self.quotes[id][_index]
                    await ctx.send('We shall never speak of it again, sir!')
                    await self.quotes.save()
                else:
                    await ctx.send('I am sorry, sir, but you are neither the quotee, '
                                   'nor the person who requested this quote to be saved.')
            except KeyError:
                log.info('Unknown quote, cannot remove!')
                await ctx.send('Sorry sir, I don\'t seem to have a record of this quote.')
        else:
            log.info('Unknown member!')
            await ctx.send('Sorry lass, I don\'t seem to have heard of this person before.')

    @quote.command(name='list')
    @permission_node(f'{__name__}.quote')
    async def _list(self, ctx, member: discord.Member):
        """List all quotes from a specific user.

        Quotes are presented as a nice flipbook, for
        easy and non-spammy perusal!
        """

        if str(member.id) in self.quotes:
            id = str(member.id)
            log.info('Showing quotes!')

            quotelist = []
            for index, quotemeta in enumerate(self.quotes[id]):
                quote = quotemeta['quote']
                quotelist.append(f'#{index}: {quote:.50}')

            if member.nick:
                name = member.nick
            else:
                name = member.name
            quoteFlip = Flipbook(ctx, quotelist, entries_per_page=12,
                                 title=f'Shit {name} says!',
                                 color=discord.Color.blurple(),
                                 close_on_exit=True)
            await quoteFlip.flip()

        else:
            log.info('Unknown member!')
            await ctx.send('Sorry lass, I don\'t seem to have heard of this person before.')


def setup(bot):
    bot.register_nodes([f'{__name__}.quote'])
    bot.add_cog(Quotator(bot))
