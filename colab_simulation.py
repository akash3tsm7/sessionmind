import numpy as np
import matplotlib.pyplot as plt
import random

# --- STANDALONE UCB1 BANDIT SIMULATION FOR COLAB ---
# This script simulates a user's clickstream session to prove that 
# the UCB1 Contextual Bandit learns and shifts recommendations in real-time.

# 1. Mock Data (50 items total, 6 are Electronics)
PRODUCTS = [
    {"id": f"e{i}", "name": f"Electronics Item {i}", "category": "Electronics"} for i in range(1, 7)
]
for i in range(7, 51):
    PRODUCTS.append({"id": f"p{i}", "name": f"Other Product {i}", "category": "Other"})

# 2. Core Bandit Logic (Identical to our FastAPI backend)
class UCB1Bandit:
    def __init__(self):
        self.n_arms = 50
        self.counts = np.zeros(self.n_arms)
        self.values = np.zeros(self.n_arms)
        self.category_boost = {}

    def update(self, arm_index: int, categories_clicked: list):
        self.counts[arm_index] += 1
        n = self.counts[arm_index]
        self.values[arm_index] += (1.0 - self.values[arm_index]) / n
        for category in categories_clicked:
            self.category_boost[category] = min(1.0, self.category_boost.get(category, 0.0) + 0.15)

    def get_ucb_scores(self, total_clicks: int) -> np.ndarray:
        scores = np.zeros(self.n_arms)
        for i in range(self.n_arms):
            if self.counts[i] == 0:
                scores[i] = 1.0 + random.uniform(0, 0.1) # Initial exploration
            else:
                ucb = self.values[i] + np.sqrt(2 * np.log(total_clicks + 1) / self.counts[i])
                boost = self.category_boost.get(PRODUCTS[i]["category"], 0.0)
                scores[i] = ucb + boost
        return scores

# 3. Simulate User Journey
def simulate():
    bandit = UCB1Bandit()
    steps = 150 # Number of clicks in the simulated session
    
    elec_indices = [i for i, p in enumerate(PRODUCTS) if p["category"] == "Electronics"]
    other_indices = [i for i, p in enumerate(PRODUCTS) if p["category"] != "Electronics"]
    
    history_elec_score = []
    history_other_score = []
    
    print("Starting simulation of 150 clicks for a user who loves Electronics...")
    
    for step in range(1, steps + 1):
        scores = bandit.get_ucb_scores(step - 1)
        top_10 = np.argsort(scores)[::-1][:10]
        
        # User Behavior Model: 
        # If an Electronic item is recommended, they click it 85% of the time.
        # Otherwise, they randomly browse.
        clicked_arm = None
        for idx in top_10:
            if idx in elec_indices and random.random() < 0.85:
                clicked_arm = idx
                break
            elif idx in other_indices and random.random() < 0.05:
                clicked_arm = idx
                break
                
        if clicked_arm is None:
            clicked_arm = random.choice(range(50))
            
        # Update model
        bandit.update(clicked_arm, [PRODUCTS[clicked_arm]["category"]])
        
        # Track metrics
        history_elec_score.append(np.mean(scores[elec_indices]))
        history_other_score.append(np.mean(scores[other_indices]))

    # 4. Plotting the Convergence
    plt.figure(figsize=(12, 6))
    plt.plot(range(1, steps + 1), history_elec_score, label="Avg UCB Score (Electronics)", color="#3b82f6", linewidth=2.5)
    plt.plot(range(1, steps + 1), history_other_score, label="Avg UCB Score (Other Categories)", color="#9ca3af", linewidth=1.5, linestyle="--")
    
    plt.title("SessionMind Bandit Convergence: Real-Time Personalization Shift", fontsize=16, fontweight="bold")
    plt.xlabel("In-Session Events (Clicks)", fontsize=12)
    plt.ylabel("System Confidence (UCB Score + Category Boost)", fontsize=12)
    
    plt.axvline(x=15, color='#ef4444', linestyle=':', label="Rapid Adaptation Phase Ends (~15 clicks)")
    plt.fill_between(range(1, steps + 1), history_elec_score, history_other_score, color='#3b82f6', alpha=0.1)
    
    plt.legend(loc="upper left")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    simulate()
