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

    from .app import create_app
    from .config import Config, ConfigError

    try:
        config = Config.from_env()
    except ConfigError as exc:
        print(f"workbench: {exc}", file=sys.stderr)
        return 2
    uvicorn.run(create_app(config), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
