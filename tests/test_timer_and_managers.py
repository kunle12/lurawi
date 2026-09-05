"""Tests for TimerManager/BotTimer and the user/callback message managers."""

import asyncio

from lurawi.callbackmsg_manager import (
    RemoteCallbackMessageListener,
    RemoteCallbackMessageUpdateManager,
)
from lurawi.timer_manager import TimerClient, TimerManager, timerManager
from lurawi.usermsg_manager import UserMessageListener, UserMessageUpdateManager

# ---------------- TimerManager / BotTimer ----------------


def test_timer_client_defaults():
    tc = TimerClient()
    asyncio.run(tc.on_timer(1))
    asyncio.run(tc.on_timer_lapsed(1))


def test_timer_manager_add_del_is_running():
    tm = TimerManager()
    assert tm.is_running() is True
    t = tm.add_timer(TimerClient(), init_start=0, interval=1, repeats=1)
    assert t > 0
    assert t in tm._timers
    tm.del_timer(t)
    assert t not in tm._timers
    tm.del_timer(t)  # idempotent (logs error)
    tm.fini()
    assert tm.is_running() is False


def test_timer_manager_fini_idempotent():
    tm = TimerManager()
    tm.fini()
    tm.fini()


def test_bot_timer_is_active_and_cancel():
    tm = TimerManager()
    tid = tm.add_timer(TimerClient(), init_start=0, interval=1, repeats=-1)
    bt = tm._timers[tid]
    assert bt.is_active() is True
    bt.cancel()
    assert bt.is_active() is False
    tm.del_timer(tid)
    tm.fini()


def test_global_timer_manager_exists():
    assert isinstance(timerManager, TimerManager)
    timerManager.fini()


# ---------------- UserMessageUpdateManager ----------------


class UserListener(UserMessageListener):
    def __init__(self, result):
        self.result = result

    async def on_user_message_update(self, context):
        return self.result


def test_user_message_manager_register_deregister():
    kb = {"MODULES": {}}
    mgr = UserMessageUpdateManager(kb)
    assert kb["MODULES"]["UserMessageManager"] is mgr
    l1 = UserListener(True)
    mgr.register_for_user_message_updates(l1, [])
    mgr.register_for_user_message_updates(l1, [])  # duplicate insert
    mgr.deregister_for_user_message_updates(l1)
    mgr.deregister_for_user_message_updates(l1)  # no-op
    # invalid registration
    mgr.register_for_user_message_updates("notalistener", [])
    mgr.register_for_user_message_updates(l1, "notalist")


def test_user_message_manager_process_and_interests():
    kb = {"MODULES": {}}
    mgr = UserMessageUpdateManager(kb)
    seen = []

    async def handler(ctx):
        seen.append(ctx)
        return True

    listener = UserListener(True)
    listener.on_user_message_update = handler
    mgr.register_for_user_message_updates(listener, [])
    asyncio.run(mgr.process_user_messages({"message": "hi"}))
    assert seen == [{"message": "hi"}]
    # consumption -> stops propagation

    async def consume(ctx):
        return False

    listener2 = UserListener(True)
    listener2.on_user_message_update = consume
    mgr.register_for_user_message_updates(listener2, [])
    assert asyncio.run(mgr.process_user_messages({"message": "x"})) is False


def test_user_message_manager_interests_filter():
    kb = {"MODULES": {}}
    mgr = UserMessageUpdateManager(kb)
    seen = []

    async def handler(ctx):
        seen.append(ctx)
        return True

    listener = UserListener(True)
    listener.on_user_message_update = handler
    mgr.register_for_user_message_updates(listener, ["node_id"])
    # message lacks node_id -> filtered out
    asyncio.run(mgr.process_user_messages({"message": "hi"}))
    assert seen == []
    # message contains node_id -> delivered
    asyncio.run(mgr.process_user_messages({"node_id": "x", "message": "hi"}))
    assert seen == [{"node_id": "x", "message": "hi"}]


def test_user_message_manager_clear_and_fini():
    kb = {"MODULES": {}}
    mgr = UserMessageUpdateManager(kb)
    mgr.clear_user_message_listeners()
    mgr.fini()
    assert kb["MODULES"]["UserMessageManager"] is None


# ---------------- RemoteCallbackMessageUpdateManager ----------------


class CbListener(RemoteCallbackMessageListener):
    def __init__(self, result=True):
        self.result = result

    async def on_remote_callback_message_update(self, data):
        return self.result


def test_callback_message_manager_register_deregister():
    kb = {"MODULES": {}}
    mgr = RemoteCallbackMessageUpdateManager(kb)
    assert kb["MODULES"]["RemoteCallbackMessageManager"] is mgr
    listener = CbListener()
    mgr.register_for_remote_callback_message_updates(listener, ["m"])
    mgr.deregister_for_remote_callback_message_updates(listener)
    mgr.deregister_for_remote_callback_message_updates(listener)
    # invalid registration
    mgr.register_for_remote_callback_message_updates("x", ["m"])
    mgr.register_for_remote_callback_message_updates(listener, "notalist")


def test_callback_message_manager_process():
    kb = {"MODULES": {}}
    mgr = RemoteCallbackMessageUpdateManager(kb)
    seen = []

    async def handler(data):
        seen.append(data)
        return True

    listener = CbListener()
    listener.on_remote_callback_message_update = handler
    mgr.register_for_remote_callback_message_updates(listener, ["method_x"])
    # matching method -> delivered
    assert asyncio.run(mgr.process_remote_callback_messages("method_x", {"a": 1})) is True
    assert seen == [{"a": 1}]
    # non-matching method -> not delivered
    asyncio.run(mgr.process_remote_callback_messages("other", {"b": 2}))
    assert len(seen) == 1
    # consumption
    listener2 = CbListener(False)
    mgr.register_for_remote_callback_message_updates(listener2, ["method_x"])
    assert asyncio.run(mgr.process_remote_callback_messages("method_x", {})) is False


def test_callback_message_manager_clear_and_fini():
    kb = {"MODULES": {}}
    mgr = RemoteCallbackMessageUpdateManager(kb)
    mgr.clear_remote_callback_message_listeners()
    mgr.fini()
    assert kb["MODULES"]["RemoteCallbackMessageManager"] is None
