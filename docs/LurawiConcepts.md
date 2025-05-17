# Lurawi Visual Programming Concepts

## Introduction

Lurawi is a workflow construction/orchestration engine that can programm  arbitrary agent workflows with little or no code. It relies a visual programming web interface similar to the popular educational programming tool [scratch](https://scratch.mit.edu/about). In fact, it is highly recommended that you shall have a good understanding of scratch before building a workflow based on Lurawi.

## Lurawi Visual Programming Editor

![Lurawi Visual Programming Editor](images/editor.png)
Fig. 1 Lurawi Agent Workflow Visual Programming Editor

### Workspace

There are two tabs, namely, **Blocks** and **Code** tab in the visual editor.

**Blocks** is the main working space where blocks can be dragged and dropped in the workarea to compose graphical agent workflows. On the left working pane, we have two agent specific groups **Behaviour** and **Action Primitives** that contain Lurawi platform specific blocks. Details of these blocks are explained in the following programming language section.

**Code** shows the realtime translation (in JSON code) of the block program constructed in the **Blocks** workspace. It is the JSON formatted code that will be ultimately executed on Lurawi agent workflow execution engine. **CAUTION**: You might make manual changes to the displayed JSON code. However, any many JSON code change will not be translated back to the visual Blockly program. It is not recommended practice as this breaks the sync with the block program and the JSON code. Always treat the Blockly program as your actual code. JSON code can be regenerated at anytime.

### File Types

There are two file types, graphical Blockly program in XML file format and Lurawi JSON code. Blockly program can be loaded and saved in the **Blocks** workspace, whereas the corresponding JSON code is saved in the **Code** workspace.

### Programming Workflow

You should build up block program in the **Blocks** workspace and verify generated JSON code in the **Code** workspace. If the block program contains syntactical errors, the corresponding JSON will not be generated successfully in the **Code** workspace. You can switch between the two tabs frequently to ensure your block program is valid. When you finish editing your block program, make sure a copy of the block program is saved in the **Blocks** workspace before switching to the **Code** workspace to save the final JSON code. Finally, you need to package the JSON file together with Lurawi runtime engine (there are multiple ways of deploying Lurawi, more detail later).

## Workflow Meta Programming Language

Lurawi platform uses a special meta programming language to develop complex workflows. The program file format is the standard JSON format that can be processed by any JSON reader. The Lurawi meta language introduces a few key concepts described in the following sections.

### Action Primitives

An **Action Primitive** represents a smallest and simplest action unit can be performed under Lurawi. It consists of a set of predefined keywords. **NOTE** Some **Action Primitives** do not have direct graphical block representations and are not used directly by user in block programming. You can find all usable Action Primitives blocks as shown in Fig. 2. in the visual editor.
<figure>
    <img src="images/action_primitives.png"
         alt="Action primitives" width="300px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 2. Action Primitives in the visual editor.</figcaption>
</figure>

|Name|Descriptions|
|----|------------|
|```text``` <img src="https://user-images.githubusercontent.com/6646691/100294205-31cfa580-2fda-11eb-8aca-c949faa1e64a.png" width="60" style="vertical-align:middle;"/>| Return a simple (formatted) text message to a client.|
|```delay``` <img src="https://user-images.githubusercontent.com/6646691/100294372-b7ebec00-2fda-11eb-9f42-7a8317cdf958.png" width="110" style="vertical-align:middle;"/>| Specify a time delay in seconds between action units. It should not be used under normal circumstances [1].|
|```knowledge```| Update agent internal knowledge database with key-value pairs as a dict.|
|```workflow_interaction```<img src="images/interaction_primitives.png" width="180" style="vertical-align:middle;"/>| Trigger action when a user start conversation with Agent|
|```play_behaviour```<img src="https://user-images.githubusercontent.com/6646691/100294603-642dd280-2fdb-11eb-8184-eb3d950432fa.png" width="140" style="vertical-align:middle;"/>| Execute a specified behaviour[1].|
|```select_behaviour```<img src="https://user-images.githubusercontent.com/6646691/100294677-9d664280-2fdb-11eb-8309-1fd1e99076b8.png" width="140" style="vertical-align:middle;"/>| Select a specified behaviour to be played next.|
|```custom``` <img src="https://user-images.githubusercontent.com/6646691/100294749-d0a8d180-2fdb-11eb-8682-0030148230ed.png" width="110" style="vertical-align:middle;"/>| Execute a custom defined plugin Python script module.
|```compare```| Compare two variables and simulate generic if flow control.|
|```calculate```| Simple generic calculation operation|
|```random```| Generate a pseudo random number|
|```comment```| A no-op comment section|

*Table 1.* A partial list of Action Primitives supported on Lurawi.

#### Custom Action Primitives (Pluginable Python Script Module)

It is impossible to encapsulated all possible agent related actions statically in a data file. Especially when those actions involves custom data processing, calling external services etc. Hence, we incorporate custom defined Python scripts as a key action primitive and process specialised actions. When a custom action primitive is invoked, the user defined Python script takes over the control of the system. When the script completes its designed task, it returns the control back to the workflow engine along with the results from its execution.

Lurawi provides a set of predefined custom action primitives that address some common use cases. For example, ```invoke_llm``` is a custom that calls OpenAI compatible LLM service. It saves the returned result from LLM in the knowledge base under the specified ```response``` key before passing control back to the workflow engine. Note that, all customs reside in ```custom``` subdirectory. Each custom script shall have a description and an example of its usage in its doc string. See current set of customs under the ```custom``` directory and the [instructions](LurawiGenAiCustoms.md) on how to create a custom action primitive.

The custom **Action Primitive** graphical block in the visual editor dynamically changes its shape when different custom is selected. Table 2 shows a selection of custom primitives prebuilt in Lurawi:

|Name|Description|
|----|-----------|
|build_gpt_prompt|Combine system prompt, user prompt and retrieved document fragments to form a RAG query prompt|
|invoke_llm|calling OpenAI compatible LLM service to generated text|

*Table 2* A list of prebuilt custom action primitives for Lurawi.

### ActionLet

An **Action Primitive** is not useful by itself. It must combine with an argument input to form an **ActionLet**. That is, an **ActionLet** is an instantiation of a **Action Primitive** in a similar fashion as an object is an instantiation of a class in Object Oriented programming language such as C++.

An **ActionLet** takes a form of two element list where the first element is the keyword of an **Action Primitive**, the second element is the argument/input in string, integer, float number, boolean, list or dict JSON data types.

```JSON
["text", "hello there"]
```
The corresponding visual representation in the visual editor:

<figure>
    <img src="images/actionlet.png"
         alt="Dispatch Workflow to runtime engine" width="200px"
         />
    <figcaption>Fig. 3 A say ActionLet.</figcaption>
</figure>

### Action

An **Action** is a list of **ActionLets**. **ActionLets** in an **Action** get played "simultaneously"[2]. An **Action** is useful when you want to start serveral action units at the same time, e.g. execution a sending text action along with incrementing a counter variable. A **Action** is not finished util every **ActionLet** inside of the **Action** is completed.
<figure>
    <img src="images/actionblock.png"
         alt="Action with two actionlets" width="320px"
         />
    <figcaption>Fig. 4 An Action that contains two ActionLets.</figcaption>
</figure>

**NOTE:** When an **Action** is completed, it does not automatically goes to the next **Action**. You need to append an additional ```["play_behaviour", "next"]``` **ActionLet** in the **Action** in order to move the next **Action**. In the visual editor, simply select *continue* option.

### Behaviour

A **Behaviour** sits at the top of the action family hierarchy. It is a dictionary with a name and a list of **Actions**. A valid workflow must have all **Actions** enclosed under **Behaviour** blocks. Multiple Behaviours can be defined in one behaviour file. One (and only one) default behaviour, with ```default``` checkbox ticked, must be specified in a behaviour file. The default behaviour is the first behaviour that is loaded and executed. It is equivalent to ```main``` function in C/C++.

<figure>
    <img src="images/behaviourblock1.png"
         alt="a behaviour with actions" width="320px"
         />
    <figcaption>Fig. 5 A valid behaviour block with actions.</figcaption>
</figure>

Furthermore, control flow blocks such as ```if```, ```while``` etc, must be enclosed directly under a Behaviour block, for example:

<figure>
    <img src="images/behaviourblock2.png"
         alt="If block under behaviour block" width="320px"
         />
    <figcaption>Fig. 6 A valid if block under a behaviour block.</figcaption>
</figure>

### Notes
[1] ```play_behaviour``` acts as a **goto** statement at the end of all **ActionLets** in the **Action** have been completed. It can be used to jump to any specific **Action** defined in a **Behaviour**.

[2] ActionLets in an Action are actually executed in sequence. Since all ActionLets are non-blocking (apart from ```delay``` primitive), their executions appear to be simultaneous.

### A Complete Behaviour JSON Code Example
```JSON
{
  "default": "__init__",
  "behaviours": [
    {
      "name": "__init__",
      "actions": [
        [
          [ "knowledge", { "COUNTNUM": "", "CNT": "" } ],
          [ "play_behaviour","test1" ]
        ]
      ]
    },
    {
      "name": "test1",
      "actions": [
        [
          [ "workflow_interaction", {
              "engagement": ["play_behaviour", "engage:0"]
            }
          ]
        ]
      ]
    },
    {
      "name": "engage",
      "actions": [
        [
          [ "text", "hello there" ],
          [ "play_behaviour", "next" ]
        ],
        [
          [ "custom", {
              "name": "number_input",
              "args": {
                "prompt": "ask me to count to a number",
                "output": "COUNTNUM",
                "type": "int",
                "min_value": 1,
                "max_value": 5
              }
            }
          ],
          [ "play_behaviour", "next" ]
        ],
        [
          [ "text", [ "I will start to count to {}", ["COUNTNUM"]] ],
          [ "knowledge", { "CNT": 1 } ],
          [ "play_behaviour", "next" ]
        ],
        [
          [ "compare", {
              "operand1": "CNT",
              "operand2": "COUNTNUM",
              "comparison_operator": "<=",
              "true_action": [ "play_behaviour", "next" ],
              "false_action": [ "play_behaviour", "6" ]
            }
          ]
        ],
        [
          [ "text", ["count {}",["CNT"]] ],
          [ "calculate",[ "CNT", "CNT + 1"] ],
          [ "delay", 2 ],
          [ "play_behaviour", "next" ]
        ],
        [
          [ "compare", {
              "operand1": "CNT",
              "operand2": "COUNTNUM",
              "comparison_operator": "<=",
              "true_action": [ "play_behaviour", "4" ],
              "false_action": [ "play_behaviour", "next" ]
            }
          ]
        ],
        [
          [ "text", "done" ],
          [ "play_behaviour", "next" ]
        ],
        [
          [ "play_behaviour", "engage:1" ]
        ]
      ]
    }
  ]
}
```

## Workflow Knowledge File
Every agent workflow (behaviour) file has an optional knowledge data file. Knowledge file stores all workflow configuration settings, preloading data as a JSON dictionary. Keys in the dictionary are all in UPPERCASE. They can be directly referenced in the workflow as the variable name. For example, when Lurawi runtime loads the JSON code in ```lurawi_example.json```, it will attempt to load ```lurawi_example_knowledge.json``` file if it exists. Behaviours in ```lurawi_example.json``` can reference a key in the knowledge dictionary as a predefined variable in its code.


### Lurawi Environment Variables
We have the following environment variables defined for every project. Normally, these configuration settings are defined in the individual project's knowledge JSON file. You can overwrite them with the corresponding environment variables:

|Environment variable | Description |
|---|---|
| PROJECT_NAME | Default project name to access Gen.Ai. Hub services |
| PROJECT_ACCESS_KEY | Access key of the project |

### Calling a Workflow in Lurawi

Lurawi workflow engine exposes one REST endpoint for triggering the loaded workflow:
```
http://{LURAWI_URL}/{project}/message
```

where ```project``` is the project name. For local testing, include ```--skip-auth``` in the commandline to skip the authentication step.

```message``` is JSON payload with the following structure:
```JSON
{
  "uid": "client/user id",
  "name": "client name",
  "session_id": "optional client provided session id",
  "activity_id": "optional activity id provided by previous interaction turn",
  "data" : {
    "message": "a text prompt message"
  }
}
```
```uid``` and ```name``` is a unique client user id and client name that may be used for triggering tailored workflow for individual user/client.  

```session_id``` is an optional client provided identifier mainly used to trace multi-turn/activity conversations when we enable conversation logging.  

```activity_id``` represents the last conversation activity returned by the previous workflow call. Client can include the ```activity_id``` to continue the workflow when the workflow is pending for additional client input, or used as a referece to log user feedback from a previous interaction (in this case, we expect a ```feedback``` string item in ```data``` dictionary).

```data``` contains a user defined dictionary that pass to the workflow directly. Uses ```query_knowledgebase``` custom action primitive to extra key-values from the dictionary.

In the case of ```lurawi_example``` code, we extract ```message``` as shown below:

<figure>
    <img src="./images/proccess_input.png"
         alt="Extract message data from input data payload" width="400px"
         />
    <figcaption>Fig. 7 Extract message data from input data payload.</figcaption>
</figure>

### Workflow Response
A ```message``` call can expect a response similar to the following:
```json
{
  "status": "success",
  "session_id": "session id if it is provided by the client",
  "activity_id": "effc95c4-9c8b-4561-b950-d9411d098e80",
  "response": "Hello, I'm an AI assistant"
}
```

