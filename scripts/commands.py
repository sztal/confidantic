"""Pass Make variables to helpers as data rather than shell expressions."""

import argparse
import os

from scripts import distributions, merge, publish, release


def required(name: str) -> str:
    """Read a nonempty command argument exported by Make."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} when invoking this target")
    return value


def main() -> None:
    """Dispatch a Make target using validated environment arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "check-dist",
            "merge",
            "merge-check",
            "release",
            "release-notes",
            "publish",
        ),
    )
    command = parser.parse_args().command
    if command == "check-dist":
        distributions.main(
            ["check"] + (["--tag", os.environ["TAG"]] if os.environ.get("TAG") else [])
        )
    elif command in ("merge", "merge-check"):
        notes, reason = os.environ.get("NOTES"), os.environ.get("NO_NOTES_REASON")
        if bool(notes) == bool(reason):
            raise ValueError("Set exactly one of NOTES and NO_NOTES_REASON")
        args = [required("BRANCH")]
        args += (
            ["--notes", notes]
            if notes
            else ["--no-notes-reason", required("NO_NOTES_REASON")]
        )
        merge.main(args + (["--check"] if command == "merge-check" else []))
    elif command in ("release", "release-notes"):
        release.main(
            [required("VERSION")] + (["--notes"] if command == "release-notes" else [])
        )
    else:
        publish.main([required("TAG")])


if __name__ == "__main__":
    main()
