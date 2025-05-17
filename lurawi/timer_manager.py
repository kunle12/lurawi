import asyncio
from threading import Thread
from .utils import logger


class TimerClient(object):
    def __init__(self):
        self.timercontext = {}

    async def on_timer(self, tid):
        return

    async def on_timer_lapsed(self, tid):
        return


class TimerManager(object):
    def __init__(self) -> None:
        self._run_thread = None
        self._loop = asyncio.new_event_loop()
        self._timers = {}
        self._next_timer_id = 1
        self._run_thread = Thread(target=self._start_run_thread)
        self._run_thread.start()
        logger.info("TimerManager initialised")

    def fini(self) -> None:
        logger.info("Shutting down TimerManager")
        if not self._run_thread:
            return

        for timer in self._timers.values():
            timer.cancel()

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._timers = {}

    def is_running(self) -> bool:
        return self._run_thread is not None

    def _start_run_thread(self) -> None:
        try:
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Unable to run event loop, error {e}")

        self._run_thread = None

    def add_timer(
        self,
        client: TimerClient,
        init_start: int = 0,
        interval: int = 1,
        repeats: int = -1,
    ):
        timer_id = self._next_timer_id
        self._next_timer_id = self._next_timer_id + 1
        self._timers[timer_id] = BotTimer(
            tid=timer_id,
            loop=self._loop,
            client=client,
            init_start=init_start,
            interval=interval,
            repeats=repeats,
        )
        return timer_id

    def add_task(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def del_timer(self, timer_id):
        if timer_id not in self._timers:
            logger.error(f"Timer {timer_id} does not exist")
            return

        timer = self._timers[timer_id]
        timer.cancel()
        del self._timers[timer_id]


class BotTimer(object):
    def __init__(
        self, tid, loop, client: TimerClient, init_start=0, interval=1, repeats=-1
    ):
        self.id = tid
        self._loop = loop
        self._client = client
        self._init_start = init_start
        self._repeats = repeats
        self._interval = interval
        self._is_running = True
        self._task = asyncio.run_coroutine_threadsafe(self._job(), self._loop)

    async def _job(self):
        if self._init_start > 0:
            await asyncio.sleep(self._init_start)
        await self._client.on_timer(self.id)
        if self._repeats < 0:
            while self._is_running:
                await asyncio.sleep(self._interval)
                await self._client.on_timer(self.id)
        else:
            while self._repeats > 0:
                await asyncio.sleep(self._interval)
                await self._client.on_timer(self.id)
                self._repeats -= 1

        await self._client.on_timer_lapsed(self.id)
        self._is_running = False

    def is_active(self) -> bool:
        return self._is_running

    def cancel(self):
        self._task.cancel()
        self._is_running = False


timerManager = TimerManager()
