"""
Timer Management Module for the Lurawi System.

This module provides classes for creating and managing timers in an asynchronous environment.
It enables scheduling of timed events with configurable intervals and repetitions.

The module includes:
- TimerClient: Base class for objects that want to receive timer events
- TimerManager: Central manager for creating and tracking timers
- BotTimer: Individual timer implementation

The module creates a global TimerManager instance (timerManager) that can be imported
and used throughout the application.
"""

import asyncio
from typing import Dict
from threading import Thread
from lurawi.utils import logger


class TimerClient:
    """
    Base class for clients that wish to receive timer events.

    Classes that need to be notified of timer events should inherit from
    `TimerClient` and override the `on_timer` and `on_timer_lapsed` methods
    to implement their specific logic.
    """
    def __init__(self):
        """
        Initializes a new TimerClient instance.

        An empty `timercontext` dictionary is created, which can be used by
        subclasses to store timer-related data specific to this client.
        """
        self.timercontext = {}

    async def on_timer(self, tid: int):  # pylint: disable=unused-argument
        """
        Callback method invoked when a timer fires.

        Subclasses should override this method to define custom behaviour
        that executes each time the associated timer's interval elapses.

        Args:
            tid (int): The unique identifier of the timer that fired.
        """
        logger.info("TimerClient: on_timer called")
        return

    async def on_timer_lapsed(self, tid: int):  # pylint: disable=unused-argument
        """
        Callback method invoked when a timer has completed all its repetitions.

        Subclasses should override this method to define custom behaviour
        that executes once the associated timer has finished its lifecycle.

        Args:
            tid (int): The unique identifier of the timer that lapsed.
        """
        logger.info("TimerClient: on_timer_lapsed called")
        return


class TimerManager:
    """
    Centralized manager for creating, tracking, and controlling timers.

    `TimerManager` operates an asynchronous event loop in a dedicated thread
    to handle timer events efficiently without blocking the main application flow.
    It provides an interface for adding, managing, and removing `BotTimer` instances.
    """
    def __init__(self) -> None:
        """
        Initializes a new TimerManager instance.

        A new asyncio event loop is created and started in a separate thread.
        Internal data structures for tracking timers are initialized, and a
        unique ID counter for new timers is set up.
        """
        self._run_thread: Thread | None = None
        self._loop = asyncio.new_event_loop()
        self._timers: Dict[int, BotTimer] = {}
        self._next_timer_id = 1
        self._run_thread = Thread(target=self._start_run_thread)
        self._run_thread.start()
        logger.info("TimerManager initialised")

    def fini(self) -> None:
        """
        Finalizes and gracefully shuts down the TimerManager.

        This method cancels all currently active timers and stops the underlying
        asyncio event loop. It should be called when the `TimerManager` instance
        is no longer required to ensure proper resource cleanup.
        """
        logger.info("Shutting down TimerManager")
        if not self._run_thread:
            return

        for timer in list(self._timers.values()):  # Iterate over a copy to allow modification
            timer.cancel()

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._timers = {}

    def is_running(self) -> bool:
        """
        Checks if the TimerManager's internal event loop thread is active.

        Returns:
            bool: `True` if the timer manager is running, `False` otherwise.
        """
        return self._run_thread is not None and self._run_thread.is_alive()

    def _start_run_thread(self) -> None:
        """
        Internal method to start the asyncio event loop in a separate thread.

        This method is executed by the dedicated thread created during
        `TimerManager` initialization. It sets the event loop for the thread
        and runs it indefinitely until explicitly stopped. Any exceptions
        during the event loop's execution are logged.
        """
        try:
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unable to run event loop, error %s", e)

        self._run_thread = None

    def add_timer(
        self,
        client: TimerClient,
        init_start: int = 0,
        interval: int = 1,
        repeats: int = -1,
    ) -> int:
        """
        Adds a new timer to be managed.

        A new `BotTimer` instance is created and configured to call the
        `client`'s `on_timer` method based on the specified parameters.

        Args:
            client (TimerClient): The client object that will receive timer events.
                                  Must be an instance of `TimerClient` or its subclass.
            init_start (int, optional): The initial delay in seconds before the
                                        first timer event fires. Defaults to 0.
            interval (int, optional): The interval in seconds between subsequent
                                      timer events. Defaults to 1.
            repeats (int, optional): The number of times the timer should repeat.
                                     -1 indicates infinite repetitions. Defaults to -1.

        Returns:
            int: The unique ID assigned to the newly created timer.
        """
        timer_id = self._next_timer_id
        self._next_timer_id += 1
        self._timers[timer_id] = BotTimer(
            tid=timer_id,
            loop=self._loop,
            client=client,
            init_start=init_start,
            interval=interval,
            repeats=repeats,
        )
        return timer_id

    def add_task(self, coro) -> asyncio.Future:
        """
        Adds a coroutine to be executed within the timer manager's event loop.

        This allows other asynchronous tasks to be scheduled and run in the
        same event loop that manages the timers.

        Args:
            coro: The coroutine function or coroutine object to be executed.

        Returns:
            asyncio.Future: A Future object representing the eventual result
                             of the coroutine's execution.
        """
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def del_timer(self, timer_id: int) -> None:
        """
        Deletes and cancels a specific timer.

        If the timer with the given `timer_id` exists, it is cancelled and
        removed from the manager's tracking. An error is logged if the timer
        does not exist.

        Args:
            timer_id (int): The unique ID of the timer to be deleted.
        """
        if timer_id not in self._timers:
            logger.error("Timer %d does not exist", timer_id)
            return

        timer = self._timers[timer_id]
        timer.cancel()
        del self._timers[timer_id]


class BotTimer:
    """
    Represents an individual timer instance with configurable firing behaviour.

    Each `BotTimer` is designed to fire repeatedly at specified intervals and
    is associated with a `TimerClient` that receives notifications when the
    timer events occur.
    """
    def __init__(
        self, tid: int, loop: asyncio.AbstractEventLoop, client: TimerClient,
        init_start: int = 0, interval: int = 1, repeats: int = -1
    ):  # pylint: disable=too-many-arguments, too-many-positional-arguments
        """
        Initializes a new BotTimer instance.

        Args:
            tid (int): The unique identifier for this timer.
            loop (asyncio.AbstractEventLoop): The asyncio event loop on which
                                              this timer's coroutine will run.
            client (TimerClient): The client object that will receive `on_timer`
                                  and `on_timer_lapsed` callbacks.
            init_start (int, optional): The initial delay in seconds before the
                                        first timer event. Defaults to 0.
            interval (int, optional): The interval in seconds between subsequent
                                      timer events. Defaults to 1.
            repeats (int, optional): The number of times the timer should repeat.
                                     -1 indicates infinite repetitions. Defaults to -1.
        """
        self.id = tid
        self._loop = loop
        self._client = client
        self._init_start = init_start
        self._repeats = repeats
        self._interval = interval
        self._is_running = True
        self._task = asyncio.run_coroutine_threadsafe(self._job(), self._loop)

    async def _job(self) -> None:
        """
        Internal asynchronous job that manages the timer's execution lifecycle.

        This coroutine handles the initial delay, repeatedly calls the client's
        `on_timer` method at the specified interval, manages the repetition count,
        and finally invokes the client's `on_timer_lapsed` method when the
        timer completes its cycle or is cancelled.
        """
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
        """
        Checks if the timer is currently active and running.

        Returns:
            bool: `True` if the timer is active, `False` otherwise.
        """
        return self._is_running

    def cancel(self) -> None:
        """
        Cancels the timer, stopping any further scheduled events.

        This method attempts to cancel the underlying asynchronous task and
        marks the timer as inactive, preventing `on_timer` callbacks from
        being invoked further.
        """
        self._task.cancel()
        self._is_running = False


# Global instance of TimerManager that can be imported and used throughout the application
timerManager = TimerManager()
