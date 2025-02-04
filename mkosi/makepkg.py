import argparse
import os
from pathlib import Path
import sys
from typing import cast

import mkosi.resources
from mkosi import __version__
from mkosi.mounts import mount_tmpfs
from mkosi.log import log_setup
from mkosi.run import PathString, run, uncaught_exception_handler
from mkosi.sandbox import CLONE_NEWNS, acquire_privileges, unshare
from mkosi.util import resource_path


@uncaught_exception_handler()
def main() -> None:
    log_setup()

    parser = argparse.ArgumentParser(
        prog="mkosi-makepkg",
        usage="mkosi-makepkg [options...]",
        description="Build PKGBUILDs using makepkg and mkosi images",
        allow_abbrev=False,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"mkosi {__version__}",
    )
    parser.add_argument(
        "-C",
        "--directory",
        type=Path,
        default=Path.cwd(),
        metavar="DIR",
        help="Directory containing PKGBUILDs",
    )
    parser.add_argument(
        "-O",
        "--output-directory",
        type=Path,
        default=Path.cwd(),
        metavar="DIR",
        help="Package output directory",
    )
    parser.add_argument(
        "--build-directory",
        type=Path,
        metavar="DIR",
        help="Path to use as persistent build directory",
    )
    parser.add_argument(
        "--cache-directory",
        type=Path,
        metavar="DIR",
        help="Path to use as incremental cache directory",
    )
    parser.add_argument(
        "--tools-tree",
        type=Path,
        metavar="DIR",
        help="Path to use as tools tree",
    )

    args = parser.parse_args()

    with resource_path(mkosi.resources) as resources:
        directory = resources / "mkosi-makepkg"

        if os.getuid() != 0:
            acquire_privileges()

        unshare(CLONE_NEWNS)

        with mount_tmpfs(directory / "mkosi.images") as subimages:
            inputdir = cast(Path, args.directory)
            outputdir = cast(Path, args.output_directory)
            outputdir.mkdir(parents=True, exist_ok=True)

            (directory / "pkgbuild/mkosi.chroot").chmod(0o755)
            (directory / "pkgbuild/mkosi.configure").chmod(0o755)

            for pkgbuild in inputdir.glob("*/PKGBUILD"):
                os.symlink("../pkgbuild", subimages / pkgbuild.parent.name)

            cmdline: list[PathString] = [
                "mkosi",
                "--directory", directory,
                "--build-sources", f"{inputdir}:input",
                "--build-sources", f"{outputdir}:output",
                "--build-sources", f"{directory / 'srcinfo'}:srcinfo",
                "--environment", "PYTHONPATH=/work/src/srcinfo",
                "--pass-environment", "PYTHONPATH",
                "--package-directory", outputdir,
                "--format", "none",
                "--distribution", "arch",
            ]  # fmt: skip

            if args.build_directory:
                cmdline += ["--build-directory", args.build_directory]

            if args.cache_directory:
                cmdline += ["--cache-directory", args.cache_directory]
                cmdline += ["--incremental"]

            if args.tools_tree:
                cmdline += ["--tools-tree", args.tools_tree]

            run(
                cmdline,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )


if __name__ == "__main__":
    main()
