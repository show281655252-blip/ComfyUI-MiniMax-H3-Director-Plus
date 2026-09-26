# Modified for Director Plus isolation, 2026-09-26. See NOTICE.md for upstream attribution.
_DARK_YELLOW = "\033[38;5;136m"
_RESET = "\033[0m"


def log_dasiwa(component: str, message: str) -> None:
    print(f"{_DARK_YELLOW}[DaSiWa {component}]{_RESET} {message}")


def log_startup_summary(node_count: int) -> None:
    log_dasiwa(
        "Nodes",
        f"Loaded {node_count} extraordinarily overengineered nodes. 🐈",
    )
    log_dasiwa(
        "Nodes",
        "By using this you agree that cat ears improve everything, SlimeGirls deserve rights, "
        "Dragoniods need more screen time, darkness is the correct light source, and \"too many toggles\" "
        "is a phrase invented by cowards.",
    )
