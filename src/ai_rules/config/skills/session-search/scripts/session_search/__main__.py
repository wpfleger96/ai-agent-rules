"""CLI entry point for cross-agent session search."""

from __future__ import annotations

import argparse
import os
import re

from session_search.core import (
    matches_term,
    print_sessions,
    sorted_sessions,
    warn,
)
from session_search.readers import iter_all_sessions, search_sessions


def add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--agent",
        choices=["claude", "codex", "gemini", "goose", "amp"],
        help="Restrict to a single agent.",
    )
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Working directory used for repo bias.",
    )
    parser.add_argument(
        "--repo",
        help="Override detected repo name for ranking.",
    )
    parser.add_argument(
        "--all-repos",
        action="store_true",
        help="Disable same-repo ranking bias.",
    )
    parser.add_argument(
        "--since",
        help="Only include sessions on/after YYYY-MM-DD.",
    )
    parser.add_argument(
        "--until",
        help="Only include sessions on/before YYYY-MM-DD.",
    )
    parser.add_argument(
        "--oldest",
        action="store_true",
        help="Sort oldest first instead of newest first.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search session transcripts across coding agents."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list", help="List recent sessions, repo-biased by default."
    )
    add_common_flags(list_parser)
    list_parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Number of sessions to print; 0 means all.",
    )
    list_parser.add_argument("--json", action="store_true", help="Print JSON.")

    find_parser = subparsers.add_parser(
        "find",
        help="Find sessions by ID fragment, title, path, cwd, or repo.",
    )
    add_common_flags(find_parser)
    find_parser.add_argument(
        "term", nargs="?", default="", help="ID fragment or search phrase."
    )
    find_parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Number of sessions to print; 0 means all.",
    )
    find_parser.add_argument("--json", action="store_true", help="Print JSON.")

    grep_parser = subparsers.add_parser(
        "grep", help="Regex search across session transcripts."
    )
    add_common_flags(grep_parser)
    grep_parser.add_argument("pattern", help="Python regular expression to search for.")
    grep_parser.add_argument(
        "--id",
        help="Restrict search to sessions matching this ID fragment.",
    )
    grep_parser.add_argument(
        "--limit-sessions",
        type=int,
        default=25,
        help="Candidate sessions to search; 0 means all.",
    )
    grep_parser.add_argument(
        "--max-matches",
        type=int,
        default=40,
        help="Maximum matches to print; 0 means all.",
    )
    grep_parser.add_argument(
        "--ignore-case",
        "-i",
        action="store_true",
        help="Case-insensitive search.",
    )
    grep_parser.add_argument(
        "--width",
        type=int,
        default=280,
        help="Truncate rendered match lines to this width.",
    )

    return parser


def cmd_grep(args: argparse.Namespace) -> int:
    sessions = iter_all_sessions(args)
    if args.id:
        sessions = [s for s in sessions if matches_term(s, args.id)]
    ranked = sorted_sessions(sessions, args.oldest)
    if args.limit_sessions > 0:
        ranked = ranked[: args.limit_sessions]

    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        pattern = re.compile(args.pattern, flags)
    except re.error as exc:
        warn(f"invalid regex: {exc}")
        return 2

    match_count = search_sessions(ranked, pattern, args)

    if match_count == 0 and not args.all_repos and not args.id:
        searched = {s.id for s in ranked}
        from session_search.core import date_key

        fallback = [
            s
            for s in sorted(
                sessions,
                key=lambda s: date_key(s.sort_time),
                reverse=not args.oldest,
            )
            if s.id not in searched
        ]
        if args.limit_sessions > 0:
            fallback = fallback[: args.limit_sessions]
        if fallback:
            print("\nNo matches in top candidates; checking older sessions.")
            match_count = search_sessions(fallback, pattern, args)

    if match_count == 0:
        print("No matches.")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        sessions = iter_all_sessions(args)
        print_sessions(sorted_sessions(sessions, args.oldest), args.limit, args.json)
        return 0

    if args.command == "find":
        sessions = iter_all_sessions(args)
        hits = [s for s in sessions if not args.term or matches_term(s, args.term)]
        print_sessions(sorted_sessions(hits, args.oldest), args.limit, args.json)
        return 0 if hits else 1

    if args.command == "grep":
        return cmd_grep(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
