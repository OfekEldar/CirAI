import numpy as np
import sympy as sp
from scipy.optimize import differential_evolution, minimize

def maximize_transfer_function(params_vec, freq_min, freq_max, formula_str):
    """
    Args:
        params_vec: רשימה של [name, min_val, max_val]
        freq_min, freq_max: גבולות התדר (ב-Hz)
        formula_str: הנוסחה כסטרינג, למשל "1 / (1 + R1 * C1 * s)"
    Returns:
        (max_val, optimal_params, optimal_freq)
    """
    s = sp.symbols('s')
    param_names = [p[0] for p in params_vec]
    sym_params = sp.symbols(param_names)
    expr = sp.sympify(formula_str)
    func = sp.lambdify([s] + list(sym_params), expr, modules='numpy')
    bounds = [(p[1], p[2]) for p in params_vec]
    bounds.append((freq_min, freq_max))
    def objective(x):
        current_params = x[:-1] 
        current_freq = x[-1] 
        s_val = 1j * 2 * np.pi * current_freq
        try:
            h_val = func(s_val, *current_params)
            return -h_val
        except Exception:
            return 0
    result = differential_evolution(objective, bounds, seed=42)
    max_magnitude = -result.fun
    optimal_vals = result.x[:-1]
    optimal_freq = result.x[-1]
    best_params_dict = {name: val for name, val in zip(param_names, optimal_vals)}
    return max_magnitude, best_params_dict, optimal_freq

# --- דוגמת הרצה ---

# נגדיר מעגל Low Pass Filter פשוט: H(s) = 1 / (1 + R*C*s)
# אנו מצפים שהמקסימום יהיה בתדר הנמוך ביותר ובהתנגדות/קיבול הנמוכים ביותר (כדי להקטין את המכנה)
params = [
    ['L', 50e-12, 150e-12],   # נגד בין 1k ל-10k
    ['C', 1e-15, 10e-12]    # קבל בין 1uF ל-10uF
]

f_min = 8e9
f_max = 12e9
formula = "s*L/(1+(s^2)*L*C)"  

max_val, best_params, best_freq = maximize_transfer_function(params, f_min, f_max, formula)

print(f"Max Magnitude: {max_val:.4f}")
print(f"At Frequency: {best_freq:.2f} Hz")
print("Best Parameters:")
print(best_params)