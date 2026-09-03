import random

def choose_model(user_id):
    random.seed(user_id)
    return "model_A" if random.random() < 0.5 else "model_B"

def log_ab_result(user_id, model_version, outcome):
    with open("data/ab_results.csv", "a") as f:
        f.write(f"{user_id},{model_version},{outcome}\n")
