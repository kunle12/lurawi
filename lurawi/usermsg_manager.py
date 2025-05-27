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
from .utils import logger


class UserMessageListener(object):
    """
    Base class for objects that want to receive user message updates.
    
    Any class that needs to receive user message updates should inherit from this class
    and override the on_user_message_update method.
    """
    def __init__(self):
        """
        Initialize a new UserMessageListener.
        
        This is a placeholder initialization method that subclasses can override
        if they need specific initialization.
        """
        pass

    async def on_user_message_update(self, data: Dict = {}):
        """
        Handle user message updates.
        
        This method is called when a user message is received. Subclasses should
        override this method to implement custom behavior.
        
        Args:
            data (Dict): The user message data
            
        Returns:
            bool: True to allow the message to be passed to other listeners,
                  False to consume the message and prevent further processing
        """
        return True  # allow node status message to be passed on


class UserMessageUpdateManager(object):
    """
    Manager for user message updates.
    
    This class manages the registration of listeners for user message updates
    and handles the distribution of messages to registered listeners.
    """
    def __init__(self, kb):
        """
        Initialize a new UserMessageUpdateManager.
        
        Args:
            kb (dict): Knowledge base dictionary to store the manager reference
            
        Note:
            The manager registers itself in the knowledge base under MODULES.UserMessageManager
        """
        self.listeners = []  # list of tuples (listener, interests)
        self.knowledge = kb
        self.knowledge["MODULES"]["UserMessageManager"] = self

    def register_for_user_message_updates(self, callable_obj, interests: List[str] = []):
        """
        Register an object to receive user message updates.
        
        Args:
            callable_obj (UserMessageListener): The object to register
            interests (List[str], optional): List of message types this object is interested in
            
        Returns:
            None
            
        Note:
            The object must be an instance of UserMessageListener
            New listeners are added to the front of the list, giving them higher priority
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

    def deregister_for_user_message_updates(self, callable_obj):
        """
        Deregister an object from receiving user message updates.
        
        Args:
            callable_obj (UserMessageListener): The object to deregister
            
        Returns:
            None
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
        Process a user message by distributing it to registered listeners.
        
        This method calls the on_user_message_update method of each registered listener
        in order of registration (newest first). If any listener returns False or None,
        the message is considered consumed and not passed to further listeners.
        
        Args:
            message (Dict): The user message to process
            
        Returns:
            bool: True if the message was processed by all listeners or none consumed it,
                  False if a listener consumed the message
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
        Clear all registered listeners.
        
        This removes all objects from the list of registered listeners.
        
        Returns:
            None
        """
        self.listeners = []

    def fini(self):
        """
        Finalize the manager.
        
        This method:
        1. Clears all registered listeners
        2. Removes the manager reference from the knowledge base
        
        This method should be called when the manager is no longer needed.
        
        Returns:
            None
        """
        self.clear_user_message_listeners()
        self.knowledge["MODULES"]["UserMessageManager"] = None
