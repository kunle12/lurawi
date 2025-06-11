import asyncio

# import concurrent.futures
from threading import Thread
import discord
from discord import Message
from lurawi.remote_service import RemoteService
from lurawi.utils import logger

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True


class HomeBot(discord.Client):
    def __init__(self, owner):
        super(HomeBot, self).__init__(intents=intents)
        self._loop = asyncio.new_event_loop()
        self.kb = owner.knowledge
        self.status = discord.Status.online
        self._owner = owner
        self._run_thread = None
        self._token = None
        # self.executor = ThreadPoolExecutor(max_workers=3)
        self._task = None
        self._main_channel = None

    async def on_ready(self):
        guild = discord.utils.get(self.guilds, name="困了的家")
        self._main_channel = discord.utils.get(guild.channels, name="常规")
        await self._main_channel.send("I am alive", delete_after=5.0)

    async def on_message(self, message: Message):
        user_name = self._discord_name_to_user(message.author.name)
        if user_name is None:
            return
        await self._owner.on_discord_event(user_name=user_name, message=message)

    async def logging_out(self):
        msg = await self._main_channel.send("I am going offline")
        await msg.delete()
        await self.logout()

    async def _send_message(self, mesg, delete_after=0.0):
        if delete_after > 0.0:
            await self._main_channel.send(mesg, delete_after=delete_after)
        else:
            await self._main_channel.send(mesg)

    def _discord_name_to_user(self, name):
        if "DiscordUserMap" in self.kb and name in self.kb["DiscordUserMap"]:
            return self.kb["DiscordUserMap"][name]
        return None

    def _start_run_thread(self):
        self._task = asyncio.ensure_future(self.start(self._token), loop=self._loop)
        # self._task.add_done_callback(stop_loop_on_completion)

        try:
            self._loop.run_until_complete(self._task)
        except (discord.LoginFailure, discord.HTTPException) as e:
            logger.error("Unable to log into the bot, error %s", e)
            self._task = None
        except KeyboardInterrupt:
            self._loop.run_until_complete(self.logging_out())
            self._task = None
        self._run_thread = None

    def start_running(self):
        if self._run_thread:
            return
        self._token = self.kb["DiscordToken"]
        self._run_thread = Thread(target=self._start_run_thread)
        self._run_thread.start()

    def stop_running(self):
        if not self._run_thread:
            return

        # also listen for termination of hearbeat / connection
        if self._task and not self._task.cancelled():
            self._task.cancel()
        self._run_thread.join()


class DiscordMessenger(RemoteService):
    def __init__(self, owner):
        super().__init__(owner=owner)
        self.token = None
        self.client = None

    def init(self):
        if "DiscordToken" in self.kb:
            self.client = HomeBot(self._owner)
            self._is_initialised = True
        else:
            logger.warning("No Discord token: Discord service is disabled")
        return self._is_initialised

    def start(self):
        if not self._is_initialised or self._is_running:
            return

        self.client.start_running()
        self._is_running = True

    def stop(self):
        if not self._is_running:
            return
        logger.info("Shutdown DiscordMessenger.")
        self.client.stop_running()
        self._is_running = False

    def fini(self):
        self.stop()
        self.client = None
        super().fini()
