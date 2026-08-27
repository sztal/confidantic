import sys

__all__ = ("is_runtime_jupyterlike",)


def is_runtime_jupyterlike() -> bool:
    """Determine whether code is running in a notebook-like kernel.

    Returns
    -------
    bool
        ``True`` for Jupyter-style kernel runtimes (including VS Code
        Interactive and notebooks), ``False`` otherwise.

    Notes
    -----
    This intentionally excludes the standard IPython terminal shell so
    CLI argument parsing remains available when running scripts via
    ``%run`` with command-line arguments.
    """
    if "ipykernel" in sys.modules:
        return True
    try:
        import IPython
    except Exception:
        return False
    get_ipython = getattr(IPython, "get_ipython", None)
    if get_ipython is None:
        return False
    shell = get_ipython()
    if shell is None:
        return False
    return type(shell).__name__ == "ZMQInteractiveShell"
