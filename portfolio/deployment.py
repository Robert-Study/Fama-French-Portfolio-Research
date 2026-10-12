from importlib.util import find_spec


# Distribution names can differ from the names used by Python imports.
PACKAGES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "scikit-learn": "sklearn",
    "cvxpy": "cvxpy",
    "osqp": "osqp",
    "plotly": "plotly",
    "openpyxl": "openpyxl",
}


def missing_dependencies():
    return [package for package, module in PACKAGES.items() if find_spec(module) is None]
