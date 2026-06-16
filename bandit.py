import math
import random
import numpy as np
from products import PRODUCTS

class UCB1Bandit:
    def __init__(self):
        self.n_arms = 50
        self.counts = np.zeros(self.n_arms)
        self.values = np.zeros(self.n_arms)
        self.category_boost = {}

    def update(self, arm_index: int, categories_clicked: list[str]):
        self.counts[arm_index] += 1
        n = self.counts[arm_index]
        self.values[arm_index] += (1.0 - self.values[arm_index]) / n
        
        for category in categories_clicked:
            current_boost = self.category_boost.get(category, 0.0)
            self.category_boost[category] = min(1.0, current_boost + 0.15)

    def get_ucb_scores(self, total_clicks: int) -> np.ndarray:
        scores = np.zeros(self.n_arms)
        for i in range(self.n_arms):
            if self.counts[i] == 0:
                scores[i] = 1.0 + random.uniform(0, 0.1)
            else:
                ucb = self.values[i] + math.sqrt(2 * math.log(total_clicks + 1) / self.counts[i])
                category = PRODUCTS[i]["category"]
                boost = self.category_boost.get(category, 0.0)
                scores[i] = ucb + boost
        return scores

    def get_recommendations(self, total_clicks: int, top_n: int = 10) -> list[int]:
        scores = self.get_ucb_scores(total_clicks)
        # argsort sorts ascending, so we reverse it
        top_indices = np.argsort(scores)[::-1][:top_n]
        return top_indices.tolist()

    def to_dict(self) -> dict:
        return {
            "counts": self.counts.tolist(),
            "values": self.values.tolist(),
            "category_boost": self.category_boost,
            "total_clicks": int(np.sum(self.counts))
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UCB1Bandit':
        bandit = cls()
        bandit.counts = np.array(data["counts"])
        bandit.values = np.array(data["values"])
        bandit.category_boost = data.get("category_boost", {})
        return bandit
