"""Tests for the shared arithmetic helper, calculate and compare behaviours."""

import asyncio
import operator
import time

from lurawi.arithmetic import evaluate_operand
from lurawi.calculate import calculate
from lurawi.callbackmsg_manager import RemoteCallbackMessageUpdateManager
from lurawi.compare import compare
from lurawi.usermsg_manager import UserMessageUpdateManager

OPS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.floordiv,
    "%": operator.mod,
    "!": operator.truediv,
}


def make_kb(extra=None):
    kb = {"MODULES": {}, "USER_INPUTS_CACHE": []}
    from threading import Lock

    kb["__MUTEX__"] = Lock()
    kb["MODULES"]["UserMessageManager"] = UserMessageUpdateManager(kb)
    kb["MODULES"]["RemoteCallbackMessageManager"] = RemoteCallbackMessageUpdateManager(kb)
    if extra:
        kb.update(extra)
    return kb


def test_evaluate_operand_basic():
    assert evaluate_operand("2+3", {}, OPS) == 5
    assert evaluate_operand("2*3+4", {}, OPS) == 10
    assert evaluate_operand("10-3", {}, OPS) == 7
    assert evaluate_operand("10/3", {}, OPS) == 3
    assert evaluate_operand("7%3", {}, OPS) == 1
    assert evaluate_operand("time", {}, OPS) == int(time.time())


def test_evaluate_operand_kb_and_float():
    kb = {"A": "10", "B": 5, "C": "2.5"}
    assert evaluate_operand("A+B", kb, OPS) == 15
    assert evaluate_operand("C", kb, OPS) == 2.5
    assert evaluate_operand("A*B", kb, OPS) == 50


def test_evaluate_operand_invalid():
    # numeric + non-numeric operand -> None
    assert evaluate_operand("A+foo", {"A": "1"}, OPS) is None
    # multiplication reflects onto the string (pre-existing quirk) -> non-None
    assert evaluate_operand("A*foo", {"A": "1"}, OPS) == "foo"


def test_calculate_run_success():
    kb = make_kb({"NUM": 5})
    c = calculate(kb, "RESULT", "NUM+2")
    asyncio.run(c.run())
    assert kb["RESULT"] == 7


def test_calculate_run_time():
    kb = make_kb()
    c = calculate(kb, "T", "time")
    asyncio.run(c.run())
    assert isinstance(kb["T"], int)


def test_calculate_run_invalid_operand():
    kb = make_kb()
    c = calculate(kb, "R", "NOPE+1")
    failed = []

    async def on_fail(*a):
        failed.append(True)

    c.on_failure = on_fail
    asyncio.run(c.run())
    assert failed == [True]


def test_calculate_run_non_dict_kb():
    c = calculate(make_kb(), "R", "1")
    c.kb = "notdict"
    calls = []

    async def fake_failed(*a):
        calls.append(True)

    c.failed = fake_failed
    asyncio.run(c.run())
    assert calls == [True]


def test_compare_run_true_false():
    kb = make_kb({"A": 5})
    c = compare(
        kb,
        {
            "operand1": "A",
            "operand2": "3",
            "comparison_operator": ">",
            "true_action": ["text", "t"],
        },
    )
    success = []

    async def on_ok(name, action):
        success.append(action)

    c.on_success = on_ok
    asyncio.run(c.run())
    assert success == [["text", "t"]]


def test_compare_run_false_action():
    kb = make_kb({"A": 1})
    c = compare(
        kb,
        {
            "operand1": "A",
            "operand2": "3",
            "comparison_operator": ">",
            "false_action": ["text", "f"],
        },
    )
    success = []

    async def on_ok(name, action):
        success.append(action)

    c.on_success = on_ok
    asyncio.run(c.run())
    assert success == [["text", "f"]]


def test_compare_run_no_action():
    kb = make_kb({"A": 5})
    c = compare(kb, {"operand1": "A", "operand2": "3", "comparison_operator": ">"})
    success = []

    async def on_ok(name, action):
        success.append(True)

    c.on_success = on_ok
    asyncio.run(c.run())
    assert success == [True]


def test_compare_run_invalid_details():
    c = compare(make_kb(), {"operand1": "1"})  # missing operand2/operator
    failed = []

    async def on_fail(*a):
        failed.append(True)

    c.on_failure = on_fail
    asyncio.run(c.run())
    assert failed == [True]


def test_compare_run_invalid_operator():
    c = compare(make_kb(), {"operand1": "1", "operand2": "2", "comparison_operator": "@"})
    failed = []

    async def on_fail(*a):
        failed.append(True)

    c.on_failure = on_fail
    asyncio.run(c.run())
    assert failed == [True]


def test_compare_run_comp_op_in_operand():
    c = compare(make_kb(), {"operand1": "1>2", "operand2": "3", "comparison_operator": ">"})
    failed = []

    async def on_fail(*a):
        failed.append(True)

    c.on_failure = on_fail
    asyncio.run(c.run())
    assert failed == [True]
