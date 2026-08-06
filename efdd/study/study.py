import argparse
import os
import sys
from pathlib import Path

import sflkit.logger
import tests4py.logger

from utils.analyze import get_analysis
from utils.check import check
from utils.events import get_events
from utils.interpret import interpret
from utils.evaluate import evaluate
from utils.stats import stats, get_avg_features, locs_to_features
from utils.summarize import summarize


def parse_args(*args: str):
    arg_parser = argparse.ArgumentParser()
    commands = arg_parser.add_subparsers(
        title="command",
        description="The framework allows for the execution of various commands.",
        help="the command to execute",
        dest="command",
        required=True,
    )

    interpret_parser = commands.add_parser(
        "interpret",
        description="The interpretation command interprets the results of the study.",
        help="execute the interpretation of the study results",
    )
    interpret_parser.add_argument(
        "-t", default=False, action="store_true", dest="tex", help="generate tex tables"
    )
    interpret_parser.add_argument(
        "-n", default=5, type=int, dest="n", help="top n for plots"
    )
    interpret_parser.add_argument(
        "-p",
        default=None,
        dest="plots",
        help="generate plots for the provided metrics",
        nargs="+",
    )

    check_parser = commands.add_parser(
        "check",
        description="The check command checks if all subjects work.",
        help="execute a check of the subjects",
    )
    check_parser.add_argument(
        "--dir", default=None, dest="directory", help="the directory to check"
    )

    summarize_parser = commands.add_parser(
        "summarize",
        description="The summarize command summarizes the results of the study.",
        help="execute the summarization of the study results",
    )

    analyze_parser = commands.add_parser(
        "analyze",
        description="The analyze command analyzes the projects by deriving the analysis objects for the projects.",
        help="execute the analysis of the projects",
    )

    events_parser = commands.add_parser(
        "events",
        description="The events command generates the events for the projects.",
        help="execute the generation of the events for the projects",
    )

    metrics_parser = commands.add_parser(
        "evaluate",
        description="The metrics command calculates the metrics for the projects.",
        help="execute the calculation of the metrics for the projects",
    )

    stats_parser = commands.add_parser(
        "stats",
        description="The stats command computes statistics about the projects.",
        help="execute the computation of statistics about the projects",
    )

    avg_features_parser = commands.add_parser(
        "avg_features",
        description="The avg_features command computes average features about the projects.",
        help="execute the computation of average features about the projects",
    )

    locs_to_features_parser = commands.add_parser(
        "locs_to_features",
        description="The locs_to_features command generates a plot of lines of code to features.",
        help="execute the generation of a plot of lines of code to features",
    )

    for parser in (analyze_parser, events_parser, metrics_parser):
        parser.add_argument(
            "-p", required=True, dest="project_name", help="project name"
        )
        parser.add_argument("-i", default=None, type=int, dest="bug_id", help="bug id")
        parser.add_argument(
            "-s", default=None, type=int, dest="start", help="start bug id (inclusive)"
        )
        parser.add_argument(
            "-e", default=None, type=int, dest="end", help="end bug id (inclusive)"
        )

    for parser in (
        analyze_parser,
        events_parser,
        metrics_parser,
        check_parser,
        interpret_parser,
        summarize_parser,
        stats_parser,
        avg_features_parser,
        locs_to_features_parser,
    ):
        parser.add_argument(
            "-q",
            action="store_true",
            dest="quite",
            default=False,
            help="the quite flag to deactivate t4p and sflkit logger information",
        )
        parser.add_argument(
            "-d",
            action="store_true",
            dest="debug",
            default=False,
            help="the debug flag to activate debug information",
        )

    return arg_parser.parse_args(args or sys.argv[1:])


def main(*args: str, stdout=sys.stdout, stderr=sys.stderr):
    if stdout is not None:
        sys.stdout = stdout
    if stderr is not None:
        sys.stderr = stderr
    args = parse_args(*args)
    if args.quite:
        sflkit.logger.LOGGER.setLevel("ERROR")
        tests4py.logger.LOGGER.setLevel("ERROR")
    elif args.debug:
        sflkit.logger.LOGGER.setLevel("DEBUG")
        tests4py.logger.LOGGER.setLevel("DEBUG")
    if args.command == "interpret":
        interpret(args.tex, args.plots, args.n)
    elif args.command == "check":
        check(args.directory)
    elif args.command == "summarize":
        summarize()
    elif args.command == "analyze":
        get_analysis(args.project_name, args.bug_id, args.start, args.end)
    elif args.command == "events":
        get_events(args.project_name, args.bug_id, args.start, args.end)
    elif args.command == "evaluate":
        evaluate(args.project_name, args.bug_id, args.start, args.end)
    elif args.command == "stats":
        stats()
    elif args.command == "avg_features":
        get_avg_features()
    elif args.command == "locs_to_features":
        locs_to_features()
    else:
        raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    assert Path.cwd() == Path(__file__).parent
    if "-O" in sys.argv:
        sys.argv.remove("-O")
        os.execl(sys.executable, sys.executable, "-O", *sys.argv)
    else:
        main()
