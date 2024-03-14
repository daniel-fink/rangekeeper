from abc import abstractmethod
from typing import Callable, List, Any, Dict

import rangekeeper as rk


class Policy:
    def __init__(
            self,
            condition: Callable[[rk.flux.Flow], List[bool]],
            action: Callable[[object, List[bool]], object]):
        self.condition = condition
        self.action = action

    def execute(
            self,
            args: tuple) -> object:
        state, model = args  # This is done to assist multiprocessing
        decision = self.condition(state)
        return self.action(model, decision)
