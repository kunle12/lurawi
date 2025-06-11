import operator
import time
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class calculate(CustomBehaviour):
    def __init__(self, kb, kb_key, operand):
        super().__init__(kb)
        self.kb = kb

        # operand can be: "a" where a is a key in kb or any number
        #                   "a-b+c..." where a,b,c... are keys in kb or numbers or time and the operators can be [+,-,*,/,%]
        #                   "time" where time is current unix epoch time

        self.arith_operators = {
            "+": operator.add,
            "-": operator.sub,
            "*": operator.mul,
            "/": operator.floordiv,
            "!": operator.truediv,
            "%": operator.mod,
        }

        self.arg_op = operand.replace(" ", "")
        self.kb_key = kb_key

    async def run(self):
        if not isinstance(self.kb, dict):
            logger.error("calculate: kb has to be a dictionary. Aborting")
            await self.failed()
            return
        operand = self.getOperand(self.arg_op, self.arith_operators)
        if operand is None:
            logger.error(f"calculate: Invalid operand - {self.arg_op}")
            await self.failed()
        else:
            logger.debug(f"calculate: {self.arg_op} = {operand}")
            self.kb[self.kb_key] = operand
            await self.succeeded()

    def getOperand(self, arg, operators):
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
                        f"calculate: Exception while {result} {op} {operand}. e={e}"
                    )
                    return None
                # print 'operand = {}, result = {} _arg = {}'.format(operand, result, _arg)
            return result
