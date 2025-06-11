"""
Custom Behaviour Module for the Lurawi System.

This module provides the base class for implementing custom behaviors in the Lurawi system.
It defines the CustomBehaviour class which serves as a foundation for creating specific
behavior implementations that can respond to user messages and remote callbacks.

The module enables behaviors to:
- Register for and receive user message updates
- Register for and receive remote callback message updates
- Handle suspension and restoration states
- Log results and manage success/failure callbacks
- Clean up resources when no longer needed

Custom behaviors should inherit from the CustomBehaviour class and override
the run() method to implement their specific logic.
"""

from time import time
from typing import List, Optional, Callable, Awaitable, Any

from lurawi.callbackmsg_manager import RemoteCallbackMessageListener
from lurawi.usermsg_manager import UserMessageListener
from lurawi.utils import logger, check_type


class CustomBehaviour(UserMessageListener, RemoteCallbackMessageListener):
    """
    Base class for implementing custom behaviors in the Lurawi system.
    
    This class provides functionality for handling user messages and remote callback messages,
    managing suspension states, and handling success/failure callbacks.
    
    Inherits from:
        UserMessageListener: For receiving user message updates
        RemoteCallbackMessageListener: For receiving remote callback message updates
    """
    def __init__(self, kb: dict = {}, details: dict = {}):
        """
        Initialize a new CustomBehaviour instance.
        
        Args:
            kb (dict): Knowledge base dictionary containing system modules and functions
            details (dict): Configuration details for this behavior
        """
        self.kb = kb
        self.details = details or {}
        self.on_success = Optional[Callable[[str, Any], Awaitable[None]]]
        self.on_failure = Optional[Callable[[str, Any], Awaitable[None]]]
        self._usermessage_manager = kb["MODULES"]["UserMessageManager"]
        self._callback_manager = kb["MODULES"]["RemoteCallbackMessageManager"]
        self._registered_for_user_message = False
        self._registered_for_callback_message = False
        self._is_suspendable = False
        self._is_suspended = False

        if "MESG_FUNC" in kb and callable(kb["MESG_FUNC"]):
            self.message = kb["MESG_FUNC"]
        else:
            self.message = self._dummy_message

    async def run(self):
        """
        Main execution method for the behavior.
        
        This method should be overridden by subclasses to implement
        the specific behavior logic.
        
        Returns:
            None
        """

    def parse_simple_input(self, key: str, check_for_type: str, env_name: str = ""):
        """
        Parse and validate input from the details dictionary.
        
        Attempts to retrieve a value from the details dictionary using the provided key.
        If the value is a string that matches a key in the knowledge base, retrieves that
        value instead. If no value is found and an environment name is provided, attempts
        to retrieve from the knowledge base.
        
        Args:
            key (str): The key to look up in the details dictionary
            check_for_type (str): The expected type of the value
            env_name (str, optional): Fallback environment variable name to check in the 
            knowledge base
            
        Returns:
            Any: The retrieved value if it matches the expected type, otherwise None
        """
        if not isinstance(self.details, dict):
            return None

        data = self.details.get(key)

        if isinstance(data, str) and data in self.kb:
            data = self.kb[data]

        if data is None and env_name and env_name in self.kb:
            data = self.kb[env_name]

        if check_type(data, check_for_type):
            return data

        return None

    def register_for_user_message_updates(self, interests: List[str] = []): # pylint: disable=dangerous-default-value
        """
        Register this behavior to receive user message updates.
        
        Args:
            interests (List[str], optional): List of message types this behavior is interested in
            
        Returns:
            None
            
        Note:
            Using an empty list as default parameter is typically discouraged but allowed here
            as indicated by the pylint disable comment.
        """
        if self._registered_for_user_message:
            logger.warning(
                "%s already registered for receiving user message update",
                self.__class__.__name__,
            )
            return

        self._registered_for_user_message = True
        self._usermessage_manager.register_for_user_message_updates(self, interests)

    def cancel_user_message_updates(self):
        """
        Cancel registration for user message updates.
        
        Deregisters this behavior from receiving user message updates if it was previously
        registered.
        
        Returns:
            None
        """
        if not self._registered_for_user_message:
            return

        self._registered_for_user_message = False
        self._usermessage_manager.deregister_for_user_message_updates(self)

    def register_for_callback_message_updates(self, interests: List[str] = []): # pylint: disable=dangerous-default-value
        """
        Register this behavior to receive remote callback message updates.
        
        Args:
            interests (List[str], optional): List of callback types this behavior is interested in
            
        Returns:
            None
            
        Note:
            Using an empty list as default parameter is typically discouraged but allowed here
            as indicated by the pylint disable comment.
        """
        if self._registered_for_callback_message:
            logger.warning(
                "%s already registered for receiving remote service callback update",
                self.__class__.__name__,
            )
            return

        self._registered_for_callback_message = True
        self._callback_manager.register_for_remote_callback_message_updates(
            self, interests
        )

    def cancel_callback_message_updates(self):
        """
        Cancel registration for remote callback message updates.
        
        Deregisters this behavior from receiving remote callback message updates
        if it was previously registered.
        
        Returns:
            None
        """
        if not self._registered_for_callback_message:
            return

        self._registered_for_callback_message = False
        self._callback_manager.deregister_for_remote_callback_message_updates(self)

    async def succeeded(self, action=None):
        """
        Signal that this behavior has succeeded.
        
        Calls the on_success callback if it exists.
        
        Args:
            action (Any, optional): The action that succeeded. If not provided,
                                   uses the 'success_action' from details.
                                   
        Returns:
            None
        """
        if self.on_success and callable(self.on_success):
            await self.on_success(
                self.__class__.__name__,
                action if action else self.details.get("success_action"),
            )

    async def failed(self, action=None):
        """
        Signal that this behavior has failed.
        
        Calls the on_failure callback if it exists.
        
        Args:
            action (Any, optional): The action that failed. If not provided,
                                   uses the 'failed_action' from details.
                                   
        Returns:
            None
        """
        if self.on_failure and callable(self.on_failure):
            await self.on_failure(
                self.__class__.__name__,
                action if action else self.details.get("failed_action"),
            )

    async def _dummy_message(self):
        """
        Default implementation of the message method.
        
        This is used when no message function is provided in the knowledge base.
        
        Returns:
            None
        """
        logger.warning("message dispatch is not implemented")

    def log_result(self, data):
        """
        Log a result to the user inputs cache.
        
        Stores the provided data along with the current timestamp in the
        USER_INPUTS_CACHE if it exists in the knowledge base.
        
        Args:
            data (Any): The data to log
            
        Returns:
            None
        """
        if "USER_INPUTS_CACHE" in self.kb:
            self.kb["__MUTEX__"].acquire()
            if isinstance(data, str):
                data = data.replace(",", "")
            self.kb["USER_INPUTS_CACHE"].append((data, time()))
            self.kb["__MUTEX__"].release()

    def is_suspendable(self):
        """
        Check if this behavior can be suspended.
        
        Returns:
            bool: True if this behavior can be suspended, False otherwise
        """
        return self._is_suspendable

    def can_suspend(self, isyes):
        """
        Set whether this behavior can be suspended.
        
        Args:
            isyes (bool): True if this behavior can be suspended, False otherwise
            
        Returns:
            None
        """
        self._is_suspendable = isyes

    def is_suspended(self):
        """
        Check if this behavior is currently suspended.
        
        Returns:
            bool: True if this behavior is suspended, False otherwise
        """
        return self._is_suspended

    def goto_suspension(self, data=None):
        """
        Attempt to suspend this behavior.
        
        Args:
            data (Any, optional): Data to pass to the on_suspension handler
            
        Returns:
            bool: True if suspension was successful, False otherwise
            
        Raises:
            None, but logs an error if the behavior is not suspendable or already suspended
        """
        if not self._is_suspendable:
            logger.error("%s is not suspendable", self.__class__.__name__)
            return False

        if self._is_suspended:
            logger.error("%s is already suspended", self.__class__.__name__)
            return True

        self._is_suspended = self.on_suspension(data)
        return self._is_suspended

    def restore_from_suspension(self, data=None):
        """
        Attempt to restore this behavior from suspension.
        
        Args:
            data (Any, optional): Data to pass to the on_restoration handler
            
        Returns:
            bool: True if restoration was successful, False otherwise
            
        Raises:
            None, but logs an error if the behavior is not suspended
        """
        if not self._is_suspended:
            logger.error("%s is not in suspension", self.__class__.__name__)
            return True

        return self.on_restoration(data)

    def on_suspension(self, data):
        """
        Handler called when the behavior is being suspended.
        
        This method should be overridden by subclasses that need to perform
        actions when being suspended.
        
        Args:
            data (Any): Data passed from goto_suspension
            
        Returns:
            bool: True if suspension was successful, False otherwise
        """
        return False

    def on_restoration(self, data):
        """
        Handler called when the behavior is being restored from suspension.
        
        This method should be overridden by subclasses that need to perform
        actions when being restored.
        
        Args:
            data (Any): Data passed from restore_from_suspension
            
        Returns:
            bool: True if restoration was successful, False otherwise
        """
        return True

    def fini(self):
        """
        Finalize this behavior.
        
        Cancels all message update registrations to clean up resources.
        This method should be called when the behavior is no longer needed.
        
        Returns:
            None
        """
        self.cancel_user_message_updates()
        self.cancel_callback_message_updates()
