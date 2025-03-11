#   Copyright 2023 - present Luciano Paz
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# Copyright 2022 Karlsruhe Institute of Technology
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import glob
import itertools
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DESIRED_LICENSE_NOTICE = (
    r"Copyright (?P<years>\d{4}\s*-\s*\d{4}|\d{4}\s*-\s*present) (?P<author>[A-Za-z].*)"
)
SINGLE_DATE_LICENSE_NOTICE = (
    r"Copyright (?P<years>\d{4}\s*|\d{4}\s*-\s*) (?P<author>[A-Za-z].*)"
)
LICENSE = """{comment_start}Copyright {year} {author}
{comment_middle}
{comment_middle}Licensed under the Apache License, Version 2.0 (the "License");
{comment_middle}you may not use this file except in compliance with the License.
{comment_middle}You may obtain a copy of the License at
{comment_middle}
{comment_middle}    http://www.apache.org/licenses/LICENSE-2.0
{comment_middle}
{comment_middle}Unless required by applicable law or agreed to in writing, software
{comment_middle}distributed under the License is distributed on an "AS IS" BASIS,
{comment_middle}WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
{comment_middle}See the License for the specific language governing permissions and
{comment_middle}limitations under the License.{comment_end}"""
LICENSE_LENGTH = len(LICENSE.splitlines())


COMMENT_STYLES = {
    "asterisk": {
        "comment_start": "/* ",
        "comment_middle": " * ",
        "comment_end": " */",
    },
    "hash": {
        "comment_start": "#   ",
        "comment_middle": "#   ",
        "comment_end": "",
    },
    "html": {
        "comment_start": "<!-- ",
        "comment_middle": "   - ",
        "comment_end": " -->",
    },
    "jinja": {
        "comment_start": "{# ",
        "comment_middle": " # ",
        "comment_end": " #}",
    },
}


FILE_TYPE_MAPPING = {
    "c": "asterisk",
    "cpp": "asterisk",
    "css": "asterisk",
    "h": "asterisk",
    "hpp": "asterisk",
    "html": "html",
    "js": "asterisk",
    "py": "hash",
    "scss": "asterisk",
    "sh": "hash",
    "vue": "html",
}


def get_files(paths, exclude=None, file_type_mapping=None):
    # Extend the existing file type mapping, if applicable.
    file_type_mapping = file_type_mapping or FILE_TYPE_MAPPING

    # Process exclude directories
    exclude = [Path(path) for path in exclude] if exclude is not None else []

    # Collect all files to check for a license header.
    file_lists = []

    for path in paths:
        if os.path.isfile(path):
            file_lists.append([path])
        else:
            for file_type in file_type_mapping:
                file_lists.append(
                    glob.iglob(
                        os.path.join(path, "**", f"*.{file_type}"), recursive=True
                    )
                )

    def to_keep(path):
        is_in_excluded = any([ex == path or ex in path.parents for ex in exclude])
        return path.suffix[1:] in file_type_mapping and not is_in_excluded

    files = filter(
        to_keep,
        (
            Path(file)
            for file in itertools.chain(*file_lists)
            if not os.path.isdir(file)
        ),
    )
    return list(files)


def get_license_header(author, year, comment_start, comment_middle, comment_end):
    license_header = LICENSE.format(
        author=author,
        year=year,
        comment_start=comment_start,
        comment_middle=comment_middle,
        comment_end=comment_end,
    )
    temp = [line.rstrip() for line in license_header.splitlines()]
    license_header = "\n".join(temp)
    return license_header


def read_file_header_lines(f, comment_style, n_lines):
    # Check if the first lines are shebangs or encodings
    first_line = f.readline()
    special_opennings = {
        "shebanged": "#!",
        "encoded": "# -*- coding:",
    }
    special_openning_lines = {}
    matched_special_openning = True
    while matched_special_openning:
        matched_special_openning = False
        for key, openning in special_opennings.items():
            if key in special_openning_lines:
                continue
            if first_line.startswith(openning):
                matched_special_openning = True
                special_openning_lines[key] = first_line
                first_line = f.readline()

    file_header = [first_line] + [
        line if line.rstrip() else comment_style["comment_middle"] + "\n"
        for i, line in enumerate(f)
        if i + 1 < n_lines
    ]
    return file_header, first_line, special_openning_lines


def parse_license_years(years):
    # years string adheres to this format:
    # (?P<years>\d{4}\s*|\d{4}\s*-\s*|\d{4}\s*-\s*\d{4}|\d{4}\s*-\s*present)

    split_years = years.split("-")
    if len(split_years) == 1:
        # Only the starting year format
        start_year = split_years[0].strip()
        end_year = ""
        wrong_space_format = f"{start_year} " != split_years[0]
    else:
        assert len(split_years) == 2
        start_year = split_years[0].strip()
        end_year = split_years[1].strip()
        wrong_space_format = (
            f"{start_year} " != split_years[0] and f" {end_year}" != split_years[0]
        )
    return start_year, end_year, wrong_space_format


def validate_file_header(
    first_line,
    current_year,
    author,
    last_year_present,
    start_year_override=None,
):
    # Check whether license header is missing
    current_year = str(current_year)
    license_notice = re.search(DESIRED_LICENSE_NOTICE, first_line)
    if not license_notice:
        license_notice = re.search(SINGLE_DATE_LICENSE_NOTICE, first_line)
    if not license_notice:
        has_license_notice = False
        must_update_license_notice = True
        start_year = start_year_override or current_year
        end_year = current_year if not last_year_present else "present"
    elif license_notice.group("author") != author:
        # There is an existing license under a different author. We must leave it there
        # and prepend our own
        has_license_notice = False
        must_update_license_notice = True
        start_year = start_year_override or current_year
        end_year = current_year if not last_year_present else "present"
    else:
        has_license_notice = True
        start_year, end_year, wrong_space_format = parse_license_years(
            license_notice.group("years")
        )
        if (
            (end_year != current_year and not last_year_present)
            or (end_year != "present" and last_year_present)
            or (start_year_override is not None and start_year != start_year_override)
        ):
            # The existing license years need to be updated
            must_update_license_notice = True
            start_year = start_year_override or start_year
            end_year = current_year if not last_year_present else "present"
        else:
            must_update_license_notice = wrong_space_format
    return has_license_notice, must_update_license_notice, start_year, end_year


def _main(
    paths,
    author,
    mapping,
    exclude,
    dry_run,
    last_year_present,
    start_year_override=None,
):
    """Check for Apache 2.0 license headers in one or multiple files.

    The given paths can be either single files and/or directories that will be searched
    recursively for suitable file types to apply the header on.
    """
    if os.name == "nt":
        os.system("color")
    file_type_mappings = FILE_TYPE_MAPPING.copy()
    mapping = mapping or {}
    for file_type, style in mapping:
        file_type_mappings[file_type] = style

    files = get_files(paths, exclude, file_type_mappings)

    # Check for missing license headers.
    exit_status = 0
    for file in files:
        # Ignore files with non-matching extensions.
        file_type_mapping = file_type_mappings[file.suffix[1:]]
        comment_style = COMMENT_STYLES[file_type_mapping]

        # Check the file for an existing header.
        with open(file, mode="r+", encoding="utf-8") as f:
            # Create the fitting license header for the current file.
            current_year = f"{datetime.now(timezone.utc).year}"

            _, first_line, special_openning_lines = read_file_header_lines(
                f, comment_style, LICENSE_LENGTH
            )

            # Check whether license header is missing
            (has_license_notice, must_update_license_notice, start_year, end_year) = (
                validate_file_header(
                    first_line=first_line,
                    current_year=current_year,
                    author=author,
                    last_year_present=last_year_present,
                    start_year_override=start_year_override,
                )
            )

        if not has_license_notice or must_update_license_notice:
            exit_status = 1
            if dry_run:
                if not has_license_notice:
                    print(f"No license header found in '{file}'.", file=sys.stdout)
                else:
                    print(
                        f"Must update existing license header found in '{file}'.",
                        file=sys.stdout,
                    )
            else:
                license_header = get_license_header(
                    author, f"{start_year} - {end_year}", **comment_style
                )
                with open(file, encoding="utf-8") as f:
                    file_content = f.readlines()

                # Create a new file in the same directory with the header and file
                # content, then replace the existing one.
                tmp_file = tempfile.NamedTemporaryFile(
                    mode="w", dir=os.path.dirname(file), delete=False
                )

                try:
                    for special_openning_line in special_openning_lines.values():
                        tmp_file.write(special_openning_line)
                    tmp_file.write(license_header + "\n")
                    if has_license_notice:
                        tmp_file.write(
                            "".join(
                                file_content[
                                    len(license_header.split("\n"))
                                    + len(special_openning_lines) :
                                ]
                            )
                        )
                    else:
                        tmp_file.write("".join(file_content))

                    tmp_file.close()

                    # Copy the metadata of the original file, if supported.
                    shutil.copystat(file, tmp_file.name)
                    os.replace(tmp_file.name, file)

                    if not has_license_notice:
                        print(f"Applied license header to '{file}'.", file=sys.stdout)
                    else:
                        print(f"Updated license header in '{file}'.", file=sys.stdout)
                except Exception as e:  # pragma: no cover
                    print(
                        f"\033[91m{e}\033[0m", fg="red", file=sys.stdout
                    )  # pragma: no cover

                    try:  # pragma: no cover
                        os.remove(tmp_file.name)  # pragma: no cover
                    except FileNotFoundError:  # pragma: no cover
                        pass  # pragma: no cover
    return exit_status


parser = argparse.ArgumentParser(
    prog="head_of_apache",
    description=(
        "Add or update the Apache v2 license header to source code files in the "
        "desired path."
    ),
)
parser.add_argument(
    "-a",
    "--author",
    required=True,
    help="The author to use in the license header.",
)
parser.add_argument(
    "-m",
    "--mapping",
    nargs=2,
    action="append",
    help=(
        "Overwrite existing or add additional file types to the default file/comment"
        " style mapping. Possible comment styles are 'asterisk', 'hash', 'html' and "
        "'jinja'."
    ),
)
parser.add_argument(
    "-x",
    "--exclude",
    action="append",
    help=(
        "A path to exclude. A file will be excluded if it starts with the given path."
        " Can be specified more than once."
    ),
    type=Path,
)
parser.add_argument(
    "-d",
    "--dry-run",
    action="store_true",
    help="Notify about missing license headers, but do not apply them.",
)
parser.add_argument(
    "-l",
    "--last-year-present",
    action="store_true",
    help="If set, the license last year is set to 'present'.",
)
parser.add_argument(
    "paths",
    nargs="*",
    type=Path,
    help=(
        "Paths in which to look for source code files to apply the Apache license "
        "header. If none is provided, the current working directory is used."
    ),
)
parser.add_argument(
    "--start-year",
    type=int,
    default=None,
    help=(
        "If present, this year will overwrite the start year found in all matched "
        "scripts. If absent, the existing start year will be preserved, and if there "
        "is no start year present, the current year (the year at which head_of_apache "
        "was called) will be used in the license header."
    ),
)


def main(args=None):
    parsed_args = parser.parse_args(args)
    paths: list[Path] = parsed_args.paths
    if not paths:
        paths = [Path(os.curdir)]
    for path in paths:
        assert path.exists(), f"The supplied {path=} does not exist."
    author: str = parsed_args.author
    mapping: list[tuple] = parsed_args.mapping
    exclude: list[Path] = parsed_args.exclude
    dry_run: bool = parsed_args.dry_run
    last_year_present: bool = parsed_args.last_year_present
    if parsed_args.start_year is not None:
        start_year_override = str(parsed_args.start_year)
    else:
        start_year_override = None
    return _main(
        paths,
        author,
        mapping,
        exclude,
        dry_run,
        last_year_present,
        start_year_override=start_year_override,
    )


if __name__ == "__main__":
    exit_code = main()  # pragma: no cover
    sys.exit(exit_code)  # pragma: no cover
