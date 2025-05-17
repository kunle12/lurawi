from time import time
from typing import List

from .callbackmsg_manager import RemoteCallbackMessageListener
from .usermsg_manager import UserMessageListener
from .utils import logger, check_type


class CustomBehaviour(UserMessageListener, RemoteCallbackMessageListener):
    def __init__(self, kb: dict = {}, details: dict = {}):
        self.kb = kb
        self.details = details or {}
        self.onSuccess = None
        self.onFailure = None
        self._usermessage_manager = kb["MODULES"]["UserMessageManager"]
        self._callback_manager = kb["MODULES"]["RemoteCallbackMessageManager"]
        self._registered_for_user_message = False
        self._registered_for_callback_message = False
        self.is_suspendable = False
        self.is_suspended = False

        if "MESG_FUNC" in kb and callable(kb["MESG_FUNC"]):
            self.message = kb["MESG_FUNC"]
        else:
            self.message = self._dummy_message

    async def run(self):
        pass

    def parse_simple_input(self, key: str, check_for_type: str, env_name: str = ""):
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

    def register_for_user_message_updates(self, interests: List[str] = []):
        if self._registered_for_user_message:
            logger.warning(
                f"{self.__class__.__name__} already registered for receiving user message update"
            )
            return

        self._registered_for_user_message = True
        self._usermessage_manager.register_for_user_message_updates(self, interests)

    def cancel_user_message_updates(self):
        if not self._registered_for_user_message:
            return

        self._registered_for_user_message = False
        self._usermessage_manager.deregister_for_user_message_updates(self)

    def register_for_callback_message_updates(self, interests: List[str] = []):
        if self._registered_for_callback_message:
            logger.warning(
                f"{self.__class__.__name__} already registered for receiving remote service callback update"
            )
            return

        self._registered_for_callback_message = True
        self._callback_manager.register_for_remote_callback_message_updates(
            self, interests
        )

    def cancel_callback_message_updates(self):
        if not self._registered_for_callback_message:
            return

        self._registered_for_callback_message = False
        self._callback_manager.deregister_for_remote_callback_message_updates(self)

    async def succeeded(self, action=None):
        if self.onSuccess and callable(self.onSuccess):
            await self.onSuccess(
                self.__class__.__name__,
                action if action else self.details.get("success_action"),
            )

    async def failed(self, action=None):
        if self.onFailure and callable(self.onFailure):
            await self.onFailure(
                self.__class__.__name__,
                action if action else self.details.get("failed_action"),
            )

    async def _dummy_message(self):
        logger.warning("message dispatch is not implemented")

    def log_result(self, data):
        if "USER_INPUTS_CACHE" in self.kb:
            self.kb["__MUTEX__"].acquire()
            if isinstance(data, str):
                data = data.replace(",", "")
            self.kb["USER_INPUTS_CACHE"].append((data, time()))
            self.kb["__MUTEX__"].release()

    def isSuspendable(self):
        return self.is_suspendable

    def canSuspend(self, isyes):
        self.is_suspendable = isyes

    def isSuspended(self):
        return self.is_suspended

    def gotoSuspension(self, data=None):
        if not self.is_suspendable:
            logger.error(f"{self.__class__.__name__} is not suspendable")
            return False

        if self.is_suspended:
            logger.error(f"{self.__class__.__name__} is already suspended")
            return True

        self.is_suspended = self.onSuspension(data)
        return self.is_suspended

    def restoreFromSuspension(self, data=None):
        if not self.is_suspended:
            logger.error(f"{self.__class__.__name__ } is not in suspension")
            return True

        return self.onRestoration(data)

    def onSuspension(self, data):
        return False

    def onRestoration(self, data):
        return True

    def fini(self):
        self.cancel_user_message_updates()
        self.cancel_callback_message_updates()
