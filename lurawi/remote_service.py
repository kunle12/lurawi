from typing import Dict
from .timer_manager import TimerClient, timerManager
from .utils import logger


class RemoteService(TimerClient):
    def __init__(self, owner):
        self.kb = owner.knowledge
        self._owner = owner
        self._is_initialised = False
        self._timers = []
        self._is_running = False

    def init(self):
        return self.is_initialised

    def start(self):
        if self.is_initialised:
            self._is_running = True

    def stop(self):
        self._is_running = False

    @property
    def is_initialised(self):
        return self._is_initialised

    @property
    def is_running(self):
        return self._is_running

    def register_for_timer(self, interval):
        if (
            not isinstance(interval, float)
            and not isinstance(interval, int)
            and interval <= 0
        ):
            logger.error(f"register_for_timer: invalid time interval {interval}")
            return

        tid = timerManager.add_timer(self, init_start=interval, interval=interval)
        self._timers.append(tid)
        return tid

    async def on_timer_lapsed(self, tid):
        if tid in self._timers:
            del self._timers[self._timers.index(tid)]

    def cancel_timer(self, tid):
        if tid in self._timers:
            timerManager.del_timer(tid)
            del self._timers[self._timers.index(tid)]

    def cancel_timers(self):
        for tid in self._timers:
            timerManager.del_timer(tid)
        self._timers = []

    def fini(self):
        self.stop()
        self.cancel_timers()
        self._is_initialised = False
