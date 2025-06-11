"""Remote callback message management for Lurawi.

This module provides classes for handling remote callback messages in the Lurawi system.
It implements a listener pattern where objects can register to receive notifications
about specific remote callback messages, allowing for decoupled communication between
components.
"""

from typing import Dict, List, cast
from lurawi.utils import logger


class RemoteCallbackMessageListener:
    """Base class for objects that want to listen for remote callback messages.

    This class defines the interface that must be implemented by any object
    that wants to receive remote callback message updates. Subclasses should
    override the on_remote_callback_message_update method to handle messages.
    """

    def __init__(self):
        """Initialize a new RemoteCallbackMessageListener."""

    async def on_remote_callback_message_update(
        self, data: Dict = {}
    ):  # pylint: disable=unused-argument, dangerous-default-value
        """Handle a remote callback message update.

        This method is called when a remote callback message is received.
        The default implementation allows the message to be passed on to other listeners.

        Args:
            data: Dictionary containing the message data

        Returns:
            bool: True to allow the message to be passed on to other listeners,
                  False to consume the message and prevent further processing
        """
        return True  # allow node status message to be passed on


class RemoteCallbackMessageUpdateManager:
    """Manager for remote callback message updates.

    This class manages the distribution of remote callback messages to registered listeners.
    It maintains a list of listeners and their interests, and routes incoming messages
    to the appropriate listeners based on those interests.
    """

    def __init__(self, kb):
        """Initialize a new RemoteCallbackMessageUpdateManager.

        Args:
            kb: Knowledge base dictionary to store the manager reference
        """
        self.listeners = []  # list of tuples
        self.knowledge = kb
        self.knowledge["MODULES"]["RemoteCallbackMessageManager"] = self

    def register_for_remote_callback_message_updates(
        self, callableObj, interests: List[str] = []
    ):
        """Register a listener for remote callback message updates.

        Args:
            callableObj: Object that implements RemoteCallbackMessageListener
            interests: List of method names the listener is interested in
        """
        if not isinstance(callableObj, RemoteCallbackMessageListener):
            logger.error(
                "%s is not a RemoteCallbackMessageListener",
                callableObj.__class__.__name__,
            )
            return
        if interests is not None and not isinstance(interests, list):
            logger.error(
                "%s's interests must be a list of node_id string",
                callableObj.__class__.__name__,
            )
            return

        self.listeners.insert(0, (callableObj, interests))

    def deregister_for_remote_callback_message_updates(self, callableObj):
        """Remove a listener from receiving remote callback message updates.

        Args:
            callableObj: The listener object to deregister
        """
        found = None
        for i, (k, v) in enumerate(self.listeners):
            if k == callableObj:
                found = i
                break

        if found is not None:
            del self.listeners[found]

    async def process_remote_callback_messages(self, method: str, message: Dict):
        """Process incoming remote callback messages.

        Routes the message to all registered listeners that have expressed
        interest in the specified method.

        Args:
            method: The method name associated with the message
            message: Dictionary containing the message data

        Returns:
            bool: True if the message should continue to be processed,
                  False if a listener has consumed the message
        """
        for k, interests in self.listeners:
            if method in interests:
                ret = await cast(
                    RemoteCallbackMessageListener, k
                ).on_remote_callback_message_update(message)
                if (
                    ret is None or ret is False
                ):  # the listener has consume the message and don't pass on
                    return False
        return True

    def clear_remote_callback_message_listeners(self):
        """Remove all registered listeners."""
        self.listeners = []

    def fini(self):
        """Clean up resources when the manager is being shut down.

        Removes all listeners and clears the manager reference from the knowledge base.
        """
        self.clear_remote_callback_message_listeners()
        self.knowledge["MODULES"]["RemoteCallbackMessageManager"] = None
