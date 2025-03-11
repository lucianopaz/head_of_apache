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
import os
import pathlib
import re
import tempfile
from unittest.mock import patch

import pytest

from head_of_apache.main import (
    COMMENT_STYLES,
    DESIRED_LICENSE_NOTICE,
    FILE_TYPE_MAPPING,
    LICENSE_LENGTH,
    _main,
    get_files,
    get_license_header,
    main,
    parse_license_years,
    read_file_header_lines,
    validate_file_header,
)

from . import utils
from .utils import (
    CURRENT_YEAR,
    GOOD_AUTHOR,
    bad_fnames,
    expected_headers,
    good_fnames,
)


@pytest.fixture(scope="function", params=["py", "c", "html"])
def file_extension(request):
    return request.param


@pytest.fixture()
def comment_style(file_extension):
    return COMMENT_STYLES[FILE_TYPE_MAPPING[file_extension]]


@pytest.fixture()
def file_structure(file_extension, comment_style):
    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = pathlib.Path(tempdir)
        for fname in good_fnames:
            with open(tempdir / f"{fname}.{file_extension}", "w") as f:
                content = getattr(utils, fname)(**comment_style)
                f.write(content)
        os.makedirs(tempdir / "bad_files", exist_ok=True)
        for fname in bad_fnames:
            with open(tempdir / "bad_files" / f"{fname}.{file_extension}", "w") as f:
                content = getattr(utils, fname)(**comment_style)
                f.write(content)
        yield tempdir


@pytest.fixture(params=["include_all", "exclude"])
def exclude(request):
    return "bad_files" if request.param == "exclude" else None


@pytest.fixture(params=[True, False])
def last_year_present(request):
    return request.param


@pytest.fixture(params=["dry_run", "real_run"])
def dry_run(request):
    return request.param == "dry_run"


@pytest.fixture(scope="function", params=["path", "multi-path", "empty"])
def cli_path(request):
    if request.param == "path":
        with tempfile.TemporaryDirectory() as dir1:
            yield [dir1]
    elif request.param == "multi-path":
        dir1 = tempfile.TemporaryDirectory()
        dir2 = tempfile.TemporaryDirectory()
        yield [dir1.name, dir2.name]
        dir1.cleanup()
        dir2.cleanup()
    else:
        yield []


@pytest.fixture(scope="function", params=[None, "1998"])
def start_year_override(request):
    return request.param


@pytest.fixture(scope="function", params=good_fnames + bad_fnames)
def single_file(request, file_extension, comment_style):
    fname = request.param
    with tempfile.TemporaryDirectory() as tempdir:
        path = pathlib.Path(tempdir) / f"{fname}.{file_extension}"
        with open(path, "w") as f:
            f.write(getattr(utils, fname)(**comment_style))
        yield (path, *expected_headers(fname, comment_style=comment_style))


def test_get_files(file_extension, file_structure, exclude):
    files = get_files(
        [file_structure], exclude=[file_structure / exclude] if exclude else None
    )
    expected = [file_structure / f"{fname}.{file_extension}" for fname in good_fnames]
    if not exclude:
        expected.extend(
            [
                file_structure / "bad_files" / f"{fname}.{file_extension}"
                for fname in bad_fnames
            ]
        )
    assert set(files) == set(expected)


def test_read_file_header_lines(single_file, comment_style):
    (path, expected_header, expected_first_line, expected_special_openning_lines) = (
        single_file
    )
    with open(path, "r") as file_obj:
        file_header, first_line, special_openning_lines = read_file_header_lines(
            file_obj, comment_style=comment_style, n_lines=LICENSE_LENGTH
        )
    assert file_header == expected_header
    assert first_line == expected_first_line
    assert special_openning_lines == expected_special_openning_lines


def test_main(single_file, comment_style, last_year_present, dry_run, capsys):
    path, *_ = single_file
    if dry_run:
        _main(
            paths=[path],
            author=GOOD_AUTHOR,
            mapping=[],
            exclude=None,
            dry_run=dry_run,
            last_year_present=last_year_present,
        )
    else:
        with capsys.disabled():
            _main(
                paths=[path],
                author=GOOD_AUTHOR,
                mapping=[],
                exclude=None,
                dry_run=dry_run,
                last_year_present=last_year_present,
            )
    if dry_run:
        no_headers = [
            "bad_file_no_author",
            "bad_file_bad_author",
            "bad_file_no_header",
            "bad_file_mit_header",
        ]
        must_change_license = [
            fname
            for fname in good_fnames + bad_fnames
            if not (
                (fname == "good_file_old_to_current_year" and not last_year_present)
                or (fname == "good_file_old_to_present" and last_year_present)
            )
            and fname not in no_headers
        ]
        captured = capsys.readouterr()
        if path.stem in no_headers:
            assert "No license header found" in captured.out
        elif path.stem in must_change_license:
            assert "Must update existing license header found in " in captured.out
    else:
        with capsys.disabled():
            with open(path, "r") as f:
                file_header, first_line, special_openning_lines = (
                    read_file_header_lines(
                        f, comment_style=comment_style, n_lines=LICENSE_LENGTH
                    )
                )
            (has_license_notice, must_update_license_notice, start_year, end_year) = (
                validate_file_header(
                    first_line=first_line,
                    current_year=CURRENT_YEAR,
                    author=GOOD_AUTHOR,
                    last_year_present=last_year_present,
                )
            )
            end_year = "present" if last_year_present else CURRENT_YEAR
            expected_license = get_license_header(
                author=GOOD_AUTHOR, year=f"{start_year} - {end_year}", **comment_style
            )
            assert (
                "\n".join([line.rstrip() for line in file_header]) == expected_license
            )
            assert has_license_notice
            assert not must_update_license_notice


def test_start_year_override(start_year_override):
    comment_style = COMMENT_STYLES[FILE_TYPE_MAPPING["py"]]
    file_content = utils.good_file_old_to_current_year(**comment_style)
    with tempfile.TemporaryDirectory() as tempdir:
        path = pathlib.Path(tempdir) / "foo.py"
        with open(path, "w") as f:
            f.write(file_content)
        _main(
            [path],
            author=GOOD_AUTHOR,
            mapping=None,
            exclude=[],
            dry_run=False,
            last_year_present=False,
            start_year_override=start_year_override,
        )
        with open(path, "r") as f:
            _, first_line, _ = read_file_header_lines(
                f, comment_style=comment_style, n_lines=LICENSE_LENGTH
            )
        if start_year_override is None:
            assert first_line.rstrip() == file_content.splitlines()[0]
        else:
            assert first_line.rstrip() != file_content.splitlines()[0]
            start_year, *_ = parse_license_years(
                re.search(DESIRED_LICENSE_NOTICE, first_line).group("years")
            )
            assert start_year == start_year_override


@patch("head_of_apache.main._main")
def test_cli(
    patched_main, cli_path, exclude, dry_run, last_year_present, start_year_override
):
    args_list = [f"--author {GOOD_AUTHOR}"]
    if exclude is not None:
        args_list.append(f"--exclude {exclude}")
        exclude = pathlib.Path(exclude)
    if dry_run:
        args_list.append("--dry-run")
    if last_year_present:
        args_list.append("--last-year-present")
    if len(cli_path) > 0:
        args_list.extend(cli_path)
        paths = [pathlib.Path(path) for path in cli_path]
    else:
        paths = [pathlib.Path(os.curdir)]
    if start_year_override is not None:
        args_list.append(f"--start-year {start_year_override}")
    args = (" ".join(args_list)).split()
    main(args)
    patched_main.assert_called_once_with(
        paths,
        GOOD_AUTHOR,
        None,
        [exclude] if exclude is not None else None,
        dry_run,
        last_year_present,
        start_year_override=start_year_override,
    )


def test_go_file(capsys):
    content = utils.good_file_old_to_current_year(**COMMENT_STYLES["asterisk"])
    with tempfile.TemporaryDirectory() as path:
        path = pathlib.Path(path)
        with open(path / "simple.go", "w") as f:
            f.write(content)
        _main(
            [path],
            author=GOOD_AUTHOR,
            mapping=[("go", "asterisk")],
            dry_run=True,
            exclude=None,
            last_year_present=False,
        )
        captured = capsys.readouterr()
        assert not captured.out
