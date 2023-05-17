from abc import abstractmethod
from typing import Callable, List, Any, Dict

import rangekeeper as rk


class Policy:
    def __init__(
            self,
            state: rk.flux.Flow,
            model: object,
            condition: Callable[[rk.flux.Flow], List[bool]],
            action: Callable[[object, List[bool]], object]):
        self.state = state
        self.model = model
        self.condition = condition
        self.action = action

    def execute(self) -> object:
        decision = self.condition(self.state)
        return self.action(self.model, decision)
