"""Tests for the ActivityManager core engine.

Covers behaviour loading, activity selection, actionlet dispatch, the
play_behaviour auto-advance chain, action completion/failure handling and
the message/response plumbing.
"""

import pytest

from lurawi.activity_manager import ActivityManager


def make_manager(actions=None, knowledge=None, uid="test_uid"):
    """Build an ActivityManager with a minimal two-behaviour config."""
    behaviour = {
        "default": "__init__",
        "behaviours": [
            {"name": "__init__", "actions": [[["play_behaviour", "main"]]]},
            {"name": "main", "actions": actions or [[["comment", "hello"]]]},
        ],
    }
    kb = {"USER_DATA": {}, "SOME_KEY": "some_value", "NUM": 5}
    if knowledge:
        kb.update(knowledge)
    return ActivityManager(uid, "Test", behaviour, kb)


async def run_play(manager, action):
    """Await play_action and return it (so tests can await it)."""
    return await manager.play_action("test_action", action)


@pytest.mark.asyncio
async def test_init_sets_knowledge_and_loads_behaviours():
    am = make_manager()
    assert am.knowledge["USER_ID"] == "test_uid"
    assert am.knowledge["USER_NAME"] == "Test"
    assert am.is_initialised is False
    assert am.active_behaviour == [[["play_behaviour", "main"]]]
    assert am.activity_index == -1
    assert am.knowledge["MODULES"]["ActivityManager"] is am
    assert am.usermessage_manager is not None
    assert am.callbackmessage_manager is not None


@pytest.mark.asyncio
async def test_init_idempotent_and_plays_next():
    am = make_manager()
    await am.init()
    assert am.is_initialised is True
    await am.init()  # second call is a no-op
    assert am.is_initialised is True


@pytest.mark.asyncio
async def test_load_behaviours_rejects_empty_and_corrupt():
    am = make_manager()
    assert am.load_behaviours({}) is False
    assert am.load_behaviours({"behaviours": []}) is False
    assert (
        am.load_behaviours({"default": "x", "behaviours": [{"name": "y", "actions": []}]}) is False
    )


@pytest.mark.asyncio
async def test_load_behaviours_force_clears_busy():
    am = make_manager()
    am.running_actions["comment"] = {"name": "comment"}
    assert am.load_behaviours({}) is False  # busy and not forced
    assert (
        am.load_behaviours(
            {"default": "__init__", "behaviours": [{"name": "__init__", "actions": []}]}, force=True
        )
        is True
    )


@pytest.mark.asyncio
async def test_select_activity_variants():
    am = make_manager()
    # numeric
    assert am.select_activity("1") is True
    assert am.activity_index == 0
    # previous from index 1 -> index -1
    am.activity_index = 1
    assert am.select_activity("previous") is True
    assert am.activity_index == -1
    # next returns True without changing index
    assert am.select_activity("next") is True
    # knowledge key resolution
    am.knowledge["NEXT_ACTIVITY"] = "1"
    assert am.select_activity("NEXT_ACTIVITY") is True
    # behaviour:index
    assert am.select_activity("main:1") is True
    # behaviour name only
    assert am.select_activity("main") is True
    # invalid
    assert am.select_activity("") is True
    assert am.select_activity("nope") is False
    assert am.select_activity("a:b:c") is False
    assert am.select_activity("main:x") is None


@pytest.mark.asyncio
async def test_set_active_behaviour_and_index_bounds():
    am = make_manager()
    assert am.set_active_behaviour("main") is True
    assert am.activity_index == -1
    assert am.set_active_behaviour("missing") is False
    assert am.set_activity_index(0) is True
    assert am.set_activity_index(-2) is False
    assert am.set_activity_index(5) is False


@pytest.mark.asyncio
async def test_is_busy():
    am = make_manager()
    am.actions_lined_up = True
    assert am.is_busy() is True
    am.actions_lined_up = False
    am.running_actions["comment"] = {"name": "comment"}
    assert am.is_busy() is True
    am.running_actions = {}
    assert am.is_busy() is False


@pytest.mark.asyncio
async def test_play_action_comment_and_name():
    am = make_manager()
    result = await run_play(am, [["comment", "ok"]])
    assert result is True
    assert am.running_actions == {}

    am2 = make_manager()
    await run_play(am2, [["name", "ALIVE"]])
    # play_action sets current_action_id to the passed id
    assert am2.current_action_id == "test_action"


@pytest.mark.asyncio
async def test_play_action_text_variants():
    am = make_manager()
    # plain string
    await run_play(am, [["text", "hello world"]])
    # knowledge key resolution
    await run_play(am, [["text", "SOME_KEY"]])
    # template list
    await run_play(am, [["text", ["hi {} and {}", ["SOME_KEY", "NUM"]]]])
    # template with missing key -> replaces with underscore-spaced key
    await run_play(am, [["text", ["hi {}", ["MISSING_KEY"]]]])
    # error status -> sends 400
    await run_play(am, [["text", "unable to do it"]])
    # non-string arg
    await run_play(am, [["text", 42]])
    # invalid template list (second item not a list) -> failure path
    am2 = make_manager()
    await run_play(am2, [["text", ["hi", "notalist"]]])
    assert am2.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_http_response():
    am = make_manager()
    # valid success response
    await run_play(am, [["http_response", {"status_code": 200, "data": {"x": 1}}]])
    # 4xx -> status failed (inverted branch fixed)
    await run_play(am, [["http_response", {"status_code": 404, "data": {}}]])
    # knowledge-key value substitution
    await run_play(am, [["http_response", {"status_code": 200, "val": "SOME_KEY"}]])
    # invalid: missing status_code
    am2 = make_manager()
    await run_play(am2, [["http_response", {"data": {}}]])
    assert am2.running_actions == {}
    # invalid: non-dict arg
    await run_play(am2, [["http_response", "string"]])


@pytest.mark.asyncio
async def test_play_action_knowledge_update():
    am = make_manager()
    await run_play(am, [["knowledge", {"NEW_KEY": "SOME_KEY"}]])
    assert am.knowledge["NEW_KEY"] == "some_value"
    await run_play(am, [["knowledge", {"TEMPLATE": ["hi {}", ["SOME_KEY"]]}]])
    assert am.knowledge["TEMPLATE"] == "hi some_value"
    await run_play(am, [["knowledge", {"PLAIN": 3}]])
    assert am.knowledge["PLAIN"] == 3
    # non-dict -> failure
    am2 = make_manager()
    await run_play(am2, [["knowledge", "notadict"]])
    assert am2.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_calculate():
    am = make_manager()
    await run_play(am, [["calculate", ["RESULT", "NUM+2"]]])
    assert am.knowledge["RESULT"] == 7
    await run_play(am, [["calculate", ["RESULT2", "time"]]])
    assert isinstance(am.knowledge["RESULT2"], int)
    # invalid operand -> failure
    am2 = make_manager()
    await run_play(am2, [["calculate", ["RES", "NOPE+1"]]])
    assert am2.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_compare():
    am = make_manager()
    await run_play(
        am,
        [["compare", {"operand1": "NUM", "operand2": "3", "comparison_operator": ">"}]],
    )
    assert am.knowledge["NUM"] == 5
    # invalid comparison operator
    am2 = make_manager()
    await run_play(
        am2, [["compare", {"operand1": "NUM", "operand2": "3", "comparison_operator": "@"}]]
    )
    assert am2.running_actions == {}
    # missing operand keys
    await run_play(am2, [["compare", {"operand1": "NUM"}]])
    # comparison operator inside operand -> None
    await run_play(
        am2, [["compare", {"operand1": "NUM>2", "operand2": "3", "comparison_operator": ">"}]]
    )


@pytest.mark.asyncio
async def test_play_action_random():
    am = make_manager()
    await run_play(am, [["random", ["PICK", [1, 2, 3]]]])
    assert am.knowledge["PICK"] in (1, 2, 3)
    # invalid random
    am2 = make_manager()
    await run_play(am2, [["random", ["PICK", "notalist"]]])
    assert am2.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_delay():
    am = make_manager()
    await run_play(am, [["delay", 0.01]])
    # non-positive -> failure path
    am2 = make_manager()
    await run_play(am2, [["delay", -1]])
    assert am2.running_actions == {}
    await run_play(am2, [["delay", "notanumber"]])


@pytest.mark.asyncio
async def test_play_action_workflow_interaction():
    am = make_manager()
    await run_play(
        am,
        [
            [
                "workflow_interaction",
                {"engagement": ["text", "hi"], "disengagement": ["text", "bye"]},
            ]
        ],
    )
    assert am.engagement_action == ["text", "hi"]
    assert am.disengagement_action == ["text", "bye"]
    am2 = make_manager()
    await run_play(am2, [["workflow_interaction", "bad"]])
    assert am2.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_unknown():
    am = make_manager()
    await run_play(am, [["not_an_action", "x"]])
    assert am.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_invalid_short_alet():
    am = make_manager()
    await run_play(am, [["x"]])
    assert am.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_play_behaviour_chain():
    am = make_manager(actions=[[["comment", "a"]], [["comment", "b"]], [["comment", "c"]]])
    ended = []
    am.activity_complete_cb = lambda: ended.append("END")
    await run_play(am, [["play_behaviour", "main"]])
    assert am.activity_index == 2
    assert am.continue_playing is False
    assert ended == ["END"]


@pytest.mark.asyncio
async def test_play_action_play_behaviour_list_and_fail():
    am = make_manager()
    await run_play(am, [["play_behaviour", [["name", "x"], ["comment", "y"]]]])
    assert am.running_actions == {}
    am2 = make_manager()
    await run_play(am2, [["play_behaviour", "missing"]])
    assert am2.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_select_behaviour():
    am = make_manager()
    await run_play(am, [["select_behaviour", "main"]])
    assert am.running_actions == {}
    am2 = make_manager()
    await run_play(am2, [["select_behaviour", "missing"]])
    assert am2.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_ignore_moves():
    am = make_manager()
    await am.play_action("test_action", [["comment", "x"]], ignore_moves=["comment"])
    assert am.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_custom_module_loaded():
    # current_datetime is a real custom module registered in sys.modules
    am = make_manager()
    await run_play(am, [["custom", {"name": "current_datetime", "args": {"output": "NOW"}}]])
    assert "NOW" in am.knowledge
    assert am.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_custom_failure():
    am = make_manager()
    await run_play(am, [["custom", {"name": "random_picker", "args": {"list": [], "output": "X"}}]])
    assert am.running_actions == {}
    # module not found
    await run_play(am, [["custom", {"name": "no_such_module", "args": {}}]])
    # non-dict arg
    await run_play(am, [["custom", "no_such_module"]])


@pytest.mark.asyncio
async def test_actionHandler_and_failHandler():
    am = make_manager()
    am.running_actions["comment"] = {"name": "comment"}
    await am.actionHandler("comment")
    assert am.running_actions == {}
    # failure handler
    am.running_actions["comment"] = {"name": "comment"}
    await am.actionFailHandler("comment")
    assert am.running_actions == {}
    # handler for unknown action logs and returns
    await am.actionHandler("unknown")
    await am.actionFailHandler("unknown")


@pytest.mark.asyncio
async def test_clear_running_actions():
    am = make_manager()
    am.running_actions["comment"] = {"name": "comment"}
    am.pending_actions = [["a", ["comment", "x"], None, None, False]]
    am.continue_playing = True
    am.clear_running_actions()
    assert am.running_actions == {}
    assert am.pending_actions == []
    assert am.continue_playing is False
    assert am.knowledge["NO_DISRUPTION"] == 0


@pytest.mark.asyncio
async def test_start_stop_user_workflow():
    am = make_manager()
    am.engagement_action = ["text", "eng"]
    am.disengagement_action = ["text", "dis"]
    # in_user_interaction blocks
    am.in_user_interaction = True
    assert await am.start_user_workflow(data={"message": "hi"}) is False
    am.in_user_interaction = False
    assert await am.start_user_workflow(data={"message": "hi"}) is not None
    await am.stop_user_workflow()
    assert am.knowledge["CURRENT_TURN_CONTEXT"] is None


@pytest.mark.asyncio
async def test_continue_workflow():
    am = make_manager()
    am.userdata_action = ["text", "ok"]
    assert await am.continue_workflow(data={"message": "hi"}) is True
    # with context
    assert await am.continue_workflow(context="ctx-1", data={"message": "hi"}) is True
    # with activity_id different from current context
    am.knowledge["CURRENT_TURN_CONTEXT"] = "ctx-1"
    assert await am.continue_workflow(activity_id="ctx-2", data={"message": "hi"}) is True


@pytest.mark.asyncio
async def test_pending_behaviour_loading():
    am = make_manager()
    assert (await am.load_pending_behaviour_if_exists()) is False
    # set pending and complete
    pending = {"default": "__init__", "behaviours": [{"name": "__init__", "actions": []}]}
    am.set_pending_behaviours(pending, {"EXTRA": "v"}, lambda: None)
    assert am.pending_behaviours == pending
    # invalid call logs error
    am.set_pending_behaviours(None, {}, None)


@pytest.mark.asyncio
async def test_update_knowledge_and_get_session():
    am = make_manager()
    am.update_knowledge({"A": 1})
    assert am.knowledge["A"] == 1
    am.update_knowledge("notdict")
    assert am.get_current_session_id() == ""


@pytest.mark.asyncio
async def test_send_message_and_get_response():
    am = make_manager()
    am.knowledge["CURRENT_TURN_CONTEXT"] = "ctx"
    am.knowledge["CURRENT_SESSION_ID"] = "sess"
    await am.send_message(status=200, data={"response": "hello"})
    resp = am.get_response()
    assert resp is not None
    assert resp.status_code == 200
    # get_response again -> 406
    resp2 = am.get_response()
    assert resp2.status_code == 406


@pytest.mark.asyncio
async def test_send_raw_message():
    am = make_manager()
    am.knowledge["CURRENT_TURN_CONTEXT"] = "ctx"
    await am.send_raw_message(200, {"x": 1})
    resp = am.get_response()
    assert resp is not None


@pytest.mark.asyncio
async def test_agent_mode_send_message():
    am = make_manager(uid="agent_xyz")
    am.knowledge["CURRENT_TURN_CONTEXT"] = "ctx"
    await am.send_message(data={"response": "hello"})
    resp = am.get_response()
    assert resp is not None


@pytest.mark.asyncio
async def test_execute_behaviour_and_check_access():
    am = make_manager()
    am.knowledge["CURRENT_TURN_CONTEXT"] = "ctx"
    assert am.check_remote_callback_access("ctx") is True
    assert am.check_remote_callback_access("other") is False
    await am.execute_behaviour("main", {"EXTRA": 1})
    assert am.knowledge["EXTRA"] == 1


@pytest.mark.asyncio
async def test_idle_time_and_fini():
    am = make_manager()
    assert am.idleTime() > 0
    am.fini()
    assert am.running_actions == {}
    am.on_shutdown()


@pytest.mark.asyncio
async def test_process_remote_callback_payload():
    am = make_manager()

    class Listener:
        async def on_remote_callback_message_update(self, data):
            return True

    am.callbackmessage_manager.listeners = [(Listener(), ["method_x"])]
    await am.process_remote_callback_payload("method_x", {})
    # non-matching method is simply ignored
    await am.process_remote_callback_payload("other_method", {})


@pytest.mark.asyncio
async def test_engage_disengage_complete():
    am = make_manager()
    await am.engage_complete()
    assert am.in_user_interaction is True
    await am.disengage_complete()
    assert am.in_user_interaction is False
    await am.user_data_complete()
    assert am.in_user_interaction is False


@pytest.mark.asyncio
async def test_is_busy_after_suspension():
    am = make_manager()
    am.running_actions["comment"] = {"name": "comment", "_custom_obj": None}
    # non-suspendable custom -> warns and stays busy
    am.running_actions["comment"]["_custom_obj"] = type("C", (), {})()
    am.running_actions["comment"]["_custom_obj"].is_suspendable = lambda: False
    assert am.is_busy_after_suspension() is True
    # all suspendable -> suspends and not busy
    obj = type("C", (), {})()
    obj.is_suspendable = lambda: True
    obj.goto_suspension = lambda d=None: None
    am.running_actions["comment"]["_custom_obj"] = obj
    assert am.is_busy_after_suspension() is False
    assert am.running_actions == {}
    assert am.suspended_actions != {}


@pytest.mark.asyncio
async def test_play_disruptive_action():
    am = make_manager()
    am.running_actions["comment"] = {"name": "comment"}
    am.actions_lined_up = True
    await am.play_disruptive_action("dis", [["comment", "x"]])
    assert am.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_when_busy():
    am = make_manager()
    am.actions_lined_up = True
    assert await am.play_action("x", [["comment", "hi"]]) is False


@pytest.mark.asyncio
async def test_send_message_stream():
    from lurawi.custom_behaviour import DataStreamHandler

    am = make_manager()
    am.knowledge["CURRENT_TURN_CONTEXT"] = "ctx"
    am.knowledge["CURRENT_SESSION_ID"] = "s"

    async def gen():
        yield type(
            "Chunk",
            (),
            {"choices": [type("C", (), {"delta": type("D", (), {"content": "hi"})()})()]},
        )()

    handler = DataStreamHandler(gen(), None)
    await am.send_message(data=handler)
    resp = am.get_response()
    assert resp is not None


@pytest.mark.asyncio
async def test_custom_module_reload(monkeypatch):
    monkeypatch.setattr("lurawi.utils.in_dev", True)
    am = make_manager()
    await run_play(am, [["custom", {"name": "current_datetime", "args": {"output": "NOW"}}]])
    assert "NOW" in am.knowledge


@pytest.mark.asyncio
async def test_custom_load_from_workspace(tmp_path, monkeypatch):
    module = tmp_path / "custom"
    module.mkdir()
    (module / "tiny_custom.py").write_text(
        "from lurawi.custom_behaviour import CustomBehaviour\n"
        "class tiny_custom(CustomBehaviour):\n"
        "    async def run(self):\n"
        "        self.kb['TINY'] = 'ok'\n"
        "        await self.succeeded()\n"
    )
    am = make_manager()
    am.knowledge["LURAWI_WORKSPACE"] = str(tmp_path)
    await run_play(am, [["custom", {"name": "tiny_custom", "args": {}}]])
    assert am.knowledge["TINY"] == "ok"
    assert "lurawi.custom.tiny_custom" in __import__("sys").modules


@pytest.mark.asyncio
async def test_on_update_user_data():
    am = make_manager()
    am.userdata_action = ["comment", "ok"]
    await am.on_update_user_data({"message": "hi"})
    # the user_data_complete callback resets the flag after the action
    assert am.in_user_interaction is False
    # missing data -> early return
    await am.on_update_user_data(None)
    await am.on_update_user_data("notdict")


@pytest.mark.asyncio
async def test_play_behaviour_pending_disruption():
    am = make_manager(actions=[[["comment", "a"]], [["comment", "b"]]])
    am.pending_actions = [["x", ["comment", "y"], None, None, True]]
    am.knowledge["NO_DISRUPTION"] = 1
    await run_play(am, [["play_behaviour", "main"]])
    assert am.knowledge["NO_DISRUPTION"] == 1
    # without NO_DISRUPTION -> purges pending and queues disrupt action
    am2 = make_manager(actions=[[["comment", "a"]], [["comment", "b"]]])
    am2.pending_actions = [["x", ["comment", "y"], None, None, True]]
    am2.knowledge["NO_DISRUPTION"] = 0
    await run_play(am2, [["play_behaviour", "main"]])
    assert am2.pending_actions == []


@pytest.mark.asyncio
async def test_play_next_activity_busy_and_end():
    am = make_manager(actions=[[["comment", "a"]]])
    am.actions_lined_up = True
    await am.play_next_activity()  # busy -> early return
    am.actions_lined_up = False
    am.activity_index = 0
    ended = []

    async def cb():
        ended.append("E")

    am.activity_complete_cb = cb
    await am.play_next_activity()  # at end -> calls activity_complete_cb
    assert ended == ["E"]


@pytest.mark.asyncio
async def test_play_action_custom_missing_workspace_and_module(monkeypatch):
    # module not in sys.modules and no workspace -> tries import and fails gracefully
    am = make_manager()
    await run_play(am, [["custom", {"name": "definitely_missing_module_xyz", "args": {}}]])
    assert am.running_actions == {}


@pytest.mark.asyncio
async def test_play_action_custom_module_bad_class():
    am = make_manager()
    await run_play(am, [["custom", {"name": "no_such_module", "args": {}}]])
    assert am.running_actions == {}
