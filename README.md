# head_of_apache
Small repo that adds or updates the Apache v2 license header to source code files of your project

The code is mostly taken from the [IAM-CMS pre-commit-hooks project](https://gitlab.com/iam-cms/pre-commit-hooks). The major changes were that the license header is fuzzily matched, meaning that if the year changes, the license header will be updated inplace instead of being prepended to the previous header.


## Usage

The hook is intended to the following:

- Add the Apache 2.0 License header for the desired author and the current year to source code files that do not have the Apache 2.0 License header
- If there's an existing Apache 2.0 License header with another author, it keeps it while prepending a new License header under the desired author and the current year
- If there's an existing Apache 2.0 License header for the desired author but for a past year, it updates the License header year.
- Any special shebang or encoding opennings are left are they were found.

To run the pre-commit hook, you must pass the following configuration:

```yaml
repos:
  - repo: https://github.com/lucianopaz/head_of_apache
    rev: "0.0.5"
    hooks:
      - id: head_of_apache
        args:
          - --author
          - name of author
          - --exclude
          - excluded/directory_or_file
```

Using the `args` keyword, the default behaviour of the hook can be adapted. The following options exist:


-a/--author: The author to use in the license header.

-m/--mapping: Overwrite existing or add additional file types to the
default file/comment style mapping. For example, to use Jinja comment styles
in HTML files, the following mapping can be used: -m html jinja.

-x/--exclude: A path to exclude. A file will be excluded if it starts with
the given path. Can be specified more than once.
