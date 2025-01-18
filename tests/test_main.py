import pytest
import tempfile
import pathlib
import os

from head_of_apache.main import (
    get_files,
    get_license_header,
    read_file_header_lines,
    validate_file_header,
    _main,
    COMMENT_STYLES,
    FILE_TYPE_MAPPING,
    LICENSE_LENGTH,
)
from . import utils
from .utils import (
    GOOD_AUTHOR,
    CURRENT_YEAR,
    expected_headers,
    good_fnames,
    bad_fnames,
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


def test_main(single_file, comment_style, last_year_present):
    path, *_ = single_file
    _main(
        paths=[path],
        author=GOOD_AUTHOR,
        mapping=[],
        exclude=None,
        dry_run=False,
        last_year_present=last_year_present,
    )
    with open(path, "r") as f:
        file_header, first_line, special_openning_lines = read_file_header_lines(
            f, comment_style=comment_style, n_lines=LICENSE_LENGTH
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
    assert "\n".join([line.rstrip() for line in file_header]) == expected_license
    assert has_license_notice
    assert not must_update_license_notice
