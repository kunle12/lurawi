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
from threading import Thread
from lurawi.utils import logger


class TimerClient:
    """
    Base class for clients that want to receive timer events.
    
    Any class that needs to receive timer notifications should inherit from this class
    and override the on_timer and on_timer_lapsed methods.
    """
    def __init__(self):
        """
        Initialize a new TimerClient.
        
        Creates an empty timercontext dictionary that can be used to store
        timer-related data specific to this client.
        """
        self.timercontext = {}

    async def on_timer(self, tid: int):  # pylint: disable=unused-argument
        """
        Called when a timer fires.
        
        This method should be overridden by subclasses to implement
        custom behavior when a timer event occurs.
        
        Args:
            tid (int): The ID of the timer that fired
            
        Returns:
            None
        """
        logger.info("TimerClient: on_timer called")
        return

    async def on_timer_lapsed(self, tid: int):  # pylint: disable=unused-argument
        """
        Called when a timer has completed all its repetitions.
        
        This method should be overridden by subclasses to implement
        custom behavior when a timer completes.
        
        Args:
            tid (int): The ID of the timer that lapsed
            
        Returns:
            None
        """
        logger.info("TimerClient: on_timer_lapsed called")
        return


class TimerManager:
    """
    Central manager for creating and tracking timers.
    
    TimerManager runs an event loop in a separate thread to handle timer events
    asynchronously. It provides methods to create, manage, and remove timers.
    """
    def __init__(self) -> None:
        """
        Initialize a new TimerManager.
        
        Creates a new event loop in a separate thread and starts it.
        Initializes the timer tracking structures.
        """
        self._run_thread = None
        self._loop = asyncio.new_event_loop()
        self._timers = {}
        self._next_timer_id = 1
        self._run_thread = Thread(target=self._start_run_thread)
        self._run_thread.start()
        logger.info("TimerManager initialised")

    def fini(self) -> None:
        """
        Finalize and shut down the TimerManager.
        
        Cancels all active timers and stops the event loop.
        This method should be called when the TimerManager is no longer needed.
        
        Returns:
            None
        """
        logger.info("Shutting down TimerManager")
        if not self._run_thread:
            return

        for timer in self._timers.values():
            timer.cancel()

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._timers = {}

    def is_running(self) -> bool:
        """
        Check if the TimerManager is currently running.
        
        Returns:
            bool: True if the timer manager is running, False otherwise
        """
        return self._run_thread is not None

    def _start_run_thread(self) -> None:
        """
        Start the event loop in a separate thread.
        
        This is an internal method called during initialization.
        It sets up the event loop and handles any exceptions that occur.
        
        Returns:
            None
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
    ):
        """
        Add a new timer.
        
        Creates a new timer that will call the client's on_timer method according
        to the specified parameters.
        
        Args:
            client (TimerClient): The client that will receive timer events
            init_start (int, optional): Initial delay in seconds before the first event. Defaults to 0.
            interval (int, optional): Interval between timer events in seconds. Defaults to 1.
            repeats (int, optional): Number of times to repeat the timer. Defaults to -1 (infinite).
            
        Returns:
            int: The ID of the newly created timer
        """
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
        """
        Add a coroutine to be executed in the timer manager's event loop.
        
        Args:
            coro: The coroutine to execute
            
        Returns:
            asyncio.Future: A Future representing the execution of the coroutine
        """
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def del_timer(self, timer_id):
        """
        Delete a timer.
        
        Cancels the timer with the specified ID and removes it from the manager.
        
        Args:
            timer_id (int): The ID of the timer to delete
            
        Returns:
            None
            
        Note:
            Logs an error if the timer does not exist
        """
        if timer_id not in self._timers:
            logger.error("Timer %d does not exist", timer_id)
            return

        timer = self._timers[timer_id]
        timer.cancel()
        del self._timers[timer_id]


class BotTimer:
    """
    Individual timer implementation.
    
    Represents a single timer that can fire repeatedly at specified intervals.
    Each timer is associated with a client that receives notifications when the timer fires.
    """
    def __init__(
        self, tid, loop, client: TimerClient, init_start=0, interval=1, repeats=-1
    ):  # pylint: disable=too-many-arguments, too-many-positional-arguments
        """
        Initialize a new BotTimer.
        
        Args:
            tid (int): The timer ID
            loop (asyncio.AbstractEventLoop): The event loop to run the timer in
            client (TimerClient): The client that will receive timer events
            init_start (int, optional): Initial delay in seconds before the first event. Defaults to 0.
            interval (int, optional): Interval between timer events in seconds. Defaults to 1.
            repeats (int, optional): Number of times to repeat the timer. Defaults to -1 (infinite).
        """
        self.id = tid
        self._loop = loop
        self._client = client
        self._init_start = init_start
        self._repeats = repeats
        self._interval = interval
        self._is_running = True
        self._task = asyncio.run_coroutine_threadsafe(self._job(), self._loop)

    async def _job(self):
        """
        Internal coroutine that handles the timer's execution.
        
        This method is responsible for:
        1. Waiting for the initial delay
        2. Calling the client's on_timer method at the specified intervals
        3. Handling the repeat count
        4. Calling the client's on_timer_lapsed method when the timer completes
        
        Returns:
            None
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
        Check if the timer is currently active.
        
        Returns:
            bool: True if the timer is active, False otherwise
        """
        return self._is_running

    def cancel(self):
        """
        Cancel the timer.
        
        Stops the timer from firing any more events and marks it as inactive.
        
        Returns:
            None
        """
        self._task.cancel()
        self._is_running = False


# Global instance of TimerManager that can be imported and used throughout the application
timerManager = TimerManager()
