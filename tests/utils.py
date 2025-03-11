#   Copyright 2025 - present Luciano Paz
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
import pathlib
import sys
from datetime import datetime, timezone
from functools import partial

from head_of_apache.main import LICENSE

GOOD_AUTHOR = "person"
BAD_AUTHOR = "god"
CURRENT_YEAR = datetime.now(timezone.utc).year


def render_file_contents(
    year,
    author,
    comment_start,
    comment_middle,
    comment_end,
    has_license,
):
    header = LICENSE.format(
        year=year or "",
        author=author or "",
        comment_start=comment_start,
        comment_middle=comment_middle,
        comment_end=comment_end,
    )
    content = ""
    if has_license:
        content += header
    content += "\nNo comments!\n"
    return content


good_file_current_year = partial(
    render_file_contents,
    year=CURRENT_YEAR,
    author=GOOD_AUTHOR,
    has_license=True,
)
good_file_old_to_current_year = partial(
    render_file_contents,
    year=f"2023 - {CURRENT_YEAR}",
    author=GOOD_AUTHOR,
    has_license=True,
)
good_file_old_to_none_year = partial(
    render_file_contents,
    year="2023 -",
    author=GOOD_AUTHOR,
    has_license=True,
)
good_file_old_to_present = partial(
    render_file_contents,
    year="2023 - present",
    author=GOOD_AUTHOR,
    has_license=True,
)
good_file_old_year = partial(
    render_file_contents,
    year="2023",
    author=GOOD_AUTHOR,
    has_license=True,
)


bad_file_closing_old_year = partial(
    render_file_contents,
    year="1999-2001",
    author=GOOD_AUTHOR,
    has_license=True,
)
bad_file_old_to_current_year_bad_space = partial(
    render_file_contents,
    year=f"2023-{CURRENT_YEAR}",
    author=GOOD_AUTHOR,
    has_license=True,
)
bad_file_no_author = partial(
    render_file_contents,
    year="2023",
    author=None,
    has_license=True,
)
bad_file_bad_author = partial(
    render_file_contents,
    year="2023",
    author=BAD_AUTHOR,
    has_license=True,
)
bad_file_no_header = partial(
    render_file_contents,
    year=None,
    author=None,
    has_license=False,
)


def bad_file_mit_header(comment_start, comment_middle, comment_end):
    mit_license = """{comment_start}MIT License
{comment_middle}
{comment_middle}Copyright (c) 325-1453 {author}
{comment_middle}
{comment_middle}Permission is hereby granted, free of charge, to any person obtaining a copy
{comment_middle}of this software and associated documentation files (the "Software"), to deal
{comment_middle}in the Software without restriction, including without limitation the rights
{comment_middle}to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
{comment_middle}copies of the Software, and to permit persons to whom the Software is
{comment_middle}furnished to do so, subject to the following conditions:
{comment_middle}
{comment_middle}The above copyright notice and this permission notice shall be included in all
{comment_middle}copies or substantial portions of the Software.
{comment_middle}
{comment_middle}THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
{comment_middle}IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
{comment_middle}FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
{comment_middle}AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
{comment_middle}LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
{comment_middle}OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
{comment_middle}SOFTWARE.
{comment_end}"""
    return mit_license.format(
        comment_start=comment_start,
        comment_middle=comment_middle,
        comment_end=comment_end,
        author=BAD_AUTHOR,
    )


def good_file_with_special_opening(comment_start, comment_middle, comment_end):
    content = good_file_current_year(
        comment_start=comment_start,
        comment_middle=comment_middle,
        comment_end=comment_end,
    )
    if comment_start.startswith("#"):
        content = "#!/bin/python\n# -*- coding: utf-8\n" + content
    return content


good_fnames = [
    "good_file_current_year",
    "good_file_old_to_current_year",
    "good_file_old_to_none_year",
    "good_file_old_to_present",
    "good_file_old_year",
    "good_file_with_special_opening",
]
bad_fnames = [
    "bad_file_closing_old_year",
    "bad_file_no_author",
    "bad_file_bad_author",
    "bad_file_no_header",
    "bad_file_mit_header",
    "bad_file_old_to_current_year_bad_space",
]


def expected_headers(name, comment_style):
    path = pathlib.Path(name)
    content_creator = path.stem
    content_creator_function = getattr(sys.modules[__name__], content_creator)
    n_lines = len(LICENSE.splitlines())
    offset = 0
    content = content_creator_function(**comment_style)
    if (
        comment_style["comment_start"].startswith("#")
        and content_creator == "good_file_with_special_opening"
    ):
        offset = 2
        special_openning_lines = {
            "shebanged": "#!/bin/python\n",
            "encoded": "# -*- coding: utf-8\n",
        }
    else:
        special_openning_lines = {}
    content_lines = content.splitlines()
    header = [line + "\n" for line in content_lines[offset : n_lines + offset]]
    first_line = content_lines[offset] + "\n"
    return header, first_line, special_openning_lines
