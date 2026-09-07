"""Tests for CustomBehaviour base class and the DataStreamHandler."""

import pytest

from lurawi.callbackmsg_manager import RemoteCallbackMessageUpdateManager
from lurawi.custom_behaviour import CustomBehaviour, DataStreamHandler
from lurawi.usermsg_manager import UserMessageUpdateManager


def make_kb():
    kb = {"MODULES": {}, "USER_INPUTS_CACHE": []}
    from threading import Lock

    kb["__MUTEX__"] = Lock()
    kb["MESG_FUNC"] = None
    kb["MODULES"]["UserMessageManager"] = UserMessageUpdateManager(kb)
    kb["MODULES"]["RemoteCallbackMessageManager"] = RemoteCallbackMessageUpdateManager(kb)
    return kb


@pytest.mark.asyncio
async def test_init_sets_managers_and_message():
    kb = make_kb()
    cb = CustomBehaviour(kb, {"a": 1})
    assert cb.kb is kb
    assert cb.details == {"a": 1}
    assert cb._usermessage_manager is kb["MODULES"]["UserMessageManager"]
    assert cb._callback_manager is kb["MODULES"]["RemoteCallbackMessageManager"]
    # dummy message when no MESG_FUNC
    assert cb.message == cb._dummy_message
    # with a real MESG_FUNC
    kb["MESG_FUNC"] = lambda **kw: None
    cb2 = CustomBehaviour(kb)
    assert cb2.message is kb["MESG_FUNC"]


@pytest.mark.asyncio
async def test_dummy_message_logs():
    cb = CustomBehaviour(make_kb())
    await cb._dummy_message()  # must not raise


@pytest.mark.asyncio
async def test_parse_simple_input():
    cb = CustomBehaviour(make_kb(), {"key": "somevalue", "num": 5, "comp": ["hi {}", ["NAME"]]})
    cb.kb["NAME"] = "bob"
    assert cb.parse_simple_input("key", "str") == "somevalue"
    assert cb.parse_simple_input("num", "int") == 5
    assert cb.parse_simple_input("comp", "str") == "hi bob"
    # key resolves from kb
    cb.kb["ALIAS"] = "real"
    cb.details["key"] = "ALIAS"
    assert cb.parse_simple_input("key", "str") == "real"
    # missing -> None
    assert cb.parse_simple_input("missing", "str") is None
    # env fallback
    cb.kb["ENV_FALLBACK"] = "fb"
    assert cb.parse_simple_input("nope", "str", env_name="ENV_FALLBACK") == "fb"
    # non-dict details
    cb2 = CustomBehaviour(make_kb(), "notadict")
    assert cb2.parse_simple_input("x", "str") is None


@pytest.mark.asyncio
async def test_register_cancel_messages():
    kb = make_kb()
    cb = CustomBehaviour(kb)
    cb.register_for_user_message_updates(["a"])
    assert cb._registered_for_user_message is True
    # duplicate registration is a no-op
    cb.register_for_user_message_updates(["a"])
    cb.register_for_callback_message_updates(["m"])
    assert cb._registered_for_callback_message is True
    cb.cancel_user_message_updates()
    assert cb._registered_for_user_message is False
    cb.cancel_callback_message_updates()
    assert cb._registered_for_callback_message is False
    # cancelling when not registered is safe
    cb.cancel_user_message_updates()
    cb.cancel_callback_message_updates()


@pytest.mark.asyncio
async def test_succeeded_failed_and_log_result():
    kb = make_kb()
    cb = CustomBehaviour(kb, {"success_action": ["text", "ok"], "failed_action": ["text", "no"]})
    calls = []

    async def on_success(action, data):
        calls.append(("s", action, data))

    async def on_failure(action, data):
        calls.append(("f", action, data))

    cb.on_success = on_success
    cb.on_failure = on_failure
    await cb.succeeded()
    await cb.succeeded()
    assert calls[0][0] == "s"
    await cb.failed()
    assert calls[-1][0] == "f"
    assert kb["ERROR_MESSAGE"] == ""
    # log_result
    cb.log_result("hello, world")
    assert kb["USER_INPUTS_CACHE"] == [
        ("hello world", pytest.approx(kb["USER_INPUTS_CACHE"][0][1], abs=2))
    ]


@pytest.mark.asyncio
async def test_suspension_flow():
    kb = make_kb()
    cb = CustomBehaviour(kb)
    assert cb.is_suspendable() is False
    cb.can_suspend(True)
    assert cb.is_suspendable() is True
    # default on_suspension returns False -> not suspended
    assert cb.goto_suspension() is False
    assert cb.is_suspended() is False
    # custom suspend/restore
    cb2 = CustomBehaviour(kb)
    cb2.can_suspend(True)
    cb2.on_suspension = lambda d: True
    assert cb2.goto_suspension("x") is True
    assert cb2.is_suspended() is True
    assert cb2.restore_from_suspension() is True
    assert cb2.is_suspended() is False
    # restore when not suspended returns True
    assert cb2.restore_from_suspension() is True
    # goto when already suspended returns True
    cb2.goto_suspension()
    assert cb2.goto_suspension() is True


@pytest.mark.asyncio
async def test_fini():
    kb = make_kb()
    cb = CustomBehaviour(kb)
    cb.register_for_user_message_updates([])
    cb.register_for_callback_message_updates([])
    cb.fini()
    assert cb._registered_for_user_message is False
    assert cb._registered_for_callback_message is False


@pytest.mark.asyncio
async def test_data_stream_handler():
    async def gen():
        delta = type("D", (), {"content": "hello"})()
        choice = type("C", (), {"delta": delta})()
        chunk = type("Chunk", (), {"choices": [choice]})()
        yield chunk

    cb = CustomBehaviour(make_kb(), {"response": "OUT"})
    succeeded = []

    async def on_success(*a):
        succeeded.append(True)

    cb.on_success = on_success

    handler = DataStreamHandler(gen(), cb)
    chunks = []
    async for c in handler.stream_generator():
        chunks.append(c)
    assert any("hello" in c for c in chunks)
    assert succeeded == [True]
    assert cb.kb["OUT"] == "hello"


@pytest.mark.asyncio
async def test_data_stream_handler_no_callback():
    async def gen():
        delta = type("D", (), {"content": None})()
        choice = type("C", (), {"delta": delta})()
        chunk = type("Chunk", (), {"choices": [choice]})()
        yield chunk

    handler = DataStreamHandler(gen(), None)
    async for c in handler.stream_generator():
        pass
    # no callback -> nothing to fail
