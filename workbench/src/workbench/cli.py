"""workbench command line: serve the app, or hash the operator password."""

from __future__ import annotations

import argparse
import getpass
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workbench")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the workbench server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8790)
    serve.add_argument("--reload", action="store_true", help="restart when the backend's Python code changes (development)")
    sub.add_parser("hash-password", help="read a password and print its hash for WORKBENCH_PASSWORD_HASH")
    args = parser.parse_args(argv)

    if args.command == "hash-password":
        from .auth import hash_password

        password = getpass.getpass("operator password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\n")
        if not password:
            print("workbench: empty password", file=sys.stderr)
            return 1
        print(hash_password(password))
        return 0

    import logging

    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    from pathlib import Path

    from .config import Config, ConfigError

    try:
        Config.from_env()  # fail here, once, rather than in every reloaded worker
    except ConfigError as exc:
        print(f"workbench: {exc}", file=sys.stderr)
        return 2
    src = Path(__file__).resolve().parents[1]
    uvicorn.run(
        "workbench.app:create_app_from_env",
        factory=True,
        host=args.host,
        port=args.port,
        log_level="info",
        reload=args.reload,
        # Event streams never end by themselves, and uvicorn otherwise waits
        # for every open response before it stops: a --reload would leave the
        # old worker waiting forever, accepting nothing.
        timeout_graceful_shutdown=3,
        reload_dirs=[str(src / "workbench"), str(src / "planlib")] if args.reload else None,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
