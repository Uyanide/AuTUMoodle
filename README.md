# AuTUMoodle

> stands for Auto - TUM - Moodle. I'm not that good at naming, I know...

## Config

Configurations are passed via two `json` files:

- `config.json`: contains general configurations such as from what to download, where to save, etc.
- `credentials.json`: contains login credentials, i.e. username and password.

> [!IMPORTANT]
>
> Both files can have whatever name you like and be placed wherever you want, as long as the correct paths are provided when running the CLI tool via the `-c/--config` and `-s/--secret` arguments respectively.

> [!NOTE]
>
> Instead of using a separate `credentials.json` file, the credentials can also be passed via environment variables:
>
> - `TUM_USERNAME`: your TUM username
> - `TUM_PASSWORD`: your TUM password
>
> or be entered interactively when running the CLI tool in a interactive terminal. However, a `credentials.json` file is generally recommended for ease of use.

---

### config.json

> [!NOTE]
>
> an example can be found in the root directory of this repository.

- `destination_base`

    **ESSENTIAL**, the base directory where all downloaded course materials will be saved to. Each course will get its own sub-directory inside this base directory by default.

-  `courses`

    a list of json objects, each representing a course to download from. ONLY the courses configured here will be processed.

    - `pattern` and `match_type` (essential)

        matches the title of the course. See [pattern matching](#pattern-matching) for how this works.

    - `semester` (essential)

        the semester of the course, e.g. WS25_26, SS26, etc.

    - `destination_base` (optional)

        the base directory where this specific course's materials will be saved to. Case a relative path, it is relative to the global `destination_base`.

        If not provided, the global `destination_base` with a sub-directory named after the course title will be used.


    - `update` (optional, default: `rename`)

        determines how updated files are handled when there are already older versions of the same file existing in the destination directory. See [Updating Methods](#updating-methods) for details.

    - `config_type` (optional, default: `category_auto`)

        determines how the course materials are organized in the destination directory. There are currently four options:

        - `category_auto`

            materials are organized into sub-directories based on their categories as defined in Moodle (e.g. Vorlesungen, Übungen, etc.). This is done automatically.

        - `category_manual`

            only the categories that matches one of the rules in the `config.rules.categories` will be processed, and the materials that matches one of the rules in `config.rules.files` will be specifically processed.

        - `file_auto`

            all materials are placed directly in the `destination_base` directory.

        - `file_manual`

            only the files that matches one of the rules in `config.rules.files` will be processed.

    - `config` (optional based on `config_type`)

        additional configuration based on the selected `config_type`.

        - for `category_auto` and `file_auto`, this field is ignored.
        - for `files_manual`, only `rules.files` is considered.
        - for `category_manual`, both `rules.categories` and `rules.files` are considered.

    - `config.rules.categories`

        a list of json objects, each representing a rule to match categories in the course. Each rule has the following fields:

        - `pattern` and `match_type` (essential)

            matches the title of the category. See [pattern matching](#pattern-matching) for how this works.

        - `destination` (optional)

            the directory where the materials in this category will be saved to. Case a relative path, it is relative to the course's `destination_base`.

            If not provided, the category title will be used as the sub-directory name inside the course's `destination_base`.

        - `update` (optional)

            if not provided, the course's `update` method will be used. See [Updating Methods](#updating-methods) for details.

    - `config.rules.files`

        a list of json objects, each representing a rule to match files in the course. Each rule has the following fields:

        - `pattern` and `match_type` (essential)

            matches the title of the file. See [pattern matching](#pattern-matching) for how this works.

        - `ignore` (optional, default: `false`)

            if set to `true`, files that matches this rule will be ignored.

        - `directory` (optional)

            the directory where this file will be saved to. Case a relative path, it is relative to the course's `destination_base`.

            If not provided, the file will be saved directly in the course's `destination_base` if in `file_manual` mode, or in the corresponding category directory if in `category_manual` mode.

        - `update` (optional)

            if not provided, the course's `update` method will be used. See [Updating Methods](#updating-methods) for details.


- `log_level` (optional, default: `INFO`)

    the log level of the CLI tool. Possible values are: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

- `cache_dir` (optional, default: `~/.cache/autumoodle`)

    the directory where cached files will be stored.

- `session_type` (optional, default: `requests`)

    implementation of the session manager to use when logging and retrieving files from Moodle. Possible values are:

    - `requests`: uses the [httpx](https://www.python-httpx.org/) library to make HTTP requests. Lightweight, fast, but may soon not work if the procedure of Shibboleth SSO login used by TUM Moodle changes some day (like many other similar tools out there).

    - `playwright`: uses the [Playwright](https://playwright.dev/) library to automate browser interactions. Although it can be used to bypass the complicated (manual) Shibboleth SSO logins, it remains to be a rather "heavy" and "slow" solution since this literally runs a browser (firefox by default) in the background.

    Both implementations are using asynchronous APIs under the hood, so the performance difference in practice may not be that significant.


- `playwright` (optional, only used when `session_type` is `playwright`)

    additional configurations for the Playwright session manager.

    - `browser` (optional, default: `firefox`)

        the browser to use. Possible values are: `chromium`, `firefox`.


    - `headless` (optional, default: `true`)

        if set to `true`, the browser will run in headless mode.

> [!NOTE]
>
> Please make sure to download the corresponding browser binaries by running `playwright install` in your terminal after installing the `playwright` package.

- `session` (optional)

    additional configurations for the session manager.

    - `save` (optional, default: `false`)

        if set to `true`, the session cookies will be saved to a file.

    - `save_path` (optional, default: `${cache_dir}/session.dat`)

        the path to the file where the session cookies will be saved to.

---

### credentials.json

- `username` (essential)

    your TUM username.

- `password` (essential)

    your TUM password.




## Pattern Matching

- `match_type` can be one of the following:

    - `literal`: exact string match
    - `regex`: regular expression match

- `pattern` is the string or regular expression to match against.

> [!NOTE]
>
> For `contains` mode, please use the `regex` mode with `pattern` set to `.*<your_substring>.*` or `<your_substring>` to achieve the same effect.


## Updating Methods

When a file to be downloaded already exists in the destination directory, and the file is determined to be updated (i.e. the update date of the file from moodle is newer than the local one), the following methods can be used to handle the situation:

- `skip`: do not download the file again, keep the existing one.
- `overwrite`: overwrite the existing file with the new one.
- `rename`: download the new file and rename it by appending numbered suffixes, e.g. `file.pdf` -> `file_1.pdf`, `file_2.pdf`, etc.