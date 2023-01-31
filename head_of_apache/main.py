# Copyright 2023 Luciano Paz
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
import glob
import itertools
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import click
from thefuzz import fuzz

LICENSE_NOTICE = r"Copyright ([0-9]{4}|[0-9]{4}-|[0-9]{4}-[0-9]{4}) (?P<author>.+)"
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


def _main(paths, author, mapping, exclude, dry_run):
    """Check for Apache 2.0 license headers in one or multiple files.

    The given paths can be either single files and/or directories that will be searched
    recursively for suitable file types to apply the header on.
    """
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
            license_header = LICENSE.format(
                author=author,
                year=datetime.now(timezone.utc).year,
                comment_start=comment_style["comment_start"],
                comment_middle=comment_style["comment_middle"],
                comment_end=comment_style["comment_end"],
            )
            temp = [line.rstrip() for line in license_header.split("\n")]
            n_lines = len(temp)
            license_header = "\n".join(temp)

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

            # Check whether license header is missing
            license_notice = re.search(LICENSE_NOTICE, first_line)
            if not license_notice:
                has_license_notice = False
                must_update_license_notice = True
            elif license_notice.group("author") != author:
                # There is an existing license under a different author. We must leave it there
                # and prepend our own
                has_license_notice = False
                must_update_license_notice = True
            else:
                ratios = [
                    fuzz.ratio(file_line.rstrip(), license_line)
                    for file_line, license_line in itertools.zip_longest(
                        file_header, license_header.split("\n"), fillvalue="\n"
                    )
                ]
                if all(ratio == 100 for ratio in ratios):
                    has_license_notice = True
                    must_update_license_notice = False
                elif all(ratio > 92 for ratio in ratios):
                    has_license_notice = True
                    must_update_license_notice = True
                else:
                    has_license_notice = False
                    must_update_license_notice = True

        if not has_license_notice or must_update_license_notice:
            exit_status = 1
            if dry_run:
                if not has_license_notice:
                    click.echo(f"No license header found in '{file}'.")
                else:
                    click.echo(
                        f"Must update existing license header found in '{file}'."
                    )
            else:
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
                    os.rename(tmp_file.name, file)

                    if not has_license_notice:
                        click.echo(f"Applied license header to '{file}'.")
                    else:
                        click.echo(f"Updated license header in '{file}'.")
                except Exception as e:
                    click.secho(str(e), fg="red")

                    try:
                        os.remove(tmp_file.name)
                    except FileNotFoundError:
                        pass
    return exit_status


@click.command()
@click.argument("paths", type=click.Path(exists=True), nargs=-1)
@click.option(
    "-a",
    "--author",
    required=True,
    help="The author to use in the license header.",
)
@click.option(
    "-m",
    "--mapping",
    nargs=2,
    multiple=True,
    help="Overwrite existing or add additional file types to the default file/comment"
    " style mapping.",
)
@click.option(
    "-x",
    "--exclude",
    multiple=True,
    help="A path to exclude. A file will be excluded if it starts with the given path."
    " Can be specified more than once.",
)
@click.option(
    "-d",
    "--dry-run",
    is_flag=True,
    help="Notify about missing license headers, but do not apply them.",
)
def main(paths, author, mapping, exclude, dry_run):
    return _main(paths, author, mapping, exclude, dry_run)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
