"""Shared arithmetic operand evaluation for the calculate and compare behaviours.

Both behaviours evaluate an arithmetic expression string (e.g. "2*time+KB_KEY")
against the knowledge base, resolving numeric literals, KB keys and the special
"time" token. This module centralises that logic to avoid duplication.
"""

import time

from lurawi.utils import logger


def evaluate_operand(arg, kb, operators):
    """Evaluate an arithmetic expression string to a single value.

    Args:
        arg: expression string, e.g. "2*time+KB_KEY"
        kb: knowledge base dict used to resolve keys
        operators: dict mapping operator chars to callables

    Returns:
        the evaluated value, or None if the expression is invalid
    """
    op_in_arg = [x for x in arg if x in operators]
    if len(op_in_arg) == 0:
        if arg.strip().lower() == "time":
            return int(time.time())
        if arg in kb:
            try:
                return float(kb[arg]) if "." in kb[arg] else int(kb[arg])
            except Exception:
                return kb[arg]
        try:
            return float(arg) if "." in arg else int(arg)
        except Exception:
            return arg

    splitted = arg.split(op_in_arg[0], 1)
    result = evaluate_operand(splitted[0], kb, operators)
    _arg = splitted[1]
    for i, op in enumerate(op_in_arg):
        if i + 1 < len(op_in_arg):
            splitted = _arg.split(op_in_arg[i + 1], 1)
            operand = evaluate_operand(splitted[0], kb, operators)
            _arg = splitted[1]
        else:
            operand = evaluate_operand(_arg, kb, operators)
        if operand is None:
            return None
        try:
            result = operators[op](result, operand)
        except Exception as e:
            logger.error("evaluate_operand: exception while %s %s %s: %s", result, op, operand, e)
            return None
    return result
