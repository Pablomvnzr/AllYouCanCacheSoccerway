import numpy as np

def get_distribucion_index(tipo_distribucion, num_opciones, parametro_zipf=1.5):
    """Retorna el índice basado en la distribución elegida."""
    if tipo_distribucion == "uniforme":
        return np.random.randint(0, num_opciones)
    elif tipo_distribucion == "zipf":
        idx = np.random.zipf(parametro_zipf) - 1
        return idx % num_opciones
    return 0
