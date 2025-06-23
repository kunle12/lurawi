# Creating Custom Action Primitives in Lurawi

This document provides comprehensive instructions on how to create custom action primitives in Lurawi using Python. These custom functions enable advanced functionalities such as data processing, integration with external services, and the implementation of complex business logic within Lurawi workflows. A practical example of a Fibonacci sequence generator is used to illustrate the development process.

## Custom Action Primitive Architecture

A custom action primitive is implemented as a Python class that inherits from the `CustomBehaviour` class, defined in [`lurawi/custom_behaviour.py`](lurawi/custom_behaviour.py). Each custom class must implement an `__init__` method and an `async run` method. An optional `fini` method can also be included for resource cleanup.

### `CustomBehaviour` Class

This is the foundational class for all custom action primitives in Lurawi, providing the necessary base functionality.

### `__init__(self, kb, details)` Method

The constructor for your custom action primitive.

*   `kb` (`dict`): A reference to the workflow's knowledge base, a dictionary used for storing and retrieving data.
*   `details` (`dict`): A dictionary containing the configuration details and input parameters for the specific custom action primitive instance.

### `async run(self)` Method

This asynchronous method encapsulates the primary logic of your custom action primitive. It is invoked when the action primitive is executed within a Lurawi workflow. The method must handle input validation and manage the flow of control based on success or failure.

### `fini(self)` Method (Optional)

This method is executed when the behaviour is finalized, typically used for releasing resources or performing any necessary cleanup operations.

## Example: Fibonacci Sequence Generator

This example demonstrates how to create a custom action primitive that generates a Fibonacci sequence up to a specified number, illustrating the use of the `kb` and `details` parameters, and handling success/failure states.

### Step 1: Create the Custom Function File

Execute the following command in your terminal to create a skeleton custom function file named [`fibonacci_seq.py`](lurawi/custom/fibonacci_seq.py) within the `lurawi/custom/` directory. This command also establishes the necessary internal links for Lurawi to recognize the new custom function.

```bash
lurawi custom new fibonacci_seq
```

### Step 2: Implement the `fibonacci_seq` Class

Open the newly created [`fibonacci_seq.py`](lurawi/custom/fibonacci_seq.py) file and modify its content with the following Python code:

```python
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

    def fini(self):
        # do cleaning up here
        pass
```

#### Class Docstring

The docstring within the `fibonacci_seq` class defines a JSON code example illustrating how the `fibonacci_seq` custom action primitive should be invoked. It is crucial to maintain this docstring in direct correspondence with the actual implementation, as the example JSON code (with dummy data input) is used by the visual programming editor to keep its interface up-to-date.

#### Class Initialization

The `__init__` method follows standard Python class initialization conventions. You can define additional instance variables within this method as needed.

#### Implementing the `async run` Method

The `async run` method is the core of every custom action primitive. Due to the flexible nature of JSON code, which allows arbitrary input types to be fed into custom code, the `run` method must perform necessary checks on the input data. In this example, it validates that the `size` input is a positive integer. To accommodate scenarios where the input might be a variable name stored in the knowledge base, the method also checks the knowledge base and extracts the actual data if applicable.

If input validation fails, `await self.failed()` is immediately called, and the method returns. This mechanism is analogous to throwing an exception in other programming languages, and the error is also logged in the system.

The method then generates a list of Fibonacci numbers and stores them in a knowledge base variable specified by the `output` parameter in `self.details`. If `output` is not provided, the result is saved under the generic name `FIBONACCI_SEQ`.

If a `success_action` is defined in `self.details`, that action is invoked upon successful execution. Conversely, in a simulated failure case (e.g., `input_size == 1` in this example), if a `failed_action` is provided, it is called. This illustrates how a custom action primitive can manage its success and failure states.

**This implementation covers the essential requirements for most custom action primitives.**

### (Optional) Step 3: Cleanup (`fini` method)

```python
    def fini(self):
        # do cleaning up here
        pass
```
You can implement the `fini` method to perform any necessary cleanup operations after the custom action primitive completes its execution.

## Usage

To utilize a newly created custom function, simply restart the Lurawi development environment by running `lurawi dev`.

**NOTE**: It is essential to download and save your workflow XML file before restarting the Lurawi service, as the visual editor will automatically update with the latest custom definitions.

For any code changes made to an existing custom function, a Lurawi service restart is generally not required. New code will be hot-loaded when you run or call the workflow, allowing for rapid iteration during development.