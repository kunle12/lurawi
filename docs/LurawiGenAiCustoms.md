# Lurawi Custom Function Blocks

## Introduction
Lurawi features an extensible plugin system built upon custom Python script modules and functions. These modules are represented in the visual editor as `run_function` blocks, also known as custom function blocks. A pulldown list reveals all custom functions currently available in the system:

<figure>
    <img src="./images/run_function.png"
         alt="Available custom functions" width="200px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 1: Available custom functions.</figcaption>
</figure>

Selecting a custom function changes the appearance of the custom function block (as shown in Fig. 1). Data blocks can be attached to the entry points of these custom function blocks. This document details the custom functions available for building Agent-based workflows that leverage the capabilities of the Gen. AI. Hub foundation service. The following sections are organized by the tasks you can achieve. For an example of how these custom function blocks are used, refer to [Advanced: RAG Reference Implementation in Lurawi](RAGReferenceImplementation.md).

## Prompt Constructions

### Manual Prompt Construction

To build a prompt string piece by piece, use the standard **Text** blocks:

<img src="./images/text_primitives.png"
         alt="Text primitives" width="200px"/>
Select the `create text with` block and plug in plain text or variable blocks to form a complete text prompt. The resulting text can be either stored in another variable (within an **ActionLet**) or attached directly to a custom function block. For example:

<figure>
    <img src="./images/text_actionlet.png"
         alt="Text ActionLets" width="500px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 2: Composing a prompt text string and saving it into a variable as an ActionLet.</figcaption>
</figure>

### Populate a Prompt Template

You can populate a templated prompt string (stored in a variable) using the `populate_prompt` custom function:

<img src="./images/populate_prompt.png"
         alt="Populate prompt custom function" width="350px"/>

The `prompt_text` input accepts a prompt template string. The `replace` input takes a dictionary, similar to the `replace` parameter in the `get_prompt` custom function. The final text string is assigned to the variable attached to the `output` port.


### Build OpenAI GPT Specific Prompt

`build_gpt_prompt` is a convenient custom function that combines a system prompt, user prompt, and optional search documents and conversation history into an OpenAI GPT prompt list structure:

```json
[
  {"role": "system", "content": "system prompt"},
  {"role": "user", "content": "user prompt text"},
  ...
]
```

<img src="./images/build_gpt_prompt.png"
         alt="Build GPT prompt custom function" width="350px"/>

You can specify `max_tokens` to restrict the overall size of the final output prompt. If the constructed prompt exceeds the maximum size, history and document data will be progressively stripped to reduce the final prompt size.


## Calling OpenAI Compatible LLM endpoint

The usage of `invoke_llm` is similar and self-explanatory to the `get_prompt` custom function:

<img src="./images/invoke_llm.png"
         alt="Invoke LLM custom function" width="350px"/>

The `stream` input accepts a boolean value. When set to `true` and `invoke_llm` is successful, a `stream_point` is sent to the client in the payload response as the final result. The workflow terminates at this point (`success_action` will not be called). The client must then use this string to fetch the stream itself.

By default, `stream` is set to `false`. In this case, the result of the LLM call will be saved in the `response` variable and can be returned to the client via a `say` action.
