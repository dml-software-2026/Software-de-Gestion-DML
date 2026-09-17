def build_flow_steps(labels, current_index):
    """Arma la lista de pasos para el tracker visual del flujo (#158).

    current_index es 1-based: el paso más avanzado ya alcanzado por el
    registro. Cada paso queda con label + state (done/current/pending)
    para que _flow_tracker.html solo tenga que pintar, sin lógica propia.
    """
    return [
        {
            "label": label,
            "state": "done" if i < current_index else ("current" if i == current_index else "pending"),
        }
        for i, label in enumerate(labels, start=1)
    ]
