import operator
import time
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class compare(CustomBehaviour):
    """!@brief Compares two operands and executes actions based on the comparison result.

    This behavior evaluates two operands (which can be knowledge base values,
    numbers, time, or arithmetic expressions) and performs a comparison using
    the specified operator. Based on the result, it executes either the true_action
    or false_action if provided.
    Args:
        operand1: First value to compare (string referencing kb key, number, "time", or arithmetic expression)
        operand2: Second value to compare (string referencing kb key, number, "time", or arithmetic expression)
        comparison_operator: Comparison operator to use ("<", "<=", "=", "!=", ">", ">=")
        success_action (list, optional): An action to execute if the value
                                         is successfully retrieved (e.g., `["play_behaviour", "2"]`).
        failed_action (list, optional): An action to execute if the retrieval
                                        fails (e.g., `["play_behaviour", "next"]`).

    Example:
    ["custom", { "name": "compare",
                 "args": {
                    "operand1": "temperature",
                    "operand2": "25",
                    "comparison_operator": ">",
                    "true_action": "turn_on_ac",
                    "false_action": "turn_off_ac"
                }
        }
    ]
    """

    def __init__(self, kb, details):
        super().__init__(kb=kb, details=details)
        # details is a dict with keys operand1, operand2, comparison_operator, true_action, false_action
        # operands can be: "a" where a is a key in kb or any number
        #                  "time" where time is current unix epoch time
        #                  "a-b+time..." where a,b... are keys in kb or numbers, time is UNIX time and the operators can be [+,-,*,/,%]
        # comparison_operator can only be: < less than, <= less than/equal to, = equal to,
        #                                  != not equal to, > greater than, >= greater than/equal to
        # true_action is what happens if the comparison result is true
        # false_action is what happens if comparison result is false

        self.comp_operators = {
            "<": operator.lt,
            ">": operator.gt,
            "=": operator.eq,
            "!=": operator.ne,
            "<=": operator.le,
            ">=": operator.ge,
        }
        self.arith_operators = {
            "+": operator.add,
            "-": operator.sub,
            "*": operator.mul,
            "!": operator.truediv,
            "/": operator.floordiv,
            "%": operator.mod,
        }

    async def run(self):
        if not isinstance(self.details, dict) or not all(
            k in self.details for k in ("operand1", "operand2", "comparison_operator")
        ):
            logger.error(
                "compare: details is expected to be a dict with keys-'operand1', 'operand2', 'true_action, 'false_action', 'comparison_operator'(got %s). Aborting",
                self.details,
            )
            await self.failed()
            return
        if self.details["comparison_operator"] not in self.comp_operators:
            logger.error(
                "Compare: Permitted comparison operators = %s, recieved = %s",
                self.comp_operators.keys(),
                self.details["comparison_operator"],
            )
            await self.failed()
            return
        operand1 = self.getOperand(self.details["operand1"], self.arith_operators)
        operand2 = self.getOperand(self.details["operand2"], self.arith_operators)
        if operand1 is None or operand2 is None:
            logger.error("compare: Invalid operand. op1=%s, op2=%s", operand1, operand2)
            await self.failed()
            return
        try:
            result = self.comp_operators[self.details["comparison_operator"]](
                operand1, operand2
            )
            logger.debug(
                "compare: %s %s %s. Result = %s",
                operand1,
                self.details["comparison_operator"],
                operand2,
                result,
            )
        except Exception as e:
            logger.error(
                "compare: operand1 = %s, operand2 = %s, operator = %s, exception = %s",
                operand1,
                operand2,
                self.details["comparison_operator"],
                e,
            )
            await self.failed()
            return
        if result:
            if "true_action" in self.details:
                await self.succeeded(self.details["true_action"])
            else:
                await self.succeeded()
        elif "false_action" in self.details:
            await self.succeeded(self.details["false_action"])
        else:
            await self.succeeded()

    def getOperand(self, arg, operators):
        # arg is an str with only arith operators

        comp_op_in_arg = [x for x in self.comp_operators if x in arg]
        if comp_op_in_arg:
            logger.error(
                "compare: Only arithmetic operators-%s allowed in operands.",
                self.arith_operators.keys(),
            )
            return None
        # print "\ninside getoperand, arg = {}".format(arg)
        op_in_arg = [x for x in arg if x in operators]
        # print 'opinarg=',op_in_arg
        if len(op_in_arg) == 0:
            # get operand
            if arg.strip().lower() == "time":
                operand = int(time.time())
            elif arg in self.kb:
                try:
                    operand = (
                        float(self.kb[arg])
                        if "." in self.kb[arg]
                        else int(self.kb[arg])
                    )
                except Exception as _:
                    operand = self.kb[arg]
            else:
                try:
                    operand = float(arg) if "." in arg else int(arg)
                except Exception as _:
                    operand = arg
            # print 'No op in arg. operand = {}\n'.format(operand)
            return operand
        else:
            result = 0
            splitted = arg.split(op_in_arg[0], 1)
            _result = splitted[0]
            _arg = splitted[1]
            result = self.getOperand(_result, self.arith_operators)
            for i, op in enumerate(op_in_arg):
                # print "\n_arg = {} i={}, op={}, result={}".format(_arg, i, op, result)
                if i + 1 < len(op_in_arg):
                    splitted = _arg.split(op_in_arg[i + 1], 1)
                    # print 'fwd splitted = {}'.format(splitted)
                    _operand = splitted[0]
                    _arg = splitted[1]
                    operand = self.getOperand(_operand, self.arith_operators)
                else:
                    operand = self.getOperand(_arg, self.arith_operators)
                if operand is None:
                    return None
                try:
                    result = self.arith_operators[op](result, operand)
                except Exception as e:
                    logger.error(
                        "compare: Exception while %s %s %s. e=%s",
                        result,
                        op,
                        operand,
                        e,
                    )
                    return None
                # print 'operand = {}, result = {} _arg = {}'.format(operand, result, _arg)
            return result
