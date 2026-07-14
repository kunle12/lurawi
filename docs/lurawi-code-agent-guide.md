# Lurawi Code Agent Guide

## Overview

Lurawi is a workflow orchestration engine using a **metaprogramming language** expressed as JSON. Programs define **Behaviours** containing **Actions** containing **ActionLets** (action primitives + arguments). The engine executes these JSON programs, with custom Python scripts handling specialized logic.

---

## 1. Project File Structure

```
lurawi/
├── lurawi/                        # Core Python package
│   ├── __init__.py                # Empty
│   ├── workflow_engine.py         # WorkflowEngine - loads behaviours, manages users, timers, remote services
│   ├── activity_manager.py        # ActivityManager - executes behaviours/actions, manages KB, callbacks
│   ├── custom_behaviour.py        # CustomBehaviour base class + DataStreamHandler
│   ├── calculate.py               # calculate action primitive (CustomBehaviour subclass)
│   ├── compare.py                 # compare action primitive (CustomBehaviour subclass)
│   ├── lurawi_agent.py            # LurawiAgent - embeddable agent (AutoGen, AWS integrations)
│   ├── utils.py                   # Logger, encryption, HTTP helpers, tokenizer, type checking
│   ├── callbackmsg_manager.py     # RemoteCallbackMessageUpdateManager
│   ├── usermsg_manager.py         # UserMessageUpdateManager
│   ├── timer_manager.py           # TimerClient, TimerManager
│   ├── webhook_handler.py         # Webhook handling
│   ├── workflow_service.py        # Workflow service endpoints
│   ├── remote_service.py          # RemoteService base class
│   ├── custom/                    # Custom function plugins (21 prebuilt)
│   │   ├── invoke_llm.py          # Call OpenAI-compatible LLM
│   │   ├── build_gpt_prompt.py    # Build GPT prompt with system/history/docs
│   │   ├── query_knowledgebase.py # Query KB with phrase match or key lookup
│   │   ├── populate_prompt.py     # Replace placeholders in template
│   │   ├── text_input.py          # Prompt user for input, await response
│   │   ├── get_keyvalue.py        # Get dict value by key from KB store
│   │   ├── get_indexvalue.py      # Get list value by index
│   │   ├── has_keyvalue.py        # Check if key exists in dict
│   │   ├── validate_with_regex.py # Regex input validation
│   │   ├── random_picker.py       # Random selection from list
│   │   ├── current_datetime.py    # Get formatted datetime
│   │   ├── web_search.py          # Google Custom Search
│   │   ├── file_loader.py         # Load file to KB
│   │   ├── user_file_upload.py    # Handle user file upload
│   │   ├── send_data_to_url.py    # HTTP POST/GET to external URL
│   │   ├── send_data_to_service_bus.py # Azure Service Bus
│   │   ├── discord_message.py     # Send Discord messages
│   │   ├── cache_conversation_history.py # Conversation caching
│   │   ├── chromadb_search.py     # Vector search in ChromaDB
│   │   ├── get_data_from_url.py   # Fetch data from URL
│   │   ├── behaviour_router.py    # Conditional behaviour routing
│   │   └── README.md
│   ├── handlers/                  # Handler modules
│   │   ├── system_operations.py
│   │   └── get_conversation_stream.py
│   └── services/                  # Remote service plugins
│       ├── __init__.py
│       └── discord_messenger.py
├── bin/
│   ├── lurawi                     # CLI entry point
│   ├── run_visual_editor          # Start visual editor
│   └── version.py                 # Version info
├── app.py                         # FastAPI application entry point
├── pyproject.toml                 # Python packaging
├── requirements.txt               # Dependencies
├── Dockerfile / Dockerfile.new    # Docker deployment
├── docs/                          # Documentation
├── visualeditor/                  # Blockly-based visual editor
├── simpleui/                      # Next.js test console UI
├── tools/                         # Utility scripts
└── lurawi_example.json/xml        # Example workflow
```

---

## 2. Lurawi Meta-Language Grammar

### Program Structure (Top-Level)

```json
{
  "default": "__init__",
  "behaviours": [...]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `default` | string | Name of the default behaviour (acts like `main()` in C) |
| `behaviours` | array | List of behaviour definitions |

### Behaviour

```json
{
  "name": "__init__",
  "actions": [...]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique behaviour identifier, used as target for `play_behaviour` |
| `actions` | array | List of Actions (each Action is an array of ActionLets) |

### Action

An Action is a list of ActionLets that execute **in sequence**. Since all ActionLets are non-blocking (except `delay`), they appear simultaneous. After an Action completes, it does NOT automatically proceed — you must include `["play_behaviour", "next"]` to advance to the next Action.

```json
[
  [ "text", "hello" ],
  [ "play_behaviour", "next" ]
]
```

### ActionLet

A 2-element array: `["primitive_keyword", argument]`. Element 0 is the keyword (string), element 1 is the argument (string/int/float/bool/list/dict).

---

## 3. Full Action Primitive Reference

### `text` — Send text message to client
```json
["text", "hello world"]
["text", ["Hello {}, welcome {}", ["USER_NAME", "PROJECT_NAME"]]]
```
- Simple string → sent directly as response
- Template format `["template", ["key1", "key2"]]` → `{}` replaced by KB values. Unknown keys use key name with underscores→spaces.
- If string arg matches a KB key, KB value is sent instead

### `delay` — Pause execution
```json
["delay", 2]
```
- Must be int/float > 0 (seconds). Uses `asyncio.sleep()`.

### `knowledge` — Update knowledge base
```json
["knowledge", { "VAR_NAME": "value", "CNT": 1 }]
["knowledge", { "MSG": ["Hello {}", ["USER_NAME"]] }]
```
- Dict keys become KB variable names (UPPERCASE convention)
- If value is a string that matches a KB key → copies that KB value
- If value is `["template", ["keys"]]` → resolves template
- Otherwise → stores value directly

### `play_behaviour` — Jump to another behaviour/action (goto)
```json
["play_behaviour", "next"]              # Next action in current behaviour
["play_behaviour", "3"]                 # Action index 3 (1-based) in current behaviour
["play_behaviour", "engage:0"]          # Action 0 in behaviour "engage"
["play_behaviour", "engage"]            # Start of behaviour "engage"
["play_behaviour", ["name", "beh:N"]]   # Chained form
```
- `"next"` → next action in current behaviour
- `"N"` → action at index N-1 (1-based) in current behaviour
- `"behaviour:N"` → action at index N in named behaviour
- `"BEHAVIOUR_NAME"` → first action of named behaviour
- `"BEHAVIOUR_NAME:"` → first action of named behaviour (trailing colon)
- Before jumping, closes all suspended custom actions

### `select_behaviour` — Select behaviour without jumping
Same routing rules as `play_behaviour`, but only sets the active behaviour without executing immediately.

### `workflow_interaction` — Set lifecycle hooks
```json
["workflow_interaction", {
  "engagement": ["play_behaviour", "input:0"],
  "disengagement": ["play_behaviour", "cleanup:0"],
  "userdata": ["play_behaviour", "process_data:0"]
}]
```
- `engagement` — runs when user starts a conversation
- `disengagement` — runs when conversation ends
- `userdata` — runs when user provides new data during conversation

### `compare` — Conditional branching
```json
["compare", {
  "operand1": "CNT",
  "operand2": "COUNTNUM",
  "comparison_operator": "<=",
  "true_action": ["play_behaviour", "next"],
  "false_action": ["play_behaviour", "6"]
}]
```
- Operators: `<`, `<=`, `=`, `!=`, `>`, `>=`
- Operands support arithmetic: `"CNT + 1"`, `"time"`, `"KB_KEY * 2 + time"`
- Arithmetic operators: `+`, `-`, `*`, `/` (floor div), `!` (true div), `%`
- `time` resolves to `int(time.time())`
- If operand is a string matching a KB key → KB value used
- If operand is numeric → parsed as float/int

### `calculate` — Arithmetic computation
```json
["calculate", ["KB_KEY", "2 * CNT + time"]]
```
- Element 0: KB key to store result
- Element 1: arithmetic expression (same syntax as compare operands)

### `random` — Random selection
```json
["random", ["KB_KEYNAME", [1, 2, 3]]]
```
- Element 0: KB key to store selected item
- Element 1: list of choices → `random.choice()` picks one

### `http_response` — Send raw HTTP response
```json
["http_response", {
  "status_code": 200,
  "response": "Hello world"
}]
```
- Sends arbitrary HTTP status code and payload body
- Supports template resolution in values (nested `["template", ["keys"]]`)

### `custom` — Execute custom Python function
```json
["custom", {
  "name": "invoke_llm",
  "args": { ... },
  "success_action": ["text", "LLMTEXT"],
  "failed_action": ["text", "System error"]
}]
```
- `name` → module name, loads from `lurawi/custom/{name}.py`
- `args` → dict passed to custom class as `self.details`
- `success_action` / `failed_action` → chained actions after completion

### `comment` — No-op
```json
["comment", "this does nothing"]
```

### Action Chaining
An ActionLet can include 3rd+ elements that execute after the primitive completes:
```json
["custom", { "name": "invoke_llm", "args": {...} },
  ["text", "LLMTEXT"]
]
["custom", { "name": "query_knowledgebase", "args": {...} },
  ["custom", { "name": "build_gpt_prompt", "args": {...} }],
  ["custom", { "name": "invoke_llm", "args": {...} }]
]
```

---

## 4. Knowledge Base (KB) System

The KB is a shared Python dict accessible throughout execution.

### Conventions
- **UPPERCASE keys** recommended (e.g., `USER_MESSAGE`, `COUNTNUM`)
- String arguments matching KB keys → KB value substituted
- KB is initialized from `{behaviour}_knowledge.json`

### Template String Resolution
```json
["text", ["Hello {}, you are visitor {}", ["USER_NAME", "VISITOR_COUNT"]]]
```
- Template string with `{}` placeholders
- Keys list resolved from KB; unknown keys use key name (underscores→spaces)

### Automatic KB Variables
| Variable | Source |
|----------|--------|
| `USER_ID` | From payload `uid` |
| `USER_NAME` | From payload `name` |
| `USER_DATA` | From payload `data` dict |
| `CURRENT_TURN_CONTEXT` | Activity context UUID |
| `CURRENT_SESSION_ID` | Session ID |
| `ACCESS_TIME` | Timestamp of last interaction |
| `MODULES` | System modules (ActivityManager, UserMessageManager, etc.) |
| `MESG_FUNC` | `send_message` function for custom functions |
| `LURAWI_SYSTEM_SERVICES` | Remote services dict |
| `__MUTEX__` | Threading mutex |

### Knowledge File
```json
// lurawi_example_knowledge.json
{ "PROJECT_NAME": "my_project", "API_KEY": "sk-..." }
```

---

## 5. CustomBehaviour Base Class — Complete API Reference

**File**: `lurawi/custom_behaviour.py`

### Inheritance
```python
class CustomBehaviour(UserMessageListener, RemoteCallbackMessageListener):
```

### Constructor
```python
def __init__(self, kb: dict = {}, details: dict = {}):
    super().__init__(kb, details)
    # self.kb — knowledge base dict (read/write)
    # self.details — args dict from ActionLet
    # self.on_success — set by engine to actionHandler callback
    # self.on_failure — set by engine to actionFailHandler callback
```

### Method Signatures

#### `parse_simple_input(key, check_for_type, env_name="")`
```python
def parse_simple_input(self, key: str, check_for_type: str, env_name: str = "") -> Any | None
```
- Retrieves value from `self.details[key]`
- If value is a string matching a KB key → resolves KB value
- If value is None and `env_name` exists in KB → uses KB[env_name]
- If `check_for_type == "str"` and value is `["template", ["keys"]]` → resolves template
- Returns value if `check_type(value, check_for_type)` passes, else None
- Valid type strings: `"int"`, `"float"`, `"str"`, `"list"`, `"dict"`, `"bool"`, etc.

#### `async succeeded(action=None)`
```python
async def succeeded(self, action=None) -> None:
```
- Calls `self.on_success(class_name, action)` which triggers `actionHandler`
- If action is None → uses `self.details.get("success_action")`
- action can be: `["play_behaviour", "next"]`, `["text", "msg"]`, etc.

#### `async failed(action=None)`
```python
async def failed(self, action=None) -> None:
```
- Calls `self.on_failure(class_name, action)` which triggers `actionFailHandler`
- If action is None → uses `self.details.get("failed_action")`

#### `async message(status, data)`
```python
async def message(self, status=200, data=None) -> None:
```
- Sends response to client via `self.kb["MESG_FUNC"]`
- `data` dict sent as JSON response

#### User Message Registration
```python
def register_for_user_message_updates(self, interests: List[str] = []) -> None
def cancel_user_message_updates(self) -> None
```
- Register to receive user input callbacks via `on_user_message_update(context)`
- Call `cancel_*` in `fini()` or when done

#### Remote Callback Registration
```python
def register_for_callback_message_updates(self, interests: List[str] = []) -> None
def cancel_callback_message_updates(self) -> None
```
- Register for remote service callback updates

#### Suspension Control
```python
def is_suspendable(self) -> bool
def can_suspend(self, isyes: bool) -> None
def is_suspended(self) -> bool
def goto_suspension(self, data=None) -> bool
def restore_from_suspension(self, data=None) -> bool
def on_suspension(self, data) -> bool   # override for custom suspension logic
def on_restoration(self, data) -> bool  # override for custom restoration logic
```

#### Utility
```python
def log_result(self, data) -> None      # Store (data, timestamp) in USER_INPUTS_CACHE
def fini(self) -> None                   # Cleanup: cancels message/callback registrations
```

### Callbacks You Can Override
```python
async def on_user_message_update(self, context) -> None     # Called when user sends message
async def on_remote_call_message_update(self, context) -> None  # Called on remote callback
```

### The `run()` Method (Required)
```python
async def run(self):
    """Main logic. Must call await self.succeeded() or await self.failed()."""
    # 1. Parse and validate inputs
    param = self.parse_simple_input(key="param", check_for_type="str")
    if param is None:
        await self.failed()
        return

    # 2. Process data, store results in self.kb
    self.kb["OUTPUT_KEY"] = result

    # 3. Signal success (optionally with chained action)
    if "success_action" in self.details:
        await self.succeeded(actions=self.details["success_action"])
    else:
        await self.succeeded()
```

### DataStreamHandler (for Streaming Responses)
```python
class DataStreamHandler:
    def __init__(self, response, callback_custom: Optional[CustomBehaviour] = None)
    async def stream_generator(self) -> AsyncIterable[str]
```
- Used by `invoke_llm` for streaming LLM responses via SSE
- Stores accumulated content in `callback_custom.kb["LLM_RESPONSE"]` or specified key

---

## 6. Complete Custom Function Patterns

### Pattern A: Simple Computation (current_datetime.py)
```python
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger

class current_datetime(CustomBehaviour):
    """!@brief Get current datetime string.
    Example:
    ["custom", { "name": "current_datetime",
                 "args": {
                     "format": "%Y-%m-%d %H:%M:%S",
                     "output": "MY_CUSTOM_DATETIME_KEY"
                 }
               }
    ]
    """
    async def run(self):
        current_time = datetime.now()
        if "format" in self.details and isinstance(self.details["format"], str):
            try:
                output = current_time.strftime(self.details["format"])
            except Exception:
                output = current_time.strftime("%d/%m/%Y %H:%M:%S")
        else:
            output = current_time.strftime("%d/%m/%Y %H:%M:%S")

        if "output" in self.details and isinstance(self.details["output"], str):
            self.kb[self.details["output"]] = output
        else:
            self.kb["CURRENT_DATETIME"] = output
        await self.succeeded()
```

### Pattern B: Awaiting User Input (text_input.py)
```python
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger

class text_input(CustomBehaviour):
    """!@brief Prompt user for text input.
    Example:
    ["custom", { "name": "text_input",
                 "args": {
                     "prompt": ["Hello {}, what is your favorite color?", ["GUESTNAME"]],
                     "output": "FAVORITE_COLOR"
                 }
               }
    ]
    """
    def __init__(self, kb, details):
        super().__init__(kb, details)
        self.data_key = None

    async def run(self):
        self.data_key = self.details.get("output")
        if not self.data_key or not isinstance(self.data_key, str):
            logger.error("text_input: missing output")
            await self.failed()
            return

        # Build prompt (template resolution)
        prompt = ""
        if "prompt" in self.details:
            prompt_arg = self.details["prompt"]
            if isinstance(prompt_arg, list) and len(prompt_arg) == 2:
                to_say, keys = prompt_arg
                if isinstance(keys, list):
                    for key in keys:
                        if key in self.kb:
                            to_say = to_say.replace("{}", str(self.kb[key]), 1)
                        else:
                            to_say = to_say.replace("{}", str(key).replace("_", " "), 1)
                    prompt = to_say
            elif isinstance(prompt_arg, str):
                prompt = prompt_arg

        self.register_for_user_message_updates()
        if prompt:
            await self.message(data={"response": prompt})

    async def on_user_message_update(self, context):
        result = ""
        if isinstance(context, dict) and "message" in context:
            result = context["message"].strip()
        self.kb[self.data_key] = result
        await self.succeeded()
```

### Pattern C: External API Call (invoke_llm.py)
```python
from openai import AsyncOpenAI
from lurawi.custom_behaviour import CustomBehaviour, DataStreamHandler
from lurawi.utils import logger

class invoke_llm(CustomBehaviour):
    """!@brief Invoke OpenAI-compatible LLM.
    Example:
    ["custom", { "name": "invoke_llm",
                 "args": {
                     "base_url": "http://localhost:8080",
                     "api_key": "OPENAI_API_KEY",
                     "model": "qwen3",
                     "prompt": [{"role": "user", "content": "Tell a story about {}"}],
                     "temperature": 0.6,
                     "max_tokens": 512,
                     "stream": false,
                     "response": "LLMTEXT",
                     "success_action": ["text", "LLMTEXT"],
                     "failed_action": ["text", "System error"]
                 }
               }
    ]
    """
    async def run(self):
        base_url = self.parse_simple_input(key="base_url", check_for_type="str")
        api_key = self.parse_simple_input(key="api_key", check_for_type="str")
        model = self.parse_simple_input(key="model", check_for_type="str")

        if not all([base_url, api_key, model]):
            await self.failed()
            return

        # Resolve prompt (string, template, or chat format)
        prompt = self.details.get("prompt")
        if isinstance(prompt, str) and prompt in self.kb:
            prompt = self.kb[prompt]

        # ... (template/list resolution logic)

        if isinstance(prompt, str):
            prompt = [{"role": "user", "content": prompt}]

        temperature = self.parse_simple_input(key="temperature", check_for_type="float") or 0.6
        stream = self.parse_simple_input(key="stream", check_for_type="bool") or False
        max_tokens = self.parse_simple_input(key="max_tokens", check_for_type="int") or 512

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            response = await client.chat.completions.create(
                model=model, messages=prompt, max_tokens=max_tokens,
                temperature=temperature, stream=stream
            )
        except Exception as err:
            self.kb["ERROR_MESSAGE"] = str(err)
            await self.failed()
            return

        if stream:
            handler = DataStreamHandler(response, callback_custom=self)
            # ... streaming response handling
        else:
            content = response.choices[0].message.content
            if "response" in self.details and isinstance(self.details["response"], str):
                result_var = self.details["response"]
                if result_var in self.kb and isinstance(self.kb[result_var], list):
                    self.kb[result_var].append(content)
                else:
                    self.kb[result_var] = content
            else:
                self.kb["LLM_RESPONSE"] = content
            await self.succeeded()
```

### Pattern D: KB Query with Phrase Matching (query_knowledgebase.py)
```python
class query_knowledgebase(CustomBehaviour):
    """!@brief Query KB with phrase matching or key lookup.
    Example:
    ["custom", { "name": "query_knowledgebase",
                 "args": {
                     "knowledge_key": "known_people",
                     "query_arg": "USER_INPUT_NAME",
                     "phrase_match": True,
                     "query_output": "MATCHED_PERSON_DATA",
                     "success_action": ["play_behaviour", "2"],
                     "failed_action": ["play_behaviour", "next"]
                 }
               }
    ]
    """
    async def run(self):
        knowledge_key = self.details.get("knowledge_key")
        if knowledge_key not in self.kb:
            await self.failed()
            return

        knowledge_variable = self.kb[knowledge_key]
        # ... phrase matching or key lookup logic

        if found:
            self.kb[self.details.get("query_output", "QUERY_OUTPUT")] = found
            await self.succeeded()
        else:
            self.kb["UNKNOWN_QUERY"] = input_arg
            await self.failed()
```

### Pattern E: Dict Key Lookup (get_keyvalue.py)
```python
class get_keyvalue(CustomBehaviour):
    """!@brief Get value from a dict by key.
    Example:
    ["custom", { "name": "get_keyvalue",
                 "args": {
                     "store": "QUERY_OUTPUT",
                     "key": "team",
                     "value": "KNOWN_TEAM",
                     "success_action": ["play_behaviour", "next"],
                     "failed_action": ["play_behaviour", "next"]
                 }
               }
    ]
    """
    async def run(self):
        query_key = self.details["key"]
        store_obj = self.kb  # default store is KB itself

        if "store" in self.details:
            skey = self.details["store"]
            if skey in self.kb:
                store_obj = self.kb[skey]
            else:
                await self.failed()
                return

        if query_key in self.kb:
            query_key = self.kb[query_key]

        if isinstance(store_obj, dict) and query_key in store_obj:
            found = store_obj[query_key]
            self.kb[self.details.get("value", "_VALUE_OUTPUT")] = found
            await self.succeeded()
        else:
            await self.failed()
```

### Pattern F: Prompt Template Population (populate_prompt.py)
```python
class populate_prompt(CustomBehaviour):
    """!@brief Fill prompt template with KB values.
    Example:
    ["custom", { "name": "populate_prompt",
                 "args": {
                     "prompt_text": "Hello {USER_NAME}, task: {TASK}.",
                     "replace": {
                         "{USER_NAME}": "USER_NAME_KB_KEY",
                         "{TASK}": "TASK_DESC_KB_KEY"
                     },
                     "output": "FINAL_PROMPT"
                 }
               }
    ]
    """
    async def run(self):
        prompt = self.parse_simple_input(key="prompt_text", check_for_type="str")
        replace = self.parse_simple_input(key="replace", check_for_type="dict")
        if not prompt or not replace:
            await self.failed()
            return

        # Resolve each replacement value from KB (with nested template support)
        for k, v in replace.items():
            if isinstance(v, str) and v in self.kb:
                value = self.kb[v]
                # handle nested template ["text", ["keys"]]
                replace[k] = value

        for k, v in replace.items():
            prompt = prompt.replace(k, str(v))

        self.kb[self.details.get("output", "PROMPT_TEXT")] = prompt
        await self.succeeded()
```

---

## 7. Critical Rules for Custom Functions

1. **Class name MUST match file name** — `class invoke_llm` in `invoke_llm.py`
2. **Must inherit from `CustomBehaviour`** — engine checks `issubclass(tclass, CustomBehaviour)`
3. **Docstring MUST contain valid JSON example** — visual editor parses it to build block UI. Each `args` key becomes a named input port on the block.
4. **Always validate inputs** — args can be direct values OR KB key references. Use `parse_simple_input()`.
5. **Always call `await self.succeeded()` or `await self.failed()`** — engine tracks running actions and cleans up.
6. **`run()` must be async** — engine calls `await custom_obj.run()`
7. **Store results in `self.kb`** — shared knowledge base dict
8. **Always call `super().__init__(kb, details)`** in `__init__`
9. **Implement `fini()` for cleanup** — cancel message/callback registrations

---

## 8. The Docstring-to-Block Pipeline

The visual editor (`visualeditor/lurawi_workspace.js`) scans each custom file, parses its docstring for the JSON example, and dynamically builds a Blockly block. The mapping is:

- **Each top-level key in `args` → named input port on the block**
- **`success_action` / `failed_action` → output statement connectors** (chain to next block)
- **`output` key → variable output port** (store result in variable)
- **`prompt`, `query`, etc. → text input ports**
- **`stream`, `phrase_match` → boolean toggle ports**
- **`temperature`, `max_tokens` → number input ports**

Changing the docstring changes the visual block. Keep docstring and implementation in sync.

---

## 9. Available Utility Functions (`lurawi/utils.py`)

```python
logger = logging.getLogger("lurawi")   # Use for all logging

def is_indev() -> bool                 # True if running in --dev mode

def calc_token_size(text: str) -> int  # Token count via tiktoken

def cut_string(s, n_tokens=2500)       # Truncate to max tokens

def check_type(value, type_info: str) -> bool  # Type check using PYTHON_TYPE_MAPPING

def is_valid_url(url_string) -> bool   # URL validation regex

# HTTP helpers
async def aget_data_from_url(headers, url) -> (status, data)
async def apost_payload_to_url(headers, url, payload) -> (status, data)
async def apost_data_to_url(headers, url, data) -> (status, data)
async def adownload_file_to_temp(url: str) -> str  # Download to temp file

# Storage helpers
def get_content_from_azure_storage(filepath, container, as_binary=False)
def save_content_to_azure_storage(filepath, content_file, container)
def get_content_from_aws_s3(filepath, container, as_binary=False)

# Crypto
def encrypt_ifavailable(data) -> str
def decrypt_ifavailable(data) -> str

def write_http_response(status, body_dict, headers={}) -> JSONResponse
def decode_json_field(data: Dict) -> Dict  # Decode *_json suffixed fields

PYTHON_TYPE_MAPPING = {
    "int": int, "float": float, "str": str, "list": list, "dict": dict,
    "bool": bool, "bytes": bytes, "set": set, "tuple": tuple, ...
}
```

---

## 10. Execution Model & Engine Architecture

### WorkflowEngine (`lurawi/workflow_engine.py`)
- Loads behaviours from JSON file (local, Azure Blob, or AWS S3)
- Loads knowledge from `{behaviour}_knowledge.json`
- Manages conversation members (ActivityManager instances per user)
- Handles timers for auto-purging idle users
- Manages remote services (Discord, etc.)

### ActivityManager (`lurawi/activity_manager.py`)
- Per-user manager that executes behaviours
- Loads behaviours → finds `default` → sets active behaviour
- `play_next_activity()` increments activity index and plays the action
- `play_action()` iterates ActionLets, calling `play_action_let()` for each
- `play_action_let()` dispatches by cmd: text, knowledge, custom, compare, calculate, etc.
- Tracks `running_actions` dict and `chained_actions` for continuation
- Custom function loading:
  1. Check `sys.modules["lurawi.custom.{name}"]`
  2. In dev mode → `importlib.reload()`
  3. Workspace path `{LURAWI_WORKSPACE}/custom/{name}.py`
  4. Fallback `importlib.import_module("lurawi.custom.{name}")`
  5. `getattr(module, name)` → class must match file name
  6. `issubclass(tclass, CustomBehaviour)` → engine runs it

### Workflow Lifecycle
```
1. POST /{project}/message with payload {uid, name, data: {message, ...}}
2. WorkflowEngine.on_event() → ActivityManager.start_user_workflow()
3. Engagement action plays (if set via workflow_interaction)
4. Default behaviour (__init__) starts → Actions execute sequentially
5. Each ActionLet dispatches: text→response, custom→Python, compare→branch, etc.
6. play_behaviour "next" advances to next Action
7. At behaviour end → response sent as {status, activity_id, response}
```

### Control Flow Patterns
- **Sequential**: `["play_behaviour", "next"]` after each action
- **Looping**: `compare` with `true_action: ["play_behaviour", "N"]` to repeat
- **Branching**: `compare` with `true_action` / `false_action`
- **Sub-workflows**: `play_behaviour "behaviour:N"` to jump between behaviours
- **Chained actions**: Extra elements in ActionLet array execute on completion

---

## 11. Built-in Custom Functions — Detailed API

### invoke_llm
| Args Key | Type | Description | Default |
|----------|------|-------------|---------|
| `base_url` | str | OpenAI-compatible API endpoint | required |
| `api_key` | str | API key or KB key | required |
| `model` | str | Model name | required |
| `prompt` | str/list | Prompt text or chat-format list | required |
| `temperature` | float | Sampling temperature | 0.6 |
| `max_tokens` | int | Max output tokens | 512 |
| `stream` | bool | Enable streaming | false |
| `response` | str | KB key for output | LLM_RESPONSE |

### build_gpt_prompt
| Args Key | Type | Description |
|----------|------|-------------|
| `system_prompt` | str | System instructions |
| `user_prompt` | str | Template with `{query}`, `{docs}` |
| `query` | str | User query replacing `{query}` |
| `history` | list | Conversation history messages |
| `documents` | str | Documents replacing `{docs}` |
| `max_tokens` | int | Token limit (-1 = no limit) |
| `output` | str | KB key for result |

### query_knowledgebase
| Args Key | Type | Description |
|----------|------|-------------|
| `knowledge_key` | str | KB key to query (required) |
| `query_arg` | str/dict | Value or key for lookup |
| `query_key` | str | Key within query_arg dict |
| `phrase_match` | bool | Enable phrase matching |
| `query_output` | str | KB key for result |
| `phrase_match_key` | str | KB key for matched phrase name |

### text_input
| Args Key | Type | Description |
|----------|------|-------------|
| `prompt` | str/list | Prompt to show user |
| `output` | str | KB key for user response (required) |

### validate_with_regex
| Args Key | Type | Description |
|----------|------|-------------|
| `input_text` | str | Text to validate |
| `regex` | str | Regex pattern |

### random_picker
| Args Key | Type | Description |
|----------|------|-------------|
| `list` | list/str | List of choices |
| `output` | str | KB key for selection |

---

## 12. CLI Commands

```bash
lurawi run          # Start production service
lurawi dev          # Start development mode (visual editor + runtime)
lurawi custom list  # List available custom functions
lurawi custom new <name>  # Create new custom function template
lurawi create <project>   # Create new project from template
lurawi version      # Show version
```

Required env vars: `PROJECT_NAME`, `PROJECT_ACCESS_KEY`

---

## 13. Docker Deployment

```dockerfile
FROM kunle12/lurawi:latest
ENV PROJECT_NAME lurawi_example
COPY lurawi_example.json /opt/defaultsite
COPY lurawi_example_knowledge.json /opt/defaultsite
COPY custom /opt/defaultsite/lurawi/custom
ENTRYPOINT ["python", "app.py", "--skip-auth", "--no-ssl-verify"]
```

---

## 14. LurawiAgent Integration

```python
from lurawi.lurawi_agent import LurawiAgent

agent = LurawiAgent(
    name="my_agent",
    behaviour="lurawi_example",
    workspace="./workspace"
)

# Synchronous
result = agent.run_agent(message="Hello", user_id="user123")

# Async
result = await agent.arun_agent(message="Hello")
```

Workspace structure:
```
workspace/
├── behaviour.json          # Main workflow
├── knowledge.json          # Knowledge base
└── custom/
    ├── my_function.py
    └── ...
```

Also supports AutoGen (`LurawiAutoGenAgent`) and AWS (`LurawiAWSAgent`) integrations.

---

## 15. Complete Workflow Example: LLM Chat

```json
{
  "default": "__init__",
  "behaviours": [
    {
      "name": "__init__",
      "actions": [
        [
          ["knowledge", {"USER_MESSAGE": "", "PROMPT": "", "LLMTEXT": ""}],
          ["play_behaviour", "main"]
        ]
      ]
    },
    {
      "name": "main",
      "actions": [
        [
          ["workflow_interaction", {
            "engagement": ["play_behaviour", "input:0"]
          }]
        ]
      ]
    },
    {
      "name": "input",
      "actions": [
        [
          ["custom", {
            "name": "query_knowledgebase",
            "args": {
              "knowledge_key": "USER_DATA",
              "query_arg": "message",
              "query_output": "USER_MESSAGE",
              "success_action": [
                "custom", {
                  "name": "build_gpt_prompt",
                  "args": {
                    "system_prompt": "You are a helpful assistant.\n\n",
                    "user_prompt": "Answer: {query}",
                    "query": "USER_MESSAGE",
                    "output": "PROMPT"
                  }
                },
                "custom", {
                  "name": "invoke_llm",
                  "args": {
                    "base_url": "http://localhost:8080",
                    "api_key": "test",
                    "model": "qwen3",
                    "prompt": "PROMPT",
                    "temperature": 0.6,
                    "stream": true,
                    "response": "LLMTEXT",
                    "success_action": ["text", "LLMTEXT"],
                    "failed_action": ["text", "System error"]
                  }
                }
              ],
              "failed_action": ["text", "System error"]
            }
          }]
        ]
      ]
    }
  ]
}
```

---

## 16. Testing & Debugging

```bash
# Send test payload
curl -X POST http://localhost:8081/{project}/message \
  -H "Content-Type: application/json" \
  -d '{"uid": "test", "name": "Test", "data": {"message": "hello"}}'

# Expected response
{"status": "success", "activity_id": "...", "response": "..."}
```

Logging: set `LOGLEVEL=DEBUG` env var. All logs use `logging.getLogger("lurawi")`.

Error handling in custom functions:
```python
logger.error("my_func: missing required arg '%s'", arg_name)
await self.failed()
return
```
