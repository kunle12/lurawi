"""
Remote Service Module for the Lurawi System.

This module provides a base class for implementing remote services that can be
started, stopped, and can register for timer events. Remote services inherit from
TimerClient to receive timer notifications.

Remote services are used to interact with external systems or perform periodic
tasks within the Lurawi system.
"""

from .timer_manager import TimerClient, timerManager
from .utils import logger


class RemoteService(TimerClient):
    """
    Base class for remote services in the Lurawi system.
    
    This class provides common functionality for services that need to:
    - Be initialized and finalized
    - Be started and stopped
    - Register for and receive timer events
    
    Inherits from:
        TimerClient: For receiving timer events
    """
    def __init__(self, owner):
        """
        Initialize a new RemoteService.
        
        Args:
            owner: The owner object that contains the knowledge base
            
        Note:
            This initializes the service but does not start it.
            Call init() to initialize and start() to start the service.
        """
        super().__init__()  # Initialize the TimerClient base class
        self.kb = owner.knowledge
        self._owner = owner
        self._is_initialised = False
        self._timers = []
        self._is_running = False

    def init(self):
        """
        Initialize the service.
        
        This method should be overridden by subclasses to perform
        service-specific initialization.
        
        Returns:
            bool: True if the service is initialized, False otherwise
        """
        return self.is_initialised

    def start(self):
        """
        Start the service.
        
        The service will only start if it has been successfully initialized.
        
        Returns:
            None
        """
        if self.is_initialised:
            self._is_running = True

    def stop(self):
        """
        Stop the service.
        
        This stops the service from running but does not finalize it.
        The service can be restarted by calling start() again.
        
        Returns:
            None
        """
        self._is_running = False

    @property
    def is_initialised(self):
        """
        Check if the service is initialized.
        
        Returns:
            bool: True if the service is initialized, False otherwise
        """
        return self._is_initialised

    @property
    def is_running(self):
        """
        Check if the service is currently running.
        
        Returns:
            bool: True if the service is running, False otherwise
        """
        return self._is_running

    def register_for_timer(self, interval: int):
        """
        Register for timer events at the specified interval.
        
        Args:
            interval (int): The interval in seconds between timer events
            
        Returns:
            int: The timer ID if successful, None if the interval is invalid
            
        Note:
            The timer ID can be used to cancel the timer later using cancel_timer()
        """
        if interval <= 0:
            logger.error("register_for_timer: invalid time interval %d", interval)
            return

        tid = timerManager.add_timer(self, init_start=interval, interval=interval)
        self._timers.append(tid)
        return tid

    async def on_timer_lapsed(self, tid):
        """
        Handle timer lapsed events.
        
        This method is called when a timer has completed all its repetitions.
        It removes the timer ID from the list of active timers.
        
        Args:
            tid (int): The ID of the timer that lapsed
            
        Returns:
            None
        """
        if tid in self._timers:
            del self._timers[self._timers.index(tid)]

    def cancel_timer(self, tid):
        """
        Cancel a specific timer.
        
        Args:
            tid (int): The ID of the timer to cancel
            
        Returns:
            None
        """
        if tid in self._timers:
            timerManager.del_timer(tid)
            del self._timers[self._timers.index(tid)]

    def cancel_timers(self):
        """
        Cancel all timers registered by this service.
        
        Returns:
            None
        """
        for tid in self._timers:
            timerManager.del_timer(tid)
        self._timers = []

    def fini(self):
        """
        Finalize the service.
        
        This method:
        1. Stops the service if it's running
        2. Cancels all timers
        3. Marks the service as not initialized
        
        This method should be called when the service is no longer needed.
        
        Returns:
            None
        """
        self.stop()
        self.cancel_timers()
        self._is_initialised = False
