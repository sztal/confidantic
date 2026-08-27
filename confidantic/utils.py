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
        from IPython import get_ipython
    except Exception:
        return False
    shell = get_ipython()
    if shell is None:
        return False
    return shell.__class__.__name__ == "ZMQInteractiveShell"
