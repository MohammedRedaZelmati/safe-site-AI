import argparse
import asyncio
import selectors

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SafeSite agent with a Psycopg-compatible Windows event loop.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = uvicorn.Config("app.main:app", host=args.host, port=args.port, loop="none")
    server = uvicorn.Server(config)
    with asyncio.Runner(
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
    ) as runner:
        runner.run(server.serve())


if __name__ == "__main__":
    main()
