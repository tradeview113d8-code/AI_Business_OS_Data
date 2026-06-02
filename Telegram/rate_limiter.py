from collections import defaultdict
from time import time

_last = defaultdict(float)

def rate_limit(user_id, cooldown=2):
    now = time()
    if now - _last[user_id] < cooldown:
        return False
    _last[user_id] = now
    return True
