from typing import Dict, List
from .utils import logger


class UserMessageListener(object):
    def __init__(self):
        pass

    async def on_user_message_update(self, data: Dict = {}):
        return True  # allow node status message to be passed on


class UserMessageUpdateManager(object):
    def __init__(self, kb):
        self.listeners = []  # list of tuples
        self.knowledge = kb
        self.knowledge["MODULES"]["UserMessageManager"] = self

    def register_for_user_message_updates(self, callableObj, interests: List[str] = []):
        if not isinstance(callableObj, UserMessageListener):
            logger.error(
                "%s is not a UserMessageListener", callableObj.__class__.__name__
            )
            return
        if interests is not None and not isinstance(interests, list):
            logger.error(
                "%s's interests must be a list of node_id string",
                callableObj.__class__.__name__,
            )
            return

        self.listeners.insert(0, (callableObj, interests))

    def deregister_for_user_message_updates(self, callableObj):
        found = None
        for i, (k, v) in enumerate(self.listeners):
            if k == callableObj:
                found = i
                break

        if found is not None:
            del self.listeners[found]

    async def process_user_messages(self, message: Dict):
        for k, _ in self.listeners:
            ret = await k.on_user_message_update(message)
            if (
                ret is None or ret is False
            ):  # the listener has consume the message and don't pass on
                return False
        return True

    def clear_user_message_listeners(self):
        self.listeners = []

    def fini(self):
        self.clear_user_message_listeners()
        self.knowledge["MODULES"]["UserMessageManager"] = None
