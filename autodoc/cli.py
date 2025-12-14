"""
AutoDoc Command-Line Interface

This module provides the CLI entry point for AutoDoc. It orchestrates the
full pipeline: discovery -> extraction -> rendering -> output.

Usage:
    autodoc /path/to/repository
    autodoc /path/to/repository --output README.md
    autodoc /path/to/repository --dry-run
    autodoc /path/to/repository --verbose --badges

Design Principles:
    1. Sensible defaults: Works out-of-the-box for common cases
    2. Transparency: Shows what's happening with --verbose
    3. Safety: --dry-run allows preview without file changes
    4. Flexibility: Options for badges, TOC, output location
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from autodoc import __version__
from autodoc.discovery import discover_files
from autodoc.extractors import ExtractorRegistry, GenericExtractor, PythonExtractor
from autodoc.renderer import RenderOptions, render_readme


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="autodoc",
        description=(
            "AutoDoc: Automatic README generation through metadata extraction.\n\n"
            "Analyzes a repository's files to extract metadata and generates "
            "a structured README.md draft for human review and refinement."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  autodoc .                      # Generate README for current directory\n"
            "  autodoc /path/to/repo          # Generate README for specified path\n"
            "  autodoc . --dry-run            # Preview without writing file\n"
            "  autodoc . --output docs/README.md  # Custom output path\n"
            "  autodoc . --no-badges --no-toc # Exclude badges and table of contents\n"
            "\n"
            "Note: AutoDoc generates a DRAFT README. Human review is essential.\n"
            "The generated file includes TODO comments for missing information.\n"
        ),
    )

    # Positional argument: repository path
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Path to the repository to analyze (default: current directory)",
    )

    # Output options
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output file path (default: README.md in repository root)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated README to stdout instead of writing to file",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing README without prompting",
    )

    # Content options
    parser.add_argument(
        "--no-badges",
        action="store_true",
        help="Exclude shields.io badges (license, Python version)",
    )

    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Exclude the table of contents",
    )

    parser.add_argument(
        "--no-notice",
        action="store_true",
        help="Omit the auto-generation notice at the end",
    )

    parser.add_argument(
        "--provenance",
        action="store_true",
        help="Include HTML comments showing data sources (for debugging)",
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress information",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )

    # Version
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def log(message: str, verbose: bool = False, quiet: bool = False) -> None:
    """
    Print a message to stderr (for progress/status).

    Args:
        message: The message to print
        verbose: If True, only print if verbose mode is enabled
        quiet: If True, suppress the message
    """
    if quiet:
        return
    if verbose:
        print(f"[autodoc] {message}", file=sys.stderr)
    else:
        print(f"[autodoc] {message}", file=sys.stderr)


def log_verbose(message: str, verbose: bool, quiet: bool) -> None:
    """Print a message only in verbose mode."""
    if verbose and not quiet:
        print(f"  {message}", file=sys.stderr)


def run_pipeline(
    repo_path: Path,
    output_path: Optional[Path],
    options: RenderOptions,
    dry_run: bool = False,
    force: bool = False,
    verbose: bool = False,
    quiet: bool = False,
) -> int:
    """
    Run the full AutoDoc pipeline.

    Args:
        repo_path: Path to the repository to analyze
        output_path: Where to write the README (None = repo_path/README.md)
        options: Rendering options
        dry_run: If True, print to stdout instead of writing
        force: If True, overwrite existing file without prompting
        verbose: If True, show detailed progress
        quiet: If True, suppress non-error output

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Validate repository path
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}", file=sys.stderr)
        return 1

    if not repo_path.is_dir():
        print(f"Error: Path is not a directory: {repo_path}", file=sys.stderr)
        return 1

    # Determine output path
    if output_path is None:
        output_path = repo_path / "README.md"

    # Check for existing file (unless dry-run or force)
    if not dry_run and output_path.exists() and not force:
        print(f"Error: File already exists: {output_path}", file=sys.stderr)
        print("Use --force to overwrite or --dry-run to preview.", file=sys.stderr)
        return 1

    # Step 1: File Discovery
    if not quiet:
        log("Discovering files...", quiet=quiet)

    try:
        discovery_result = discover_files(repo_path)
    except Exception as e:
        print(f"Error during file discovery: {e}", file=sys.stderr)
        return 1

    log_verbose(f"Found {discovery_result.total_file_count} files", verbose, quiet)

    if discovery_result.exceeded_limit:
        log("Warning: Repository exceeds recommended size (500 files)", quiet=quiet)

    # Show category breakdown in verbose mode
    if verbose and not quiet:
        counts = discovery_result.get_category_counts()
        for category, count in sorted(counts.items(), key=lambda x: -x[1]):
            log_verbose(f"  {category.name}: {count}", verbose, quiet)

    # Step 2: Metadata Extraction
    if not quiet:
        log("Extracting metadata...", quiet=quiet)

    registry = ExtractorRegistry()
    registry.register(GenericExtractor())   # Generic fallback (runs first, lower confidence)
    registry.register(PythonExtractor())    # Python-specific (higher confidence)
    # Future: registry.register(JavaScriptExtractor())

    try:
        metadata = registry.extract_all(discovery_result, repo_path)
    except Exception as e:
        print(f"Error during metadata extraction: {e}", file=sys.stderr)
        return 1

    # Report what was found
    if verbose and not quiet:
        if metadata.name.value:
            log_verbose(f"Project name: {metadata.name.value}", verbose, quiet)
        if metadata.version.value:
            log_verbose(f"Version: {metadata.version.value}", verbose, quiet)
        if metadata.license.value:
            log_verbose(f"License: {metadata.license.value}", verbose, quiet)
        log_verbose(f"Dependencies: {len(metadata.dependencies)}", verbose, quiet)
        log_verbose(f"Dev dependencies: {len(metadata.dev_dependencies)}", verbose, quiet)
        log_verbose(f"Entry points: {len(metadata.entry_points)}", verbose, quiet)

    # Report placeholders
    placeholders = metadata.get_placeholder_fields()
    if placeholders and not quiet:
        log(f"Missing fields (will be placeholders): {', '.join(placeholders)}", quiet=quiet)

    # Report warnings
    if metadata.extraction_warnings:
        for warning in metadata.extraction_warnings:
            if not quiet:
                log(f"Warning: {warning}", quiet=quiet)

    # Step 3: Render README
    if not quiet:
        log("Rendering README...", quiet=quiet)

    try:
        readme_content = render_readme(metadata, options)
    except Exception as e:
        print(f"Error during rendering: {e}", file=sys.stderr)
        return 1

    # Step 4: Output
    if dry_run:
        # Print to stdout
        print(readme_content)
        if not quiet:
            log("(Dry run - no file written)", quiet=quiet)
    else:
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(readme_content)

            if not quiet:
                log(f"README written to: {output_path}", quiet=quiet)

        except IOError as e:
            print(f"Error writing file: {e}", file=sys.stderr)
            return 1

    # Final message
    if not quiet and not dry_run:
        log("Done! Please review and edit the generated README.", quiet=quiet)

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Convert path to Path object
    repo_path = Path(args.path).resolve()

    # Determine output path
    output_path = None
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = repo_path / output_path

    # Build render options
    # Note: badges and toc default to True, CLI flags can disable them
    render_options = RenderOptions(
        include_badges=not args.no_badges,
        include_toc=not args.no_toc,
        include_generation_notice=not args.no_notice,
        include_provenance=args.provenance,
    )

    # Run the pipeline
    return run_pipeline(
        repo_path=repo_path,
        output_path=output_path,
        options=render_options,
        dry_run=args.dry_run,
        force=args.force,
        verbose=args.verbose,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    sys.exit(main())
