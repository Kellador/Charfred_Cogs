import logging
import asyncio
import traceback
from concurrent.futures import CancelledError
from discord.ext import commands
from utils import permission_node
from .utils import RelayConfig

log = logging.getLogger('charfred')


def escape(string):
    return string.strip().replace('\n', '\\n').replace('::', ':\:').replace('::', ':\:')


defaulttypes = {
    'MSG': {
        'prefix': 'MSG',
        'formatstr': '[**{client}**] {user}: {content}',
        'sendable': True,
        'formatfields': ['client', 'user', 'content'],
        'encoding': 'MSG::{client}::{user}::{content}::\n'
    },
    'SYS': {
        'prefix': 'SYS',
        'formatstr': '{content}',
        'sendable': False,
        'formatfields': ['content'],
        'encoding': 'SYS::{content}::\n'
    }
}


class ChatRelay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop
        self.inqueue = asyncio.Queue(maxsize=64, loop=self.loop)
        self.clients = {}
        self.inqueue_worker_task = None
        self.cfg = RelayConfig(f'{bot.dir}/configs/chatrelaycfg.toml',
                               initial=defaulttypes, load=True, loop=self.loop)
        self.server = bot.get_cog('StreamServer')
        if self.server:
            self.server.register_handshake('ChatRelay', self.connection_handler)

    def cog_unload(self):
        if self.inqueue_worker_task:
            self.inqueue_worker_task.cancel()
        if self.clients:
            for client in self.clients.values():
                try:
                    client['workers'][0].cancel()
                    client['workers'][1].cancel()
                except KeyError:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if (self.server is None) or (not self.server.running):
            # Don't even do anything if the server isn't running.
            return

        if message.author.bot or (message.guild is None):
            return

        ch_id = str(message.channel.id)
        if message.content and (ch_id in self.cfg.ch_clients):

            # Check whether the message is a command, as determined
            # by having a valid prefix, and don't proceed if it is.
            prefix = await self.bot.get_prefix(message)
            if isinstance(prefix, str):
                if message.content.startswith(prefix):
                    return
            else:
                try:
                    if message.content.startswith(tuple(prefix)):
                        return
                except TypeError:
                    # If we get here, then the prefixes are borked.
                    raise

            try:
                restriction = self.cfg.restricted[ch_id]
            except KeyError:
                out = f'MSG::Discord::{escape(message.author.display_name)}:' \
                      f':{escape(message.clean_content)}::\n'
            else:
                msgtype = self.cfg.types[restriction]
                if msgtype.sendable:
                    out = msgtype.encoding.format(
                        client='Discord',
                        user=escape(message.author.display_name),
                        content=escape(message.clean_content)
                    )
                else:
                    return

            for client in self.cfg.ch_clients[ch_id]:
                try:
                    self.clients[client]['queue'].put_nowait((5, out))
                except KeyError:
                    pass
                except asyncio.QueueFull:
                    pass

    @commands.group(invoke_without_command=True)
    async def chatrelay(self, ctx):
        """Minecraft chat relay commands.

        This returns a list of all Minecraft servers currently
        connected and what channel they're linked to.
        """

        info = ['# Chat Relay Status:']
        if self.clients:
            info.append('\n# Currently connected clients:')
            for client in self.clients:
                info.append(f'- {client}')
        if self.cfg:
            info.append('\n# Relay configuration:')
            for channel_id, clients in self.cfg.ch_clients.items():
                channel = self.bot.get_channel(int(channel_id))
                try:
                    res = self.cfg.restricted[channel_id]
                except KeyError:
                    info.append(f'{channel.name if channel else channel_id}:')
                else:
                    info.append(f'{channel.name if channel else channel_id} - Restricted to {res}:')
                if clients:
                    for client in clients:
                        info.append(f'- {client}')
                    else:
                        info.append('\n')
                else:
                    info.append('> No clients configured.\n')
        if len(info) == 2:
            info.append('> No clients connected, nothing configured.')
        await ctx.sendmarkdown('\n'.join(info))

    async def incoming_worker(self, reader, client):
        log.info(f'CR-Incoming: Worker for {client} started.')
        try:
            while True:
                data = await reader.readline()
                if not data:
                    log.info(f'CR-Incoming: {client} appears to have disconnected!')
                    break
                try:
                    data = data.decode()
                except UnicodeDecodeError as e:
                    log.info(f'CR-Incoming: {e}')
                    continue
                try:
                    self.inqueue.put_nowait((client, data))
                except asyncio.QueueFull:
                    log.warning(f'CR-Incoming: Incoming queue full, message dropped!')
        except CancelledError:
            raise
        except ConnectionResetError:
            log.info(f'CR-Incoming: Connection reset by {client}!')
        finally:
            log.info(f'CR-Incoming: Worker for {client} exited.')

    async def outgoing_worker(self, writer, client):
        log.info(f'CR-Outgoing: Worker for {client} started.')
        try:
            while True:
                try:
                    _, data = await self.clients[client]['queue'].get()
                except (KeyError, AttributeError):
                    log.error(f'CR-Outgoing: Outqueue for {client} is gone!'
                              ' Connection shutting down!')
                    break
                else:
                    data = data.encode()
                    writer.write(data)
                    await writer.drain()
        except CancelledError:
            writer.close()
            raise
        finally:
            log.info(f'CR-Outgoing: Worker for {client} exited.')

    async def connection_handler(self, reader, writer):
        peer = str(writer.get_extra_info("peername"))
        log.info(f'CR-Connection: Connection {peer} recieved!')
        handshake = await reader.readline()
        if not handshake:
            log.warning(f'CR-Connection: No handshake from {peer} recieved!'
                        ' Connection shutting down!')
            writer.close()
            return

        handshake = handshake.decode()
        hshk = handshake.split('::')
        if hshk[0] == 'HSHK':
            try:
                client = hshk[1]
            except IndexError:
                log.warning(f'CR-Connection: Invalid handshake: {handshake}')
                client = None
        else:
            log.warning(f'CR-Connection: Invalid handshake: {handshake}')
            client = None

        if client is None:
            log.warning(f'CR-Connection: Using client address as name.')
            client = peer

        await self.inqueue.put((client, f'SYS::```markdown\n# {client} connected!\n```'))

        if client in self.clients and self.clients[client]:
            if 'worker' in self.clients[client]:
                log.warning(f'CR-Connection: {client} reconnecting after messy exit, cleaning up!')
                for worker in self.clients[client]['workers']:
                    worker.cancel()

        self.clients[client] = {}
        self.clients[client]['queue'] = asyncio.PriorityQueue(maxsize=24, loop=self.loop)

        in_task = self.loop.create_task(self.incoming_worker(reader, client))
        out_task = self.loop.create_task(self.outgoing_worker(writer, client))

        self.clients[client]['workers'] = (in_task, out_task)

        _, waiting = await asyncio.wait([in_task, out_task],
                                        return_when=asyncio.FIRST_COMPLETED)
        for task in waiting:
            task.cancel()

        try:
            baggage = self.clients.pop(client)
        except KeyError:
            pass
        else:
            log.info(f'CR-Connection: Outqueue for {client} removed with'
                     f' {baggage["queue"].qsize()} items.')

        writer.close()
        log.info(f'CR-Connection: Connection with {client} closed!')
        await self.inqueue.put((client, f'SYS::```markdown\n< {client} disconnected! >\n```'))

    async def inqueue_worker(self):
        log.info('CR-Inqueue: Worker started!')
        try:
            while True:
                client, data = await self.inqueue.get()

                # Check if the data has a valid format.
                _data = data.split('::')

                try:
                    msgtype = self.cfg.types[_data[0]]
                except KeyError:
                    log.debug(f'CR-Inqueue: Data from {client} with invalid format: {data}')
                    continue

                # If we get here, then the format represents a valid type.
                if msgtype.sendable:
                    for other in self.clients:
                        if other == client:
                            continue
                        try:
                            self.clients[other]['queue'].put_nowait((5, data))
                        except KeyError:
                            pass
                        except asyncio.QueueFull:
                            pass

                # Check if we have a channel to post this message to.
                try:
                    channel = self.bot.get_channel(int(self.cfg.client_ch[client]))
                except KeyError:
                    log.debug(f'CR-Inqueue: No channel for: "{client} : {data}", dropping!')
                    continue

                # If we get here, we might have a channel and can process according to format map.
                if not channel:
                    log.warning(f'CR-Inqueue: {_data[0]} message from {client} could not be sent.'
                                ' Registered channel does not exist!')
                    continue

                try:
                    await channel.send(
                        msgtype.formatstr.format(**dict(zip(msgtype.formatfields, _data[1:])))
                    )
                except IndexError as e:
                    log.debug(f'{e}: {data}')
                    pass
        except CancelledError:
            raise
        finally:
            log.info('CR-Inqueue: Worker exited.')

    def _inqueueDone(self, future):
        try:
            exc = future.exception()
        except CancelledError:
            pass
        else:
            if exc:
                log.error('CR-Inqueue-Future: Exception occured!')
                log.error(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
                log.info('CR-Inqueue-Future: Restarting inqueue worker...')
                self._handle_inqueue_worker()

    def _handle_inqueue_worker(self, cancel=False):
        """Starts or cancels the inqueue_worker task
        and attaches relevant callbacks.
        """

        task = self.inqueue_worker_task
        if task:
            if not task.done():
                if cancel:
                    log.debug('Cancelling inqueue_worker_task.')
                    task.cancel()
                    return
                else:  # Task still running and no request to cancel, just proceed.
                    log.debug('Inqueue worker still running, no need to restart.')
                    return

            if cancel:  # We'll only get here if the task is done.
                self.inqueue_worker_task = None
                return

        # If the task does not exist, or is done and we don't want to cancel:
        self.inqueue_worker_task = self.loop.create_task(self.inqueue_worker())
        self.inqueue_worker_task.add_done_callback(self._inqueueDone)

    @chatrelay.command(aliases=['start', 'init'])
    @permission_node(f'{__name__}.init')
    async def initialize(self, ctx):
        """This initializes the relay server on the given port,
        allowing connections from Minecraft servers to be established.

        Be sure to also set up at least one channel to relay chat
        to and from, using the 'register' subcommand, otherwise
        chat recieved from clients will just be dropped!
        """

        if not self.server:
            self.server = self.bot.get_cog('StreamServer')
        try:
            self.server.register_handshake('ChatRelay', self.connection_handler)
        except AttributeError:
            await ctx.sendmarkdown('< Relay could not be established!'
                                   ' StreamServer is unavailable. >')
        else:
            self._handle_inqueue_worker()
            await ctx.sendmarkdown('# Relay server running.')

    @chatrelay.command(aliases=['stop'])
    @permission_node(f'{__name__}.init')
    async def close(self, ctx):
        """This unregisters the connection handler from the server,
        and disconnects all clients, effectively shutting down the
        chat relay.

        New connections can still be attempted but they will be dropped
        by the server.
        """

        if self.server:
            self.server.unregister_handshake('ChatRelay')
        else:
            await ctx.sendmarkdown(
                '< Could not unregister the connection handler.'
                ' StreamServer unavailable. >'
            )
            return
        self._handle_inqueue_worker(cancel=True)
        if self.clients:
            for client in self.clients.values():
                try:
                    client['workers'][0].cancel()
                    client['workers'][1].cancel()
                except KeyError:
                    pass
        await ctx.sendmarkdown('# All clients disconnected!')

    @chatrelay.command(aliases=['listen'])
    @permission_node(f'{__name__}.register')
    async def register(self, ctx, client: str):
        """Registers a channel to recieve chat from a given client,
        and send chat from the channel to the client.

        The channel you run this in will be the registered channel.

        You can get a list of clients by just running 'chatrelay'
        without a subcommand.
        """

        channel_id = str(ctx.channel.id)
        if client not in self.clients:
            await ctx.sendmarkdown('< Client unknown, registering anyway. >\n'
                                   '< Please check if you got the name right,'
                                   ' when the client eventually connects. >')
        log.info(f'CR: Trying to register {ctx.channel.name} for {client}.')

        if client in self.cfg.client_ch:
            await ctx.sendmarkdown('< Client is already registered to a channel! >')
            return

        self.cfg.client_ch[client] = channel_id

        await self.cfg.save()
        await ctx.sendmarkdown(f'# {ctx.channel.name} is now registered for'
                               f' recieving chat from, and sending chat to {client}.')

    @chatrelay.command(aliases=['unlisten'])
    @permission_node(f'{__name__}.register')
    async def unregister(self, ctx, client: str):
        """Unregisters a channel from recieving chat from a given
        client or sending chat to that client.

        Since a client can only be registered to one channel,
        it does not matter where you execute this command.

        You can get a list of clients by just running 'chatrelay'
        without a subcommand.
        """

        log.info(f'CR: Trying to unregister {client}.')

        if client not in self.cfg.client_ch:
            await ctx.sendmarkdown(f'> {client} is not registered with any channel.')
            return

        del self.cfg.client_ch[client]
        await self.cfg.save()
        await ctx.sendmarkdown(f'# {client} has been unregistered!')

    @chatrelay.group(invoke_without_command=True)
    @permission_node(f'{__name__}.register')
    async def formatting(self, ctx):
        """Returns the list of available message types and their
        formatting strings and whether or not they're restricted.
        """

        out = []
        for k, msgtype in self.cfg.types.items():
            prefix, suffix = ('< ', ' >') if msgtype.sendable else ('  ', '')
            out.append(f'{prefix}{msgtype.formatstr}{suffix}')
        await ctx.sendmarkdown('# Registered formats:\n' +
                               '\n'.join(out) +
                               '\n> Formats highlighted in yellow are not sendable.')

    @formatting.command(name='add', aliases=['modify'])
    @permission_node(f'{__name__}.format')
    async def _add(self, ctx, msgtype: str, formatstring: str, sendable: bool=True):
        """Adds a new, or modifies an existing message type, with a format string and
        sets if it is a sendable message type or not.

        'sendable' means that it can be sent to clients, either through relay from
        one client to all others, or by being sent from Discord.
        """

        self.cfg.types.add(msgtype, formatstring, sendable)
        await self.cfg.save()
        await ctx.sendmarkdown(
            f'{msgtype} has been saved with the following entries:' +
            '\n'.join([f'{k}: {v}' for k, v in self.cfg.types[msgtype]._asdict()]) +
            '\n> Some of these entries are auto-generated.'
        )

    @formatting.command(name='remove')
    @permission_node(f'{__name__}.format')
    async def _remove(self, ctx, msgtype: str):
        """Removes a message type and associated format string."""

        if msgtype in ('MSG', 'SYS'):
            await ctx.sendmarkdown(f'< Base type {msgtype} cannot be removed,'
                                   ' only modified! >')
            return

        try:
            del self.cfg.types[msgtype]
        except KeyError:
            await ctx.sendmarkdown(f'> {msgtype} was not registered.')
        else:
            await ctx.sendmarkdown(f'# {msgtype} removed!')
            await self.cfg.save()

    @chatrelay.command()
    @permission_node(f'{__name__}.register')
    async def restrict(self, ctx, msgtype: str):
        """Restricts a channel to only send and recieve a given
        type of message.

        The channel you run this in will be the restricted channel.

        A channel can only be restricted to one type of message, so this
        will override previous restrictions if they exist!

        You can get a list of message types using 'chatrelay formatting'.
        """

        channel_id = str(ctx.channel.id)
        if msgtype not in self.cfg.types:
            await ctx.sendmarkdown(f'< {msgtype} unknown! >')
            return
        if channel_id not in self.cfg.ch_clients:
            await ctx.sendmarkdown('< This channel is not yet registered for '
                                   'any client! Cannot restrict. >')
            return

        log.info(f'Restricting {ctx.channel.name} to {msgtype}.')

        self.cfg.restricted[channel_id] = msgtype
        await self.cfg.save()
        await ctx.sendmarkdown('# This channel is now restricted to only send '
                               f'and recieve {msgtype} messages.\n'
                               '> All outgoing messages will be converted to this type!')

    @chatrelay.command()
    @permission_node(f'{__name__}.register')
    async def unrestrict(self, ctx):
        """Unrestricts a channel and reverts it to being able to recieve any
        unrestricted type of message.

        The channel you run this in will be the channel that gets unrestricted.

        Outgoing messages will once again be of type 'MSG', after unrestriction.
        """

        channel_id = str(ctx.channel.id)
        if channel_id not in self.cfg.ch_clients:
            await ctx.sendmarkdown('< This channel is not yet registered for '
                                   'any client! Cannot unrestrict. >')
            return

        log.info(f'Unrestricting {ctx.channel.name}.')

        self.cfg.restricted[channel_id] = ''
        await self.cfg.save()
        await ctx.sendmarkdown('# This channel is now unrestricted and can recieve '
                               'all unrestricted types of messages.')


def setup(bot):
    permission_nodes = ['init', 'register']
    bot.register_nodes([f'{__name__}.{node}' for node in permission_nodes])
    bot.add_cog(ChatRelay(bot))
