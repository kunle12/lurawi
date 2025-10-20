# Lurawi Agent Integration Guide

The `LurawiAgent` provides a Python module interface for embedding Lurawi agent workflows within larger applications. This integration approach enables developers to leverage Lurawi's powerful workflow capabilities as a component in custom solutions, MCP servers, or A2A protocol-based agents.

## Overview

The Lurawi Agent (`LurawiAgent`) module allows you to:

- Embed agent workflows directly in Python applications
- Integrate with existing AI/ML pipelines and systems
- Create custom MCP servers using Lurawi workflows
- Build A2A protocol agents with Lurawi processing capabilities
- Deploy agent functionality as part of larger microservice architectures

## Prerequisites

Before using the Lurawi Agent, ensure you have:

1. A working Python environment (Python 3.12+ recommended)
2. An existing Lurawi workflow developed and tested
3. Workflow files saved in the appropriate directory structure

## Directory Structure Setup

Organise your Lurawi project files as follows:

```
workspace/
├── behaviour.json          # Main workflow behavior configuration
├── knowledge.json          # Knowledge base configuration
└── custom/                 # Custom function scripts
    ├── custom_function_1.py
    ├── custom_function_2.py
    └── ...
```

**Key Components:**

- **Behaviour Files**: JSON-based workflow definitions, e.g. `llm_example.json`.
- **Knowledge Files**: a corresponding knowledge base configuration in `llm_example_knowledge.json`
- **Custom Directory**: Contains Python scripts with custom functions not part of the official Lurawi function library

## Installation

Install the LurawiAgent package in your Python environment:

```bash
pip install lurawi-agent
```

For development or specific version requirements:

```bash
pip install lurawi-agent==<version>
```

## Basic Usage

### Import and Initialize

```python
from lurawi.lurawi_agent import LurawiAgent

# Initialize the agent with your workflow
agent = LurawiAgent(
    name="my_agent",
    behaviour="llm_example",
    workspace="./workspace"  # Path to your workspace directory
)
```

**Parameters:**

- `name` (str): Unique identifier for the agent instance
- `behaviour` (str): Name of the behaviour file (without .json extension)
- `workspace` (str): Path to the directory containing workflow files

### Execute Agent Workflow

```python
# Basic execution with a message
result = agent.run_agent(message="Hello, how can you help me?")
print(result)

# Execution with additional parameters
result = agent.run_agent(
    message="Analyze this data",
    user_id="user123",
    session_data={"context": "previous_conversation"}
)
print(result)
```

**Note**: any parameter in the `run_agent` call must be resolved in the workflow using `query_knowledgebase` custom to be useful.

## Advanced Integration Patterns

### MCP Server Integration

```python
from lurawi.lurawi_agent import LurawiAgent
from modelcontextprotocol.server import Server
from modelcontextprotocol.models import Tool

# Initialize Lurawi Agent
lurawi_agent = LurawiAgent(
    name="mcp_agent",
    behaviour="llm_example",
    workspace="./workspace"
)

# Create MCP server
server = Server(
    name="lurawi-integration",
    tools=[
        Tool(
            name="lurawi_process",
            description="Process input through Lurawi agent workflow",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "context": {"type": "object"}
                },
                "required": ["message"]
            }
        )
    ]
)

@server.tool_call
async def lurawi_process(message: str, context: dict = None):
    result = lurawi_agent.run_agent(
        message=message,
        context=context
    )
    return {"result": result}
```

### A2A Protocol Agent

```python
from lurawi.lurawi_agent import LurawiAgent
from a2a.agent import Agent
from a2a.models import Message

class LurawiA2AAgent(Agent):
    def __init__(self, name: str, behaviour: str, workspace: str):
        super().__init__(name=name)
        self.lurawi_agent = LurawiAgent(
            name=f"{name}_lurawi",
            behaviour=behaviour,
            workspace=workspace
        )

    async def handle_message(self, message: Message) -> Message:
        # Extract relevant information from A2A message
        content = message.content
        context = message.context

        # Process through Lurawi agent
        result = self.lurawi_agent.run_agent(
            message=content,
            context=context
        )

        return Message(
            sender=self.name,
            content=result,
            context=context
        )
```

## Error Handling and Logging

```python
import logging
from lurawi.lurawi_agent import LurawiAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    agent = LurawiAgent(
        name="production_agent",
        behaviour="production_workflow",
        workspace="./workspace"
    )

    result = agent.run_agent(message="Process this request")
    logger.info(f"Agent execution completed: {result}")

except Exception as e:
    logger.error(f"Agent execution failed: {str(e)}")
    # Handle error appropriately
```

## Examples and Resources

- [Summary Agent Example](https://github.com/kunle12/lurawi-code-examples/tree/main/summary-agent)
- [MCP Server Documentation](https://modelcontextprotocol.io/docs/develop/build-server)
- [A2A Protocol Documentation](https://a2a-protocol.org/latest/)
