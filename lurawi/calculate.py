import operator

from lurawi.arithmetic import evaluate_operand
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
        operand = evaluate_operand(self.arg_op, self.kb, self.arith_operators)
        if operand is None:
            logger.error(f"calculate: Invalid operand - {self.arg_op}")
            await self.failed()
        else:
            logger.debug(f"calculate: {self.arg_op} = {operand}")
            self.kb[self.kb_key] = operand
            await self.succeeded()
