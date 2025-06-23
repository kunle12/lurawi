"""
User Message Manager Module for the Lurawi System.

This module provides classes for handling user message updates in the Lurawi system.
It defines a listener interface for objects that want to receive user message updates
and a manager class that handles registration and distribution of messages to listeners.

The module enables components to:
- Register for user message updates
- Process and respond to user messages
- Filter messages based on interests
"""

from typing import Dict, List
from lurawi.utils import logger


class UserMessageListener:
    """
    Base class for objects that want to receive user message updates.
    
    Any class that needs to receive user message updates should inherit from this class
    and override the on_user_message_update method.
    """
    def __init__(self):
        """
        Initializes a new UserMessageListener.
        
        This is a placeholder initialization method that subclasses can override
        if they need specific initialization logic.
        """

    async def on_user_message_update(self, context: Dict = {}):
        """
        Handles incoming user message updates.
        
        This method is invoked when a user message is received. Subclasses should
        override this method to implement custom behaviour for processing the message.
        
        Args:
            context (Dict): A dictionary containing the user message data and context.
                            Defaults to an empty dictionary.
            
        Returns:
            bool:
                - True: Allows the message to be passed to other registered listeners.
                - False: Consumes the message, preventing further processing by subsequent listeners.
        """
        return True  # allow node status message to be passed on


class UserMessageUpdateManager:
    """
    Manages the registration and distribution of user message updates to listeners.
    
    This class provides functionality to:
    - Register `UserMessageListener` objects to receive updates.
    - Deregister listeners.
    - Process incoming user messages and distribute them to interested listeners.
    - Clear all registered listeners.
    """
    def __init__(self, kb: Dict):
        """
        Initializes a new UserMessageUpdateManager.
        
        Args:
            kb (Dict): The knowledge base dictionary where the manager will store
                       itself under the "MODULES.UserMessageManager" key.
            
        Note:
            The manager automatically registers itself in the knowledge base
            under `kb["MODULES"]["UserMessageManager"]`.
        """
        self.listeners: List[tuple[UserMessageListener, List[str]]] = []
        self.knowledge = kb
        self.knowledge["MODULES"]["UserMessageManager"] = self

    def register_for_user_message_updates(self, callable_obj: UserMessageListener, interests: List[str] = []):
        """
        Registers an object to receive user message updates.
        
        Listeners are added to the front of the list, giving them higher priority
        in message processing.
        
        Args:
            callable_obj (UserMessageListener): The object to register. Must be an
                                                instance of `UserMessageListener`.
            interests (List[str], optional): A list of message types (e.g., node IDs)
                                             that this object is interested in.
                                             Defaults to an empty list, meaning all messages.
            
        Raises:
            TypeError: If `callable_obj` is not an instance of `UserMessageListener`.
            TypeError: If `interests` is not a list of strings.
        """
        if not isinstance(callable_obj, UserMessageListener):
            logger.error(
                "%s is not a UserMessageListener", callable_obj.__class__.__name__
            )
            return
        if interests is not None and not isinstance(interests, list):
            logger.error(
                "%s's interests must be a list of node_id string",
                callable_obj.__class__.__name__,
            )
            return

        self.listeners.insert(0, (callable_obj, interests))

    def deregister_for_user_message_updates(self, callable_obj: UserMessageListener):
        """
        Deregisters an object from receiving user message updates.
        
        Args:
            callable_obj (UserMessageListener): The object to deregister.
        """
        found = None
        for i, (k, v) in enumerate(self.listeners):
            if k == callable_obj:
                found = i
                break

        if found is not None:
            del self.listeners[found]

    async def process_user_messages(self, message: Dict):
        """
        Processes a user message by distributing it to registered listeners.
        
        This method iterates through registered listeners in order of priority (newest first).
        If a listener's `on_user_message_update` method returns `False` or `None`,
        the message is considered consumed, and further distribution is halted.
        
        Args:
            message (Dict): The user message data to be processed.
            
        Returns:
            bool:
                - True: If the message was processed by all listeners or no listener consumed it.
                - False: If a listener explicitly consumed the message (returned `False` or `None`).
        """
        for k, _ in self.listeners:
            ret = await k.on_user_message_update(message)
            if (
                ret is None or ret is False
            ):  # the listener has consume the message and don't pass on
                return False
        return True

    def clear_user_message_listeners(self):
        """
        Clears all registered listeners from the manager.
        
        This effectively removes all objects from the list of registered listeners,
        preventing them from receiving future user message updates.
        """
        self.listeners = []

    def fini(self):
        """
        Finalizes the UserMessageUpdateManager.
        
        This method performs necessary cleanup by:
        1. Clearing all registered listeners.
        2. Removing the manager's reference from the knowledge base.
        
        This method should be called when the manager instance is no longer needed
        to ensure proper resource release and prevent memory leaks.
        """
        self.clear_user_message_listeners()
        self.knowledge["MODULES"]["UserMessageManager"] = None
