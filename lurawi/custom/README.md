# Lurawi Custom Action Primitives

## Prerequisite
Follow the instruction [here](../../docs/LurawiDevContainer.md) to run Lurawi as a dev docker container.

<figure>
    <img src="../../docs/images/devcontainer3.png"
         alt="Dispatch Workflow to runtime engine" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 1 custom directory under lurawi highlighted in yellow.</figcaption>
</figure>

The ```custom``` directory(Fig. 1) contains a set of prebuilt custom action primitives that can be used as parts of Agent based orchestration workflows. Each custom primitive achieves a specific task with a set of custom defined inputs. This document provides step-by-step instructions on how to create a simple custom action primitive.

**WARNING**: Any code modifications in the dev container will be lost if the dev container is rebuilt!!! BE SURE to copy and save all your code changes under ```/home/lurawi``` directory before changing ```.devcontainer.json``` file, for example.

## A custom that generates a Fibonacci Sequence
To illustrate the steps required to create a custom action primitive, we are going to create a simple custom that generates a Fibonacci sequence (with an input size) as a concrete example.

### Step 1. Create a custom class

```Python
from ..utils import logger
from ..custom_behaviour import CustomBehaviour

class fibonacci_seq(CustomBehaviour):
    """!@brief generate a Fibonacci sequence.
    Example:
    ["custom", { "name": "fibonacci_seq",
                 "args": {
                            "size": 4,
                            "output": "FIB_SEQ",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    @note only limited parameters are supported in this call
    """

    def __init__(self, kb, details):
        super(fibonacci_seq, self).__init__(kb,details)
```

In the code above, we import the custom base class `CustomBehaviour` and create a new custom class called `fibonacci_seq`.

#### The class DocString
The docstring defines a JSON code example of how `fibonacci_seq` should be called. It is essential that this docstring is created and maintained in correspondence to the acutal custom implementation. The example JSON code (with dummy data input) must presented so that visual programming editor runner can keep the editor up-to-date.

#### Class initialisation
A stardard Python class `__init__` def should be followed as shown above. You may place additional variables in the `__init__` method.

### Step 2. Implement **`run`** method
```Python
    async def run(self):
        size = self.parse_simple_input(key="size", check_for_type="int")

        if size is None or size <= 0:
            logger.error("fibonacci_seq: invalid input 'size', must be a +ve integer.")
            await self.failed()
            return
```

async `run` method is the key method that every custom action primitive need to implement. Because the flexibility of the JSON code allows any abitrary (type of) input to be fed into the custom code. `run` method must perform the necessary checks on the input data. In this case, we must check whether `size` input is a positive integer. To accomodate the possiblity that input might a variable (name) in the knowledgebase, check against the knowledgebase and extract the actual data when it is indeed the case.

If input validation failed, we immediately call `await self.failed()` and `return`, this corresponds to throwing an exception in other programming languages. We also log the error in the system.

```Python
        if input_size > 1:
            # first two terms
            n1, n2 = 0, 1
            count = 0
            # generate fibonacci sequence
            print("Fibonacci sequence:")
            fseq = []
            while count < input_size:
                fseq.append(n1)
                nth = n1 + n2
                # update values
                n1 = n2
                n2 = nth
                count += 1
            if 'output' in self.details and isinstance(self.details['output'], str):
                self.kb[self.details['output']] = fseq
            else:
                self.kb['FIBONACCI_SEQ'] = fseq
            await self.succeeded()
        else:  # a simulated failed case
            await self.failed()
```

Now we generate a list of Fibonacci numbers and save them in a knowledgebase variable specified in the `output`. If `output` is not given, we save the result under a generic name  `FIBONACCI_SEQ`.

If the follow on `success_action` is defined, we call the action, whereas in *failed* case, we call the `failed_action` when it is provided. Note that, we deliberately treating `input_size == 1` as the fail case in this custom to illustrate how a custom may handle its failed cases. 

**This is all you need to implement for most custom action primitives!!**

### (Optional) Step 3. Cleanup

```Python
    def fini(self):
        # do cleaning up here
        pass
```
You can implement a `fini` method for cleaning up any additional resources after the cusom finishes its execution.

## Usage
To use a newly created custom function, simply rerun ```./run_lurawi_service.sh```. **NOTE**: you need download/save your workflow xml file before you restart the lurawi service because the visual editor will be automagically updated with latest custom definitions.

For any code changes made to an existing custom, no lurawi service restart required. New code will be hot-loaded when you run/call the workflow. 