# AuTUMoodle

> stands for Auto - TUM - Moodle. I'm not that good at naming, I know...

## How to Use

0.  Prerequisites:

    - [uv](https://docs.astral.sh/uv/) (or Python 3.12+ and pip)
    - git (or manually download the source code as a zip file and extract it)

1.  Clone this repository:

    ```sh
    git clone https://github.com/Uyanide/AuTUMoodle.git --depth 1
    ```

    or download the source code as a zip file from Github and extract to a local directory.

2.  Prepare virtual environment (optional but recommended):

    - Using `uv` (recommanded):

    ```sh
    uv venv .venv
    source .venv/bin/activate  # Or other commands depending on your OS and shell
    ```

    - Using `venv` (built-in Python module):

    ```sh
    python -m venv .venv
    source .venv/bin/activate  # Or other commands depending on your OS and shell
    ```

3.  Install dependencies:

    - Using `uv` (recommanded):

    ```sh
    uv sync
    ```

    - Using `pip`:

    ```sh
    pip install -r requirements.txt
    ```

    - or manually:

      - for logs:

      ```sh
      pip install loguru
      ```

      and depending on the session manager implementation you want to use:

      - for `requests` session manager (better performance, but may break in the future):

      ```sh
      pip install httpx beautifulsoup4
      ```

      - for `playwright` session manager (more robust, but much heavier):

      ```sh
      pip install playwright
      playwright install
      ```

4.  Prepare the configuration files:

    > see [Config](#config) for details.

5.  Run the CLI tool:

    ```sh
    python -m autumoodle -c path/to/config.json -s path/to/credentials.json
    ```

## How this works

1. Find out which course(s) to download from.
2. Fetch "Download Center" page of each course.
3. Parse the page and find all categories and entries.
4. Download as a ZIP archive (using Moodle's built-in ZIP download feature).
5. Extract files from the ZIP archive to the right place.

Based on this procedure, rules defined in the configuration file primarily target four levels:

- **course**, e.g. Analysis I (WS25_26)
- **category**, e.g. Vorlesungen, Übungen, etc.
- **entry**, e.g. Folien 01, Hausaufgabe 1, etc.
- **file**, e.g. Folien 01.pdf, Hausaufgabe 1/some/subdirectories/sheet_1.pdf etc.

## Config

Configurations are passed via two `json` files:

- `config.json`: contains general configurations such as what to download, where to save, etc.
- `credentials.json`: contains login credentials, i.e. username and password.

These two files can have whatever name you like and be placed wherever you want, as long as the correct paths are provided via the `-c/--config` and `-s/--secret` arguments when running the CLI tool.

> [!IMPORTANT]
>
> Both files should be encoded in UTF-8 to avoid potential issues with special characters. This is especially important for Windows systems.

> [!NOTE]
>
> Instead of using a separate `credentials.json` file, the credentials can also be passed via environment variables:
>
> - `TUM_USERNAME`: your TUM username, e.g. ab12cde
> - `TUM_PASSWORD`: your TUM password, e.g. nevergonnagiveyouup123
>
> or be entered interactively when running the CLI tool in a interactive terminal. However, a `credentials.json` file is generally recommended for ease of use.

### config.json

> [!NOTE]
>
> Examples can be found [here](https://github.com/Uyanide/AuTUMoodle/blob/master/config.json)(for Linux) and [here](https://github.com/Uyanide/AuTUMoodle/blob/master/config-win.json)(for Windows).

- `destination_base` (optional, default: `~/Documents/AuTUMoodle`)

  the base directory where all downloaded course materials will be saved to. Each course will get its own sub-directory inside this base directory by default.

- `courses` (optional, but nothing will be download if not provided)

  a list of json objects, each representing a course to download from. ONLY the courses configured here will be processed.

  - `pattern` and `match_type` (essential)

    matches the title of the course. See [pattern matching](#pattern-matching) for how this works.

  - `semester` (essential)

    the semester of the course, e.g. WS25_26, SS26, etc.

  - `destination_base` (optional)

    the base directory where this specific course's materials will be saved to. Case a relative path, it is relative to the global `destination_base`.

    If not provided, the global `destination_base` with a sub-directory named after the course title will be used.

  - `update` (optional, default: `rename`)

    determines how updated files are handled when there are already older versions of the same file existing in the destination directory. See [updating methods](#updating-methods) for details.

  - `config_type` (optional, default: `category_auto`)

    determines how the course materials are organized in the destination directory. There are currently four options:

    - `category_auto`

      entries are organized into sub-directories based on their categories as defined in Moodle (e.g. Vorlesungen, Übungen, etc.). This is done automatically.

    - `category_manual`

      only the categories that matches one of the rules in the `config.rules.categories` will be processed, and the entries that matches one of the rules in `config.rules.entries` will be specifically processed.

    - `entry_auto`

      all entries are placed directly in the `destination_base` directory.

    - `entry_manual`

      only the entries that matches one of the rules in `config.rules.entries` will be processed.

  - `config` (optional)

    additional configuration based on the selected `config_type`.

    - for `category_auto` and `entry_auto`, only `rules.files` is considered.
    - for `entry_manual`, `rules.entries` and `rules.files` are considered.
    - for `category_manual`, all `rules.categories`, `rules.entries` and `rules.files` are considered.

  - `config.rules.categories`

    a list of json objects, each representing a rule to match categories in the course. Each rule has the following fields:

    - `pattern` and `match_type` (essential)

      matches the title of the category. See [pattern matching](#pattern-matching) for how this works.

    - `destination` (optional)

      the directory where the materials in this category will be saved to. Case a relative path, it is relative to the course's `destination_base`.

      If not provided, the category title will be used as the sub-directory name inside the course's `destination_base`.

    - `update` (optional)

      if not provided, the course's `update` method will be used. See [updating methods](#updating-methods) for details.

  - `config.rules.entries`

    a list of json objects, each representing a rule to match entries in the course. Each rule has the following fields:

    - `pattern` and `match_type` (essential)

      matches the title of the entry. See [pattern matching](#pattern-matching) for how this works.

    - `ignore` (optional, default: `false`)

      if set to `true`, entries that matches this rule will be ignored.

    - `directory` (optional)

      the directory where this entry will be saved to. Case a relative path, it is relative to the course's `destination_base`.

      If not provided, the entry will be saved directly in the course's `destination_base` if in `entry_manual` mode, or in the corresponding category directory if in `category_manual` mode.

    - `update` (optional)

      if not provided, the course's `update` method will be used. See [updating methods](#updating-methods) for details.

  - `config.rules.files`

    a list of json objects, each representing a rule to match **actual downloaded files** in the course. The matching processes will only take place after the files are downloaded and parsed from the ZIP archive, and will have the highest priority. Each rule has the following fields:

    - `pattern` and `match_type` (essential)

      matches the basename with extension of the file. See [pattern matching](#pattern-matching) for how this works.

    - `directory` (optional)

      the directory where this file will be saved to. Case a relative path, it is relative to the course's `destination_base`.

      If not provided, the file will be saved in the default location, i.e. determined by the course/category/entry rules.

    - `update` (optional)

      if not provided, the course's `update` method will be used. See [updating methods](#updating-methods) for details.

    - `ignore` (optional, default: `false`)

      if set to `true`, files that matches this rule will be ignored.

- `ignored_files` (optional)

  a list of json objects, each representing a rule to match files that should be ignored globally (i.e. for all courses). Each rule has the following fields:

  - `pattern` and `match_type` (essential)

    matches the basename with extension of the file. See [pattern matching](#pattern-matching) for how this works.

> [!TIP]
>
> This is useful when ignoring html files that are automatically generated by Moodle for certain types of entries (such as intro.html).

> [!IMPORTANT]
>
> Rules in this field have the highest priority, and will be applied to **actual files** rather than entries displayed in the "Download Center" page.

- `log_level` (optional, default: `INFO`)

  the log level of the CLI tool. Possible values are: `DEBUG`, `INFO`, `WARNING`, `ERROR`.

- `cache_dir` (optional, default: `~/.cache/autumoodle`)

  the directory where cached files will be stored.

> [!TIP]
>
> Temporary files will be stored in the system's temporary directory such as `/tmp` on Linux systems and `%TEMP%` on Windows systems. To clear the temporary files that have not been deleted properly (such as after ctrl+c), run:
> ```sh
> rm -rf /tmp/autumoodle_*
> ```
> on Linux systems, or:
> ```ps1
> Remove-Item -Recurse -Force $env:TEMP\autumoodle_*
> ```
> on Windows systems (in powershell).

- `session_type` (optional, default: `requests`)

  implementation of the session manager to use when logging and retrieving files from Moodle. Possible values are:

  - `requests`: uses the [httpx](https://www.python-httpx.org/) library to make HTTP requests. Lightweight, fast, but may soon break if the procedure of Shibboleth SSO login used by TUM Moodle changes some day (like many other similar tools out there).

  - `playwright`: uses the [Playwright](https://playwright.dev/) library to automate browser interactions. Although it can be used to bypass the complicated (manual) Shibboleth SSO logins, it remains to be a rather "heavy" solution since this literally runs a browser (firefox by default) in the background.

  Both implementations are using asynchronous APIs under the hood, so the performance difference in practice may not be that significant.

> [!NOTE]
>
> Please make sure to download the corresponding browser binaries by running `playwright install` in your terminal after installing the `playwright` package if you are planning to use the `playwright` session implementation.

- `playwright` (optional, only used when `session_type` is `playwright`)

  additional configurations for the Playwright session manager.

  - `browser` (optional, default: `firefox`)

    the browser to use. Possible values are: `chromium`, `firefox`.

  - `headless` (optional, default: `true`)

    if set to `true`, the browser will run in headless mode.

- `session` (optional)

  additional configurations for the session manager, works for both `requests` and `playwright` session types.

  - `save` (optional, default: `false`)

    if set to `true`, the session cookies will be saved to a file.

  - `save_path` (optional, default: `${cache_dir}/session.dat`)

    the path to the file where the session cookies will be saved to.

### credentials.json

> [!NOTE]
>
> An example from myself can be found [here](https://www.youtube.com/watch?v=dQw4w9WgXcQ) :)

- `username` (essential)

  your TUM username, e.g. ab12cde.

- `password` (essential)

  your TUM password, e.g. nevergonnagiveyouup123.

## Pattern Matching

- `match_type` can be one of the following:

  - `literal`: exact string match
  - `regex`: regular expression match
  - `contains`: substring match

- `pattern` is the string or regular expression to match against.

## Updating Methods

When a file to be downloaded already exists in the destination directory, and the file is determined to be updated (i.e. the update date of the file from moodle is newer than the local one), the following methods can be used to handle the situation:

- `skip`: do not download the file again, keep the existing one.
- `overwrite`: overwrite the existing file with the new one.
- `rename`: download the new file and rename it by appending numbered suffixes, e.g. `file.pdf` -> `file_1.pdf`, `file_2.pdf`, etc.
