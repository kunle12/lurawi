# Lurawi Custom Action Primitives

## Prerequisite
Follow the instruction [here](LurawiDevContainer.md) to run Lurawi as a dev docker container.

The ```/opt/default/lurawi/custom``` directory contains a set of prebuilt custom action primitives that can be used as parts of Agent based orchestration workflows. Each custom primitive achieves a specific task with a set of custom defined inputs. This document provides step-by-step instructions on how to create a simple custom action primitive.

## A custom that generates a Fibonacci Sequence
To illustrate the steps required to create a custom action primitive, we are going to create a simple custom that generates a Fibonacci sequence (with an input size) as a concrete example.

### Step 1. Create a custom class
Run the following command to create a skeleton custom function file ```fibonacci_seq.py``` in ```/home/lurawi/custom``` directory and link it to the Lurawi internal custom directory.
```bash
lurawi custom new fibonacci_seq
```
Open the file and modify ```fibonacci_seq``` class with the code below

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
        super(fibonacci_seq, self).__init__(kb)
        self.details = details
```

In the code above, we import the custom base class `CustomBehaviour` and create a new custom class called `fibonacci_seq`.

#### The class DocString
The docstring defines a JSON code example of how `fibonacci_seq` should be called. It is essential that this docstring is created and maintained in correspondence to the acutal custom implementation. The example JSON code (with dummy data input) must presented so that visual programming editor runner can keep the editor up-to-date.

#### Class initialisation
A stardard Python class `__init__` def should be followed as shown above. You may place additional variables in the `__init__` method.

### Step 2. Implement **`run`** method
```Python
    async def run(self):
        if 'size' not in self.details:
            logger.error("fibonacci_seq: missing input 'size'.")
            await self.failed()
            return
        input_size = self.details['size']
        if isinstance(input_size, str) and input_size in self.kb:
            input_size = self.kb[input_size]

        if not isinstance(input_size, int) or input_size <= 0:
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
            if 'success_action' in self.details:
                await self.succeeded(actions=self.details['success_action'])
            else:
                await self.succeeded()
        else:  # a simulated failed case
            if 'failed_action' in self.details:
                await self.failed(actions=self.details['failed_action'])
            else:
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
To use a newly created custom function, simply rerun ```lurawi dev```. **NOTE**: you need download/save your workflow xml file before you restart the lurawi service because the visual editor will be automagically updated with latest custom definitions.

For any code changes made to an existing custom, no lurawi service restart required. New code will be hot-loaded when you run/call the workflow. 