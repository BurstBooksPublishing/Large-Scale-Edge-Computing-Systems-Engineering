# Minimal production-grade privacy budget manager for edge nodes.
# Depends: numpy, typing. Integrate with TF-Privacy or Opacus for mechanisms.
from typing import Dict, Tuple
import math
import time

class BudgetExceeded(Exception):
    pass

class PrivacyBudgetManager:
    def __init__(self, global_delta: float = 1e-5):
        # store per-user budgets: {user_id: (eps_remaining, delta_remaining)}
        self._budgets: Dict[str, Tuple[float, float]] = {}
        self.global_delta = global_delta

    def allocate_user(self, user_id: str, eps: float, delta: float):
        """Provision initial budget for a user/device."""
        self._budgets[user_id] = (eps, delta)

    def _advanced_compose(self, eps_list, delta0, target_delta):
        """Return composed epsilon using advanced composition (Eq. 2)."""
        k = len(eps_list)
        eps = sum(eps_list) / k if k else 0.0
        # Conservative approximate bound: Eq. (2)
        eps_prime = math.sqrt(2*k*math.log(1.0/target_delta))*eps + k*eps*(math.exp(eps)-1.0)
        return eps_prime

    def recommend_sigma(self, sensitivity: float, eps: float, delta: float) -> float:
        """Gaussian noise sigma per Eq. (3)."""
        return (sensitivity * math.sqrt(2.0*math.log(1.25/delta))) / eps

    def consume(self, user_id: str, eps: float, delta: float):
        """Consume budget for a single operation; raise if exceeded."""
        if user_id not in self._budgets:
            raise KeyError("Unknown user")
        eps_rem, delta_rem = self._budgets[user_id]
        if eps > eps_rem + 1e-12 or delta > delta_rem + 1e-12:
            raise BudgetExceeded("Budget exhausted for user")
        self._budgets[user_id] = (eps_rem - eps, delta_rem - delta)

    def get_remaining(self, user_id: str) -> Tuple[float, float]:
        return self._budgets.get(user_id, (0.0, 0.0))

# Example usage on-device:
# mgr = PrivacyBudgetManager(global_delta=1e-5)
# mgr.allocate_user("device-42", eps=5.0, delta=1e-5)
# sigma = mgr.recommend_sigma(sensitivity=1.0, eps=0.2, delta=1e-6)
# mgr.consume("device-42", eps=0.2, delta=1e-6)