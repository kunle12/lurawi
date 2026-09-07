"""Import all importable lurawi modules so coverage measures them.

Modules requiring unavailable third-party packages (autogen, azure.servicebus)
are skipped; they are excluded from the coverage scope in the pytest config.
"""

import glob
import importlib
import logging

logging.getLogger("lurawi").setLevel(logging.ERROR)

_IMPORTABLE = [
    "lurawi.utils",
    "lurawi.arithmetic",
    "lurawi.calculate",
    "lurawi.compare",
    "lurawi.custom_behaviour",
    "lurawi.timer_manager",
    "lurawi.usermsg_manager",
    "lurawi.callbackmsg_manager",
    "lurawi.activity_manager",
    "lurawi.workflow_engine",
    "lurawi.webhook_handler",
    "lurawi.workflow_service",
    "lurawi.remote_service",
    "lurawi.services.discord_messenger",
    "lurawi.handlers.system_operations",
    "lurawi.handlers.remote_service_notification",
    "lurawi.handlers.get_conversation_stream",
]

for _name in _IMPORTABLE:
    try:
        importlib.import_module(_name)
    except Exception as _e:  # pragma: no cover
        pass

for _f in sorted(glob.glob("lurawi/custom/*.py")):
    if _f.endswith("__init__.py"):
        continue
    _m = _f[:-3].replace("/", ".").replace(".py", "")
    try:
        importlib.import_module(_m)
    except Exception as _e:  # pragma: no cover
        pass
