from constants import MAX_DEPTH

class CircuitBreaker:
    def __init__(self, maximum_allowed_depth=None):
        self.depth = 0
        self.maximum_allowed_depth = maximum_allowed_depth if maximum_allowed_depth is not None else MAX_DEPTH
        self.max_recorded_depth = 0

    def on_push(self):
        self.depth += 1
        if self.depth > self.maximum_allowed_depth:
            raise CircuitBreakerException(f"Max nesting depth {self.maximum_allowed_depth} exceeded")
        
        if self.depth > self.max_recorded_depth:
            self.max_recorded_depth = self.depth

    def on_pop(self):
        self.depth -= 1

        
class CircuitBreakerException(Exception):
    pass