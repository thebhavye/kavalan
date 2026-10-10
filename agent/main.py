"""CLI entrypoint — TEXT mode first (voice stubs raise NotImplementedError)."""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from agent.agent import KavalanAgent
from agent.armoriq_adapter import ArmoriqNotConfiguredError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kavalan voice guardian (TEXT mode)")
    parser.add_argument("--user-email", default=os.environ.get("KAVALAN_USER_EMAIL", ""),
                        help="end-user email for ArmorIQ policy attribution")
    parser.add_argument("--once", default=None,
                        help="process one line of text and exit")
    parser.add_argument("--resume-held", type=int, default=None,
                        help="resume a held action id after family approval")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    if not args.user_email:
        print("Set KAVALAN_USER_EMAIL in .env or pass --user-email.", file=sys.stderr)
        return 2
    agent = KavalanAgent()
    try:
        if args.resume_held is not None:
            print(agent.resume_held(args.resume_held, args.user_email))
            return 0
        if args.once is not None:
            print(agent.process_text(args.once, args.user_email))
            return 0
        print("Kavalan (TEXT mode). Type a request, Ctrl+C to quit.")
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye.")
                return 0
            if text:
                print(agent.process_text(text, args.user_email))
    except ArmoriqNotConfiguredError as exc:
        print(f"ArmorIQ is required and not configured: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
