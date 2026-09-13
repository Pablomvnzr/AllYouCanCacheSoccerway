import numpy as np


def probabilities(distribution, count, alpha=1.5):
    if count < 1:
        raise ValueError("Catálogo vacío")
    if distribution == "uniforme":
        return np.full(count, 1 / count)
    if distribution == "zipf" and alpha > 1:
        weights = np.arange(1, count + 1, dtype=float) ** -alpha
        return weights / weights.sum()
    raise ValueError("Distribución inválida o alpha Zipf <= 1")


def get_distribucion_index(tipo_distribucion, num_opciones, parametro_zipf=1.5, rng=None):
    rng = rng if rng is not None else np.random
    return int(rng.choice(num_opciones, p=probabilities(tipo_distribucion, num_opciones, parametro_zipf)))


def arrival_delay(distribution, mean_seconds, rng, alpha=1.5):
    if mean_seconds < 0:
        raise ValueError("Espera negativa")
    if distribution == "constant":
        return mean_seconds
    if distribution == "uniforme":
        return float(rng.uniform(0, 2 * mean_seconds))
    ranks = np.arange(1, 51, dtype=float)
    p = probabilities(distribution, 50, alpha)
    return float(rng.choice(ranks, p=p) * mean_seconds / np.dot(ranks, p))
