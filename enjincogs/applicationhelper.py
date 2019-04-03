import logging
import json
import asyncio
from time import sleep
from threading import Event
from discord.ext import commands
from utils.config import Config
from utils.discoutils import permission_node, sendMarkdown, promptInput, promptConfirm, send
from .utils.enjinutils import post, verifysession

log = logging.getLogger('charfred')


class ApplicationHelper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.session = bot.session
        if hasattr(bot, 'enjinsession'):
            self.enjinsession = bot.enjinsession
        else:
            self.enjinsession = None
        if hasattr(bot, 'enjinlogin'):
            self.enjinlogin = bot.enjinlogin
        else:
            self.enjinlogin = None
        self.enjinappcfg = Config(f'{bot.dir}/configs/applicationcfg.json',
                                  load=True, loop=bot.loop)
        try:
            self.enjinappcfg['template']
        except KeyError:
            self.enjinappcfg['template'] = {}
        try:
            self.enjinappcfg['fieldnames']
        except KeyError:
            self.enjinappcfg['fieldnames'] = {}

        self.watchdogfuture = None
        self.latestappids = []
        self.openapps = []

    def cog_unload(self):
        if self.watchdogfuture:
            self.watchdogfuture[1].set()

    @commands.group(aliases=['enjinapps', 'app'], invoke_without_command=True)
    @permission_node(f'{__name__}.enjinapps')
    async def apps(self, ctx):
        """Enjin Application commands.

        Gives some enjin login status information, when no subcommand is given.
        """

        if hasattr(self.bot, 'enjinsession'):
            self.enjinsession = self.bot.enjinsession
        else:
            self.enjinsession = None
        if hasattr(self.bot, 'enjinlogin'):
            self.enjinlogin = self.bot.enjinlogin
        else:
            self.enjinlogin = None

        if not self.enjinappcfg:
            await sendMarkdown(ctx, '< No application configuration available! >')
        if not self.enjinappcfg['fieldnames']:
            await sendMarkdown(ctx, '< No fieldnames set! >')
        if not self.enjinappcfg['template']:
            await sendMarkdown(ctx, '< No application template set! >')
        if not self.enjinsession:
            await sendMarkdown(ctx, '< Not logged into enjin! >')
        else:
            valid = await verifysession(self.session, self.enjinsession)
            if valid:
                await sendMarkdown(ctx, '# All is well!')
            else:
                await sendMarkdown(ctx, '< Current enjin session is invalid! >')

    async def _getapp(self, appid):
        payload = {
            'method': 'Applications.getApplication',
            'params': {
                'session_id': self.enjinsession.session_id,
                'application_id': appid
            }
        }
        app = await post(self.session, payload, self.enjinsession.url)
        if not app:
            log.info('No application recieved!')
            return None
        fields = app['result']['user_data']
        qhashes = list(fields.keys())
        return (fields, qhashes)

    def _applyfieldnames(self, qhashes):
        if not self.enjinappcfg['fieldnames']:
            return qhashes
        return [self.enjinappcfg['fieldnames'][qhash] for qhash in qhashes]

    def _formatmsg(self, fields, qhashes, numbered=False):
        msg = ['# Retrieved Application contained the following entries:']
        fieldnames = self._applyfieldnames(qhashes)
        if numbered:
            for i, key in enumerate(qhashes):
                msg.append(f'[{i}]-[{fieldnames[i]}]: {fields[key]}')
        else:
            for i, key in enumerate(qhashes):
                msg.append(f'[{fieldnames[i]}]: {fields[key]}')
        msg = '\n'.join(msg)
        return msg

    @apps.command(name='get')
    async def getapp(self, ctx, appid):
        """Retrieves the user entered info for a given application id."""

        fields, qhashes = await self._getapp(appid)
        if not fields:
            await sendMarkdown(ctx, '< Application could not be retrieved! >')
            return
        msg = self._formatmsg(fields, qhashes)
        await sendMarkdown(ctx, msg)

    @apps.command()
    @permission_node(f'{__name__}.enjinedittemplate')
    async def setfieldnames(self, ctx, anyappid: int):
        """Save a set of short identifiers for all application entry fields.

        Requires a valid application id to retrieve the necessary field name hashes,
        as they are returned by the enjin api; Ideally this would be an application
        that allows you to easily distinguish the fields from one another.
        """

        if self.enjinappcfg and self.enjinappcfg['fieldnames']:
            log.info('Application field names already saved!')
            b, _, timedout = await promptConfirm(ctx, '> A set of field names is already '
                                                 'saved! Override?')
            if timedout:
                return
            if not b:
                await sendMarkdown(ctx, '> Override aborted.')
                return

        fields, qhashes = await self._getapp(anyappid)
        if not fields:
            await sendMarkdown(ctx, '< Application could not be retrieved! >')
            return
        msg = self._formatmsg(fields, qhashes, numbered=True)
        await sendMarkdown(ctx, msg)

        await sendMarkdown(ctx, '> This next bit is gonna be a bit tricky...')
        fieldnames, _, timedout = await promptInput(
            ctx,
            '# Please enter the field names for each field, in the order '
            'as they appear in the above application listing, seperated by spaces.\n\n'
            '< These names should be short and cannot contain spaces themselves! >\n\n'
            '> You may use underscores in place of spaces for readability!\n\n'
            '# Also hurry it up, this prompt will time out in 5 minutes!',
            360
        )
        if timedout:
            return
        if not fieldnames:
            log.info('Prompt failed!')
            await sendMarkdown(ctx, '< Prompt failed, please try again! >')
            return
        fieldnames = fieldnames.split()
        if not (len(fieldnames) == len(qhashes)):
            log.info('Not enough names entered!')
            await sendMarkdown(ctx, '< Not enough names entered, please try again! >')
            return
        self.enjinappcfg['fieldnames'] = {}
        for i, name in enumerate(fieldnames):
            self.enjinappcfg['fieldnames'][qhashes[i]] = name
        await self.enjinappcfg.save()
        await sendMarkdown(ctx, '# Field names saved!')

    @apps.command(aliases=['configure'])
    @permission_node(f'{__name__}.enjinedittemplate')
    async def settemplate(self, ctx, correctappid: int):
        """Save a template for validation of an application.

        You may specify an application id, for an \'ideal\' application,
        after which said application will be parsed and you will be prompted
        to select the fields that you wish your template to contain.
        """

        if self.enjinappcfg:
            log.info('Application template already saved.')
            b, _, timedout = await promptConfirm(ctx, 'An application template already '
                                                 'exists, do you wish to override?')
            if timedout:
                return
            if not b:
                await sendMarkdown(ctx, '> Configuration complete!')
                return

        fields, qhashes = await self._getapp(correctappid)
        if not fields:
            await sendMarkdown(ctx, '< Application could not be retrieved! >')
            return
        msg = self._formatmsg(fields, qhashes, numbered=True)
        await sendMarkdown(ctx, msg)
        selection, _, timedout = await promptInput(
            ctx,
            '# Please enter the numbers for all the fields you wish to include '
            'in the template, seperated by spaces.\n\n'
            '# Go on, type type! This prompt times out in 5 minutes!',
            360
        )
        if timedout:
            return
        if not selection:
            log.info('Prompt failed!')
            await sendMarkdown(ctx, '< Prompt failed, please try again! >')
        selection = selection.split()
        self.enjinappcfg['template'] = {}
        for i in selection:
            self.enjinappcfg['template'][qhashes[int(i)]] = fields[qhashes[int(i)]]
        await self.enjinappcfg.save()
        await sendMarkdown(ctx, '# Template saved!\n> You may review the current '
                           'template via the viewtemplate command.')

    @apps.command()
    async def viewtemplate(self, ctx, raw: bool=False):
        """Prints the current template."""

        log.info('Printing enjin application template.')

        if raw:
            template = json.dumps(self.enjinappcfg.cfgs, indent=2)
            await sendMarkdown(ctx, '# Current enjin application template:')
            await send(ctx, f'```json\n{template}```')
        else:
            msg = ['# Current enjin application template:\n']
            for k, v in self.enjinappcfg['template'].items():
                fieldname = self.enjinappcfg['fieldnames'][k]
                msg.append(f'[{fieldname}]: {v}')
            msg = '\n'.join(msg)
            await sendMarkdown(ctx, msg)

    async def _getapplist(self, type: str='open'):
        payload = {
            'method': 'Applications.getList',
            'params': {
                'session_id': self.enjinsession.session_id,
                'type': type,
                'site_id': self.enjinsession.site_id
            }
        }
        apps = await post(self.session, payload, self.enjinsession.url)
        if not apps:
            return None
        else:
            return apps['result']['items']

    @apps.command(name='list')
    async def _list(self, ctx, type: str='open'):
        """Retrieves a condensed list of applications.

        You may specify a type, if you wish to see closed or rejected
        applications, otherwise it will default to open ones.
        """

        log.info('Retrieving applications...')
        apps = await self._getapplist(type)
        if not apps:
            log.warning('Application retrieval failed!')
            await sendMarkdown(ctx, f'< Application retrieval failed! >')
            return
        msg = [f'# The following applications are currently {type}:\n']
        for app in apps:
            msg.append('# Application by: ' + app['username'])
            msg.append('> Application ID: ' + app['application_id'] + '\n')
        msg = '\n'.join(msg)
        await sendMarkdown(ctx, msg)
        log.info('Applications retrieved and listed!')

    @apps.group(invoke_without_command=True)
    async def watchdog(self, ctx):
        """Application watchdog commands.

        Returns the status of the application watchdog,
        if no subcommand was given.
        """

        if self.watchdogfuture:
            if self.watchdogfuture[0].done():
                await sendMarkdown(ctx, '< Application watchdog inactive! >')
            else:
                await sendMarkdown(ctx, '# Application watchdog active!')

    @watchdog.command()
    async def start(self, ctx):
        """Start application watchdog.

        Checks for new applications every 5 minutes,
        and reports the number of open applications at that time.
        """

        async def applisttimeout():
            await sendMarkdown(ctx, '< App list retrieval timed out! Odd... >',
                               deletable=False)

        async def applistexception():
            await sendMarkdown(ctx, '< An exception occured during app list retrieval! >',
                               deletable=False)

        async def watchgone():
            await sendMarkdown(ctx, '> Application watchdog stopped!', deletable=False)

        def watchdone(future):
            log.info('AW: Application watchdog stopped.')
            if future.exception():
                log.warning('AW: Exception in application watchdog!')
                raise future.exception()
            asyncio.run_coroutine_threadsafe(watchgone(), self.loop)

        def watch(event):
            log.info('Starting application watchdog.')
            while not event.is_set():
                future = asyncio.run_coroutine_threadsafe(self._getapplist(), self.loop)
                try:
                    apps = future.result(10)
                except asyncio.TimeoutError:
                    log.warning('AW: App list retrievel timed out!')
                    future.cancel()
                    asyncio.run_coroutine_threadsafe(applisttimeout(), self.loop)
                except Exception as e:
                    log.error('AW: Exception in app list retrieval!')
                    log.error(e)
                else:
                    if apps is None:
                        coro = sendMarkdown(ctx, '< App list could not be retrieved! >')
                        asyncio.run_coroutine_threadsafe(coro, self.loop)
                    else:
                        if len(apps) > 0:
                            apps = [{'username': app['username'],
                                     'application_id': app['application_id']}
                                    for app in apps]
                            diff = [app for app in apps if app not in self.openapps]
                        else:
                            self.latestappids.clear()
                            diff = []
                        self.openapps = apps
                        if diff:
                            for app in diff:
                                msg = (f'```markdown\nNew Application by: {app["username"]}\n```'
                                       f'{self.enjinsession.url}/dashboard/applications/'
                                       f'application?app_id={app["application_id"]}')
                                self.latestappids.append(app['application_id'])
                                coro = send(ctx, msg)
                                asyncio.run_coroutine_threadsafe(coro, self.loop)
                            log.info('New applications retrieved and listed!')
                        else:
                            log.info('No new applications.')
                sleep(300)

        event = Event()
        watchfuture = self.loop.run_in_executor(None, watch, event)
        watchfuture.add_done_callback(watchdone)
        self.watchdogfuture = (watchfuture, event)
        await sendMarkdown(ctx, '# Application watchdog activated!', deletable=False)

    @watchdog.command()
    async def stop(self, ctx):
        """Stop the application watchdog."""

        if self.watchdogfuture and not self.watchdogfuture[0].done():
            self.watchdogfuture[1].set()
            await sendMarkdown(ctx, '> Terminating application watchdog...', deletable=False)
        else:
            await sendMarkdown(ctx, '# Application watchdog already inactive!', deletable=False)

    @apps.command(aliases=['check'])
    async def validate(self, ctx, applicationid: int=None):
        """Validate an application against the saved template.

        Requires the application id for the application you wish to
        validate (you may use the apps list command to retrieve a
        list of such ids).
        If no application id is given, the id of the latest known
        application will be used, removing it from the list of
        latest application ids.
        """

        log.info('Validating application...')
        if not self.enjinappcfg:
            log.warning('No template found!')
            await sendMarkdown(ctx, '< No template found! Please configure'
                               'one before trying again! >')
            return

        if not applicationid:
            if len(self.latestappids) > 0:
                log.info('Using latest application id.')
                applicationid = self.latestappids.pop()
            else:
                log.warning('No id given and no latest app id known!')
                await sendMarkdown(ctx, '< No application id given! >')

        payload = {
            'method': 'Applications.getApplication',
            'params': {
                'session_id': self.enjinsession.session_id,
                'application_id': applicationid
            }
        }
        app = await post(self.session, payload, self.enjinsession.url)
        if not app:
            log.warning('App could not be retrieved!')
            await sendMarkdown(ctx, '< App could not be retrieved! >')
            return

        user = app['result']['username']
        answers = app['result']['user_data']
        freeformfields = {k: v for k, v in answers.items() if k not in self.enjinappcfg['template']}
        correctfields = {k: v for k, v in answers.items() if k in self.enjinappcfg['template'] and
                         v == self.enjinappcfg['template'][k]}
        incorrectfields = {k: v for k, v in answers.items() if k not in freeformfields and
                           k not in correctfields}
        corrections = {k: v for k, v in self.enjinappcfg['template'].items() if k in incorrectfields}

        msg = [f'# Application by: {user}']
        msg.append('\n> Text input fields (not evaluated):\n')
        for k, v in freeformfields.items():
            try:
                fieldname = self.enjinappcfg['fieldnames'][k]
            except KeyError:
                fieldname = k
            msg.append(f'> {fieldname}: {v}')

        msg.append('\n# Correct fields:\n')
        for k, v in correctfields.items():
            try:
                fieldname = self.enjinappcfg['fieldnames'][k]
            except KeyError:
                fieldname = k
            msg.append(f'# {fieldname}: {v}')

        msg.append('\n< Incorrect fields: >\n')
        for k, v in incorrectfields.items():
            try:
                fieldname = self.enjinappcfg['fieldnames'][k]
            except KeyError:
                fieldname = k
            msg.append(f'< {fieldname}: {v} >')

        msg.append('\n> Corrections for incorrect fields:\n')
        for k, v in corrections.items():
            try:
                fieldname = self.enjinappcfg['fieldnames'][k]
            except KeyError:
                fieldname = k
            msg.append(f'> {fieldname}: {v}')

        msg = '\n'.join(msg)
        await sendMarkdown(ctx, msg)
        await send(ctx, f'{self.enjinsession.url}/dashboard/applications'
                   f'/application?app_id={applicationid}')


def setup(bot):
    permission_nodes = ['enjinapps', 'enjinedittemplate']
    bot.register_nodes([f'{__name__}.{node}' for node in permission_nodes])
    bot.add_cog(ApplicationHelper(bot))
