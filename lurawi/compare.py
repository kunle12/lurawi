import operator
import time
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class compare(CustomBehaviour):
    def __init__(self, kb, details):
        super().__init__(kb)
        self.kb = kb
        self.details = details
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
                f"compare: details is expected to be a dict with keys-'operand1', 'operand2', 'true_action, 'false_action', 'comparison_operator'(got {self.details}). Aborting"
            )
            await self.failed()
            return
        if self.details["comparison_operator"] not in self.comp_operators:
            logger.error(
                f"Compare: Permitted comparison operators = {self.comp_operators.keys()}, recieved = {self.details['comparison_operator']}"
            )
            await self.failed()
            return
        operand1 = self.getOperand(self.details["operand1"], self.arith_operators)
        operand2 = self.getOperand(self.details["operand2"], self.arith_operators)
        if operand1 is None or operand2 is None:
            logger.error(f"compare: Invalid operand. op1={operand1}, op2={operand2}")
            await self.failed()
            return
        try:
            result = self.comp_operators[self.details["comparison_operator"]](
                operand1, operand2
            )
            logger.debug(
                f"compare: {operand1} {self.details['comparison_operator']} {operand2} . Result = {result}"
            )
        except Exception as e:
            logger.error(
                f"compare: operand1 = {operand1}, operand2 = {operand2}, operator = {self.details['comparison_operator']}, exception = {e}"
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
                f"compare: Only arithmetic operators-{self.arith_operators.keys()} allowed in operands."
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
                except:
                    operand = self.kb[arg]
            else:
                try:
                    operand = float(arg) if "." in arg else int(arg)
                except:
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
                        f"compare: Exception while {result} {op} {operand}. e={e}"
                    )
                    return None
                # print 'operand = {}, result = {} _arg = {}'.format(operand, result, _arg)
            return result
