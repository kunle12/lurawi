from typing import Dict, List, cast
from .utils import logger


class RemoteCallbackMessageListener(object):
    def __init__(self):
        pass

    async def onRemoteCallbackMessageUpdate(self, data: Dict = {}):
        return True  # allow node status message to be passed on


class RemoteCallbackMessageUpdateManager(object):
    def __init__(self, kb):
        self.listeners = []  # list of tuples
        self.knowledge = kb
        self.knowledge["MODULES"]["RemoteCallbackMessageManager"] = self

    def register_for_remote_callback_message_updates(
        self, callableObj, interests: List[str] = []
    ):
        if not isinstance(callableObj, RemoteCallbackMessageListener):
            logger.error(
                f"{callableObj.__class__.__name__} is not a RemoteCallbackMessageListener"
            )
            return
        if interests is not None and not isinstance(interests, list):
            logger.error(
                f"{callableObj.__class__.__name__}'s interests must be a list of node_id string"
            )
            return

        self.listeners.insert(0, (callableObj, interests))

    def deregister_for_remote_callback_message_updates(self, callableObj):
        found = None
        for i, (k, v) in enumerate(self.listeners):
            if k == callableObj:
                found = i
                break

        if found is not None:
            del self.listeners[found]

    async def processRemoteCallbackMessages(self, method: str, message: Dict):
        for k, interests in self.listeners:
            if method in interests:
                ret = await cast(
                    RemoteCallbackMessageListener, k
                ).onRemoteCallbackMessageUpdate(message)
                if (
                    ret is None or ret is False
                ):  # the listener has consume the message and don't pass on
                    return False
        return True

    def clearRemoteCallbackMessageListeners(self):
        self.listeners = []

    def fini(self):
        self.clearRemoteCallbackMessageListeners()
        self.knowledge["MODULES"]["RemoteCallbackMessageManager"] = None
