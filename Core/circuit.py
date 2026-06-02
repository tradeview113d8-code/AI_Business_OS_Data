import time

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_threshold  = failure_threshold
        self.recovery_timeout   = recovery_timeout
        self.failure_count      = 0
        self.state              = "closed"
        self.last_failure_time  = 0

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.recovery_timeout:
                self.state = "half_open"
            else:
                raise Exception(
                    f"Circuit OPEN — retry in "
                    f"{int(self.recovery_timeout - elapsed)}s"
                )
        try:
            result = func(*args, **kwargs)
            if self.state == "half_open":
                self.state         = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count    += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            raise e
