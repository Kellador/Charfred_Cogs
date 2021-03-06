import logging
import random
import asyncio
from datetime import datetime
from discord.ext import commands

log = logging.getLogger('charfred')

dances = [
    [u"└|ﾟεﾟ|┐", u"┌|ﾟзﾟ|┘", u"└|ﾟεﾟ|┐", u"┌|ﾟзﾟ|┘", u"└|ﾟεﾟ|┐", u"┌|ﾟзﾟ|┘"],
    [u"└|∵┌|", u"|┐∵|┘", u"└|∵┌|", u"|┐∵|┘", u"└|∵┌|", u"|┐∵|┘"],
    [u"(o^^)o", u"o(^^o)", u"(o^^)o", u"o(^^o)", u"(o^^)o", u"o(^^o)"],
    [u"|o∵|o", u"o|∵o|", u"|o∵|o", u"o|∵o|", u"|o∵|o", u"o|∵o|"],
    [u"(ノ￣ー￣)ノ", u"(〜￣△￣)〜", u"(ノ￣ω￣)ノ", u"(ノ￣ー￣)ノ", u"(〜￣△￣)〜", u"(ノ￣ω￣)ノ"]
]

faces = [
    u"(´﹃｀)", u"(・ε・｀)", u"(ง •̀ω•́)ง✧", u"╭( ･ㅂ･)و", u"ಠ‿↼", u"d(-_^)", u"d(´･ω･`)",
    u"٩(^ᴗ^)۶", u"ಥ◡ಥ", u"⚈ ̫ ⚈", u"∠(^ー^)", u"(^-^)ゝ", u"(∩^o^)⊃━☆ﾟ.*･｡ﾟ", u"ლ(・ヮ・ლ)"
]

pleasures = [
    'My pleasure, sir!', 'My pleasure, ma\'am', 'You are very welcome, sir!',
    'You are very welcome, madam!', 'Of course, your highness!', 'Of course, your ladyship!',
    'M\'lord *tips tophat*', 'Indubitably!', 'Fuck you!', '...', ' '
]

loves = [
    u"•́ε•̀٥", u"˶⚈Ɛ⚈˵", u"(・ε・｀)", u"(~￣³￣)~", u".+(´^ω^`)+.", u"ﾟ*｡(･∀･)ﾟ*｡", u"",
    u"(∩^o^)⊃━☆゜.*", u"ಠ◡ಠ", u"ʢᵕᴗᵕʡ", u"(^￢^)", u"(º﹃º)", u"ಠ_ರೃ", u"d(´･ω･`)"
]

gms = [
    'Top o\' the mornin\' to ya!', 'Good morning, sir!', 'Good morning, madam!',
    'o/', 'Fuck you!', 'I\'m a cybernetic organism, living tissue over metal endoskelton.',
    'Fuck you, asshole!', 'Hello, dear!', 'Sup?', 'Good morning!', '*muffled screaming*',
    'If you don\'t stop screwing around back there, this is what I\'m going to do with you'
    '\n*snaps pencil*', 'Aloha!', '*high five*', '*hug*'
]

gn9s = [
    'Good night, sir!', 'Good night!', 'Nighty night!', 'Sweet dreams!',
    'Sleep well!', 'Don\'t let the bedbugs bite!', 'Pleasant dreams!',
    'Glorious dreams to you, too!'
]

shrugs = [
    u"┐(￣ヘ￣)┌", u"ლ（╹ε╹ლ）", u"ლ(ಠ益ಠ)ლ", u"¯\_(⊙_ʖ⊙)_/¯",
    u"¯\_(ツ)_/¯", u"┐(´ー｀)┌", u"乁༼☯‿☯✿༽ㄏ", u"╮(╯_╰)╭"
]

shocks = [
    u"(ʘᗩʘ’)", u"(ʘ言ʘ╬)", u"(◯Δ◯∥)", u"(●Ω●;)"
]

spins = [
    [u"(・ω・)", u"(　・ω)", u"(　・)", u"(　)", u"(・　)", u"(ω・　)", u"(・ω・)"],
    [u"(´･ω･`)", u"( ´･ω･)", u"( 　´･ω)", u"( 　　)", u"( 　　)", u"(ω･´　)", u"(･ω･´)", u"(｀･ω･´)"],
    [u"(･▽･)", u"( ･▽)", u"(　･)", u"(　　)", u"(･　)", u"(▽･ )", u"(･▽･)"],
    [u"(･＿･)", u"( ･_)", u"(　･)", u"(　　)", u"(･　)", u"(_･ )", u"(･＿･)"],
    [u"(°o°)", u"(°o。)", u"(。o。)", u"(。o°)", u"(°o°)", u"(°o。)", u"(。o。)", u"(。o°)"]
]

weather = [
    'rainy', 'sunny', 'cloudy', 'foggy', 'stormy'
]

cats = [
    'ㅇㅅㅇ', '=ටᆼට=', '(=①ω①=)', '(=ＴェＴ=)', '(=ↀωↀ=)', '(⁎˃ᆺ˂)', 'ฅ•ω•ฅ',
    '=^∇^*=', '(^･ｪ･^)'
]


class Entertain(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.session = bot.session
        self.cats = {}

    @commands.command(aliases=['partytime'])
    async def dance(self, ctx):
        dance = random.choice(dances)
        step = await ctx.send(dance[0], deletable=False)
        await asyncio.sleep(2, loop=self.loop)
        for move in dance[1:]:
            await step.edit(content=move)
            await asyncio.sleep(2, loop=self.loop)
        else:
            await step.add_reaction('👍')

    @commands.command(aliases=['youspinmerightroundbabyrightround'])
    async def spin(self, ctx):
        spin = random.choice(spins)
        step = await ctx.send(spin[0], deletable=False)
        await asyncio.sleep(2, loop=self.loop)
        for turn in spin[1:]:
            await step.edit(content=turn)
            await asyncio.sleep(2, loop=self.loop)
        else:
            await step.add_reaction('👍')

    @commands.command(aliases=['*shrug*'])
    async def shrug(self, ctx):
        await ctx.send(random.choice(shrugs))

    @commands.command(aliases=['jikes'])
    async def shock(self, ctx):
        await ctx.send(random.choice(shocks))

    @commands.command(aliases=['flip', 'table'])
    async def tableflip(self, ctx):
        unflipped = await ctx.send(u"(ಠ_ಠ) ┳━┳", deletable=False)
        await asyncio.sleep(2, loop=self.loop)
        await unflipped.edit(content=u"(╯ಠ_ಠ)╯︵┻━┻")

    @commands.command(aliases=['thank'])
    async def thanks(self, ctx):
        await ctx.send(random.choice(pleasures) + ' ' +
                       random.choice(faces))

    @commands.command(aliases=['gn9', 'gn8', 'goodnight', 'nn'])
    async def gn(self, ctx):
        await ctx.send(random.choice(gn9s) + ' ' +
                       random.choice(loves))

    @commands.command(aliases=['cats'])
    async def getcat(self, ctx):
        try:
            apitok = self.bot.cfg['cogcfgs'][f'{__name__}.catapi'][0]
        except KeyError:
            log.warning('No token for thecatapi.com configured!')
            await ctx.sendmarkdown('< No catapi token found! Sorry! >')
        else:
            headers = {'x-api-key': apitok}
            async with self.session.get('https://api.thecatapi.com/v1/images/search',
                                        headers=headers) as r:
                jsoncat = await r.json()
            try:
                cat = jsoncat[0]['url']
            except KeyError:
                log.warning('Response from thecatapi.com contained no cat url!')
                cat = None
            else:
                await ctx.send(f'{random.choice(cats)}\n{cat}')

    @commands.command(aliases=['gm', 'goodmorning', 'goodday'])
    async def morning(self, ctx):

        greeting = random.choice(gms)
        now = datetime.now()

        log.info('Retrieving historical data!')

        async with self.session.get('https://history.muffinlabs.com/date') as r:
            if r.status == 200:
                data = await r.json(content_type=None)
            else:
                log.warning(f'Recieved status code: {r.status} from history.muffinlabs.com/date\n'
                            'Skipping historical data...')
                data = None

        if data:
            try:
                event = random.choice(data['data']['Events'])
            except KeyError:
                log.warning('Response content from history.muffinlabs.com/date is malformed!')
                history = ''
            except IndexError:
                log.warning('Apparently there are no historical events for this date, wow!')
                history = f'\nOn this date in history, fuck all happened!\n'
            else:
                history = f'\nOn this date, in {event["year"]}, the following historical event took place:\n{event["text"]}\n'
        else:
            history = ''

        out = [
            greeting,
            now.strftime('The date and time is:\n%c'),
            history,
            f'I am expecting {random.choice(weather)} weather today (somewhere).'
        ]

        await ctx.send('\n'.join(out))


def setup(bot):
    bot.register_cfg(f'{__name__}.catapi',
                     'Please enter your api token for thecatapi.com:\n',
                     '')
    bot.add_cog(Entertain(bot))
