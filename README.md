<h1>AuTUMoodle</h1>

> stands for Auto - TUM - Moodle. I'm not that good at naming, I know...

## Quick Start

> [!WARNING]
>
> The instructions in this section are highly simplified (but still works in most cases).
> For more proper and robust usage, please refer to the [How to Use](#how-to-use) section and [Config](#config) section.

For Linux systems, run the following commands in a POSIX-compliant terminal (e.g. bash, zsh):

```sh
# Clone this repository
git clone https://github.com/Uyanide/AuTUMoodle.git --depth 1
cd AuTUMoodle

# Prepare virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
python3 -m pip install -r requirements-minimal.txt

# Prepare a minimal config file (change semester accordingly)
cat > config-minimal.json << EOF
{
  "courses": [
    {
      "pattern": ".*",
      "match_type": "regex",
      "semester": "WS25_26"
    }
  ]
}
EOF

# Good to go!
python3 -m autumoodle -c config-minimal.json
```

for Windows systems, run the following commands in PowerShell:

```ps1
# Clone this repository
git clone https://github.com/Uyanide/AuTUMoodle.git --depth 1
Set-Location AuTUMoodle

# Prepare virtual environment (optional but recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements-minimal.txt

# Prepare a minimal config file (change semester accordingly)
@"{
  "courses": [
    {
      "pattern": ".*",
      "match_type": "regex",
      "semester": "WS25_26"
    }
  ]
}"@ | Out-File -Encoding utf8 config-minimal.json

# Good to go!
python -m autumoodle -c config-minimal.json
```

This will download all courses in the specified semester (here: winter semester 2025/2026) to the default location (`~/Documents/AuTUMoodle` on Linux, `C:\Users\YourUsername\Documents\AuTUMoodle` on Windows), organizing the downloaded files into sub-directories based on the course titles and categories as defined in Moodle.

> [!NOTE]
>
> Prompts will appear to ask for your TUM Moodle credentials (username and password) after launching. If you don't want to enter them interactively every time, you can create a `credentials.json` file as explained in the [Config](#config) section.

## Contents

- [Quick Start](#quick-start)
- [Contents](#contents)
- [Features](#features)
- [How to Use](#how-to-use)
  - [Via Docker](#via-docker)
  - [Directly via Python](#directly-via-python)
- [CLI Arguments](#cli-arguments)
- [How This Works](#how-this-works)
- [Config](#config)
  - [config.json](#configjson)
  - [credentials.json](#credentialsjson)
- [Session Implementations](#session-implementations)
- [Pattern Matching](#pattern-matching)
- [Updating Methods](#updating-methods)

## Features

- Automatic authentication via TUM Shibboleth SSO.
- Download course materials from TUM Moodle's "Download Center".
- Configurable rules to select which courses, categories, entries to download.
- Configurable updating methods for existing files.
- Configurable organization of downloaded files.
- Summary report generation after each download session (as csv).
- Multiple session implementations (`requests` and `playwright`) to handle potential login issues.
- Asynchronous implementation for better performance.
- Docker support for easy deployment.
- Tested on both GNU/Linux and Windows systems.

## How to Use

> [!TIP]
>
> To set up a scheduled task, one may consider using `cron` on Linux systems or `Task Scheduler` on Windows systems. e.g. a `cron` job that runs every day at 2am (with Docker):
>
> ```sh
> 0 2 * * * docker start -a autumoodle
> ```

### Via Docker

1. Prerequisites:

   - [Docker](https://docs.docker.com/get-docker/)
   - git (or manually download the source code as a zip file and extract it)
   - (optional) [Docker Compose](https://docs.docker.com/compose/install/)

2. Clone this repository:

   ```sh
   git clone https://github.com/Uyanide/AuTUMoodle.git --depth 1
   ```

   or download the source code as a zip file from Github and extract to a local directory.

3. Prepare configuration files:

   When using Docker, only `config.json` is required, as credentials can be passed via environment variables. A minimal config file could look like:

   ```json
   {
     "destination_base": "/data",
     "cache_dir": "/cache",
     "courses": []
   }
   ```

   where the following entries should **NOT** be changed:

   - `destination_base`: `/data` (the directory inside the container where downloaded files will be saved to)
   - `cache_dir`: `/cache` (the directory inside the container where cached files will be stored)

   If you are planning to use the `playwright` session implementation (e.g. when the `requests` implementation fails to log in some day in the future), set:

   ```json
   {
     ...
     "session_type": "playwright",
     "playwright": {
       "headless": true
     },
     ...
   }
   ```

   Please also keep in mind that all the absolute paths in the config file should refer to paths inside the container (i.e. starting with `/data` or `/cache`), not paths on the host machine (e.g. `/home/ACoolGuy/Documents/Uni`).

   > For detailed information about the configuration file, please refer to the [Config](#config) section.

4. Run the Docker container:

- Using `docker run`:

  1. Build the Docker image:

     ```sh
     docker build \
       --build-arg PUID=$(id -u) \
       --build-arg PGID=$(id -g) \
       -t autumoodle:latest \
       /path/to/AuTUMoodle/repository
     ```

     > explained:
     >
     > - `PUID` and `PGID` build arguments are used to set the user and group id inside the container to match those of the host user, so that files created by the container will have the correct ownership on the host machine.
     > - `-t autumoodle:latest` tags the built image with the name `autumoodle` and tag `latest`.
     > - `/path/to/AuTUMoodle/repository` should be replaced with the actual path to the cloned/extracted AuTUMoodle repository on your machine.

  2. Run the container, mapping the configuration file and necessary directories, and passing in the credentials via environment variables:

     ```sh
     docker run \
       --name autumoodle \
       -v /path/to/local/config.json:/app/config.json:ro \
       -v /path/to/local/destination:/data \
       -v /path/to/local/cache:/cache \
       -e TUM_USERNAME="your_username" \
       -e TUM_PASSWORD="your_password" \
       autumoodle:latest
     ```

     > explained:
     >
     > - `--name autumoodle` names the container `autumoodle` for easier reference in subsequent runs.
     > - `-v /path/to/local/config.json:/app/config.json:ro` maps the local configuration file to the container's expected location, in read-only mode.
     > - `-v /path/to/local/destination:/data` maps the local directory where downloaded files will be saved to the container's `/data` directory. e.g. `/home/ACoolGuy/Documents/Uni`.
     > - `-v /path/to/local/cache:/cache` maps the local directory for cached files to the container's `/cache` directory. e.g. `/home/ACoolGuy/.cache/autumoodle`.
     > - `-e TUM_USERNAME="your_username"` and `-e TUM_PASSWORD="your_password"` set the TUM Moodle login credentials as environment variables inside the container.
     > - `autumoodle:latest` specifies the image to run.

     Additionally, a `--rm` flag can be added to automatically remove the container after running, but in this case `docker start` in step 3 can no longer be used for subsequent runs.

  3. Then each time you want to run the tool, execute:

     ```sh
     docker start -a autumoodle
     ```

     where the `-a` flag is used to attach the container's output to your terminal. Or

     ```sh
     docker run --rm ... # same as step 2
     ```

     case `--rm` flag is used.

- Using `docker-compose` (recommended):

  1. Create a `compose.yaml` or `docker-compose.yaml` file, for example:

     ```yaml
     name: autumoodle # project name, default to be the directory name

     services:
       autumoodle:
         build:
           context: /path/to/AuTUMoodle/repository
           args:
             PUID: ${PUID} # or replace with actual numeric value
             PGID: ${PGID} # or replace with actual numeric value
         container_name: autumoodle # container name
         volumes:
           - /path/to/local/config.json:/app/config.json:ro
           - /path/to/local/destination:/data
           - /path/to/local/cache:/cache
         environment: # or use env_file to load from .env
           - TUM_USERNAME=your_username
           - TUM_PASSWORD=your_password
     ```

     > A complete example can be found [here](https://github.com/Uyanide/AuTUMoodle/blob/master/docker/compose.yaml).

  2. Set the `PUID` and `PGID` environment variables in your shell:

     ```sh
     export PUID=$(id -u)
     export PGID=$(id -g)
     ```

     Or if you already know the exact user id and group id, you can directly replace `${PUID}` and `${PGID}` in the `compose.yaml` file with the actual numeric values.

  3. Build and run the container:

     ```sh
     docker compose up autumoodle
     ```

     > or
     >
     > ```sh
     > docker-compose up autumoodle
     > ```
     >
     > if you are using an older version of Docker.

     Additionally, a `-d` flag can be added to run the container in detached mode, `--build` flag to force rebuild the image (useful after editing source code).

  4. Then each time you want to run the tool, execute:

     ```sh
     docker start -a autumoodle
     ```

     where the `-a` flag is used to attach the container's output to your terminal.

### Directly via Python

1.  Prerequisites:

    - (optional) [uv](https://docs.astral.sh/uv/)
    - (required when not using `uv`) Python 3.12+
    - git (or manually download the source code as a zip file and extract it)

2.  Clone this repository:

    ```sh
    git clone https://github.com/Uyanide/AuTUMoodle.git --depth 1
    ```

    or download the source code as a zip file from Github and extract to a local directory.

3.  Prepare virtual environment (optional but recommended):

    - Using `uv` (recommended):

    ```sh
    uv venv .venv
    source .venv/bin/activate  # Or other commands depending on your OS and shell
    ```

    - Using `venv` (built-in Python module):

    ```sh
    python3 -m venv .venv
    source .venv/bin/activate  # Or other commands depending on your OS and shell
    ```

4.  Install dependencies:

    - Using `uv` (recommended):

    ```sh
    uv sync
    ```

    - Using `pip`:

    ```sh
    python3 -m pip install -r requirements.txt
    ```

    - or manually, depending on the session implementation you want to use:

      - for `requests` (better performance, but may break in the future):

      ```sh
      python3 -m pip install httpx beautifulsoup4
      ```

      - for `playwright` (more robust, but much heavier):

      ```sh
      python3 -m pip install playwright
      playwright install
      playwright install-deps
      ```

5.  Prepare the configuration files:

    > Please refer to the [Config](#config) section for details about the configuration files.

6.  Run the CLI tool:

    ```sh
    python3 -m autumoodle -c path/to/config.json -s path/to/credentials.json
    ```

## CLI Arguments

| Argument                     | Description                                                  |
| ---------------------------- | ------------------------------------------------------------ |
| -c CONFIG, --config CONFIG   | Path to the config file                                      |
| -s SECRET, --secret SECRET   | Path to the credential file                                  |
| -h, --help                   | Show help message and exit                                   |
| -r REGEX, --regex REGEX      | Match course title against the given regular expression...   |
| -t SUBSTR, --contains SUBSTR | Match course title that contains the given substring...      |
| -l STR, --literal STR        | Match course title that exactly matches the given literal... |

`-r/--regex`, `-t/--contains` and `-l/--literal` arguments can be given multiple times, which serve as additional filters for courses to download from, in addition to those defined in the configuration file. Only the courses matching at least **one of** the courses defined in the configuration file **and** at least **one of** the additional filters provided here (if any) will be processed. The order of these additional filters matters, as they are evaluated in the same order as they are provided in the command line.

If none is provided, all courses defined in the configuration file will be processed (same effect as a single `--regex ".*"`).

e.g.

```sh
python -m autumoodle -c config.json -s credentials.json -r "^Analysis" -t "IN0009"
```

will select courses using config.json, and only download from courses whose title starts with "Analysis" **or** contains "IN0009".

> [!NOTE]
>
> When using `docker-compose` or `docker run`, these additional filters can be passed via the `command` field/argument, e.g.:
>
> ```yaml
> services:
>   autumoodle:
>     ...
>     command: ["-r", "^Analysis", "-t", "IN0009"]
>     ...
> ```
>
> or
>
> ```sh
> docker run ... autumoodle:latest -r "^Analysis" -t "IN0009"
> ```

## How This Works

1. Login ~~(which is so far the most tricky part)~~.
2. Find out which course(s) to download from.
3. Fetch "Download Center" page of each course.
4. Parse the page and find all categories and entries.
5. Download as a ZIP archive (using Moodle's built-in ZIP download feature).
6. Extract files from the ZIP archive to the right place.

Based on this procedure, rules defined in the configuration file primarily target four levels:

| Level    | Takes effect in steps | Example target                           |
| -------- | --------------------- | ---------------------------------------- |
| course   | 2                     | Analysis I (WS25_26)                     |
| category | 4, 6                  | Vorlesungen, Übungen                     |
| entry    | 4, 6                  | Folien 01, Hausaufgabe 1                 |
| file     | 6                     | Folien 01.pdf, Hausaufgabe 1/sheet_1.pdf |

> [!NOTE]
>
> `entry` refers to the items displayed under each category, which not necessarily represents an actual file (e.g. it can be a folder containing multiple files, or a link to an external resource, etc.).

## Config

Configurations are passed via two (or one) `json` files:

- `config.json`: contains general configurations such as what to download, where to save, etc.
- (optional) `credentials.json`: contains login credentials, i.e. username and password.

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
> or be entered interactively when running the CLI tool in an interactive terminal. However, a `credentials.json` file is generally recommended for ease of use.

### config.json

A minimal example could look like:

```json
{
  "courses": [
    {
      "pattern": ".*",
      "match_type": "regex",
      "semester": "WS25_26"
    }
  ]
}
```

which will download all courses in the winter semester 2025/2026, save them to the default location (`~/Documents/AuTUMoodle`), and organize the downloaded files into sub-directories based on the course titles and categories as defined in Moodle.

> Complete examples can be found [here](https://github.com/Uyanide/AuTUMoodle/blob/master/config.json) (for Linux), [here](https://github.com/Uyanide/AuTUMoodle/blob/master/config-win.json) (for Windows) and [here](https://github.com/Uyanide/AuTUMoodle/blob/master/config-docker.json) (for Docker).

Detailed explanation of each field:

- `"$schema": "https://raw.githubusercontent.com/Uyanide/AuTUMoodle/master/schema/config.schema.json"` (optional but **highly recommended**)

  URL to the JSON schema for this configuration file. This is useful when using editors that support JSON schema validation (e.g. VSCode) to provide auto-completion and validation of the config file.

- `destination_base` (optional, default: `~/Documents/AuTUMoodle`)

  the base directory where all downloaded course materials will be saved to. Each course will get its own sub-directory inside this base directory by default.

- `courses` (optional, but nothing will be download if not provided)

  a list of json objects, each representing a course to download from. ONLY the courses configured here will be processed.

  - `pattern` and `match_type` (required)

    matches the title of the course. See [pattern matching](#pattern-matching) for how this works.

  - `semester` (required)

    the semester of the course, e.g. WS_25/26, SS_26.

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

    - `pattern` and `match_type` (required)

      matches the title of the category. See [pattern matching](#pattern-matching) for how this works.

    - `destination` (optional)

      the directory where the materials in this category will be saved to. Case a relative path, it is relative to the course's `destination_base`.

      If not provided, the category title will be used as the sub-directory name inside the course's `destination_base`.

    - `update` (optional)

      if not provided, the course's `update` method will be used. See [updating methods](#updating-methods) for details.

  - `config.rules.entries`

    a list of json objects, each representing a rule to match entries in the course. Each rule has the following fields:

    - `pattern` and `match_type` (required)

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

    - `pattern` and `match_type` (required)

      matches the basename with extension of the file. See [pattern matching](#pattern-matching) for how this works.

    - `directory` (optional)

      the directory where this file will be saved to. Case a relative path, it is relative to the course's `destination_base`.

      If not provided, the file will be saved in the default location, i.e. determined by the course/category/entry rules.

    - `update` (optional)

      if not provided, the course's `update` method will be used. See [updating methods](#updating-methods) for details.

    - `ignore` (optional, default: `false`)

      if set to `true`, files that matches this rule will be ignored.

> [!NOTE]
>
> You might have noticed that there are two different words describing paths: `destination` and `directory`, which may seem a bit confusing at first. The difference is that `destination` specifies the exact path where the target object should be saved **as**, while `directory` specifies the parent directory where the target object should be saved **to**. The former is used for categories, while the latter is used for entries and files.

- `ignored_files` (optional)

  a list of json objects, each representing a rule to match files that should be ignored globally (i.e. for all courses). Each rule has the following fields:

  - `pattern` and `match_type` (required)

    matches the basename with extension of the file. See [pattern matching](#pattern-matching) for how this works.

> [!NOTE]
>
> Rules in this field have the highest priority, and will be applied to **actual files** rather than entries displayed in the "Download Center" page.

> [!TIP]
>
> This is useful when ignoring html files that are automatically generated by Moodle for certain types of entries (such as intro.html).

- `log_level` (optional, default: `INFO`)

  the log level. Possible values are: `DEBUG`, `INFO`, `WARNING`, `ERROR`.

- `cache_dir` (optional, default: `~/.cache/autumoodle`)

  the directory where cached files will be stored.

> [!TIP]
>
> Temporary files will be stored in the system's temporary directory such as `/tmp` on Linux systems and `%TEMP%` on Windows systems. To clear the temporary files that have not been deleted properly (such as after ctrl+c), run:
>
> ```sh
> rm -rf /tmp/autumoodle_*
> ```
>
> on Linux systems, or:
>
> ```ps1
> Remove-Item -Recurse -Force $env:TEMP\autumoodle_*
> ```
>
> on Windows systems (in powershell).

- `session_type` (optional, default: `requests`)

  implementation of the session to use when logging and retrieving files from Moodle. Possible values are:

  - `requests`
  - `playwright`

  Please refer to the [Session Implementations](#session-implementations) section for details.

- `playwright` (optional, only used when `session_type` is `playwright`)

  additional configurations for the Playwright session.

  - `browser` (optional, default: `chromium`)

    the browser to use. Please refer to the [Playwright documentation](https://playwright.dev/python/docs/browsers) for details.

  - `headless` (optional, default: `true`)

    if set to `true`, the browser will run in headless mode.

- `session` (optional)

  additional configurations for the session manager, works for both `requests` and `playwright` session implementations.

  - `save` (optional, default: `false`)

    if set to `true`, the session cookies will be saved to a file.

  - `save_path` (optional, default: `${cache_dir}/session.dat`)

    the path to the file where the session cookies will be saved to.

- `summary` (optional)

  configurations for the summary report generation feature.

  - `enabled` (optional, default: `false`)

    if set to `true`, a summary report will be generated after each download session.

  - `path` (optional, default: `${destination_base}/summaries`)

    the directory where the summary reports will be saved to.

  - `expire_days` (optional, default: `7`)

    the number of days after which old summary reports will be deleted.

### credentials.json

> An example for my account can be found [here](https://www.youtube.com/watch?v=dQw4w9WgXcQ).

- `username` (required)

  your TUM username, e.g. ab12cde.

- `password` (required)

  your TUM password, e.g. nevergonnagiveyouup123.

## Session Implementations

- `requests`: based on the [httpx](https://www.python-httpx.org/) library to make HTTP requests. Lightweight, fast, but may soon break if the procedure of Shibboleth SSO login used by TUM Moodle changes some day (like many other similar tools out there).

- `playwright`: based on the [Playwright](https://playwright.dev/) library to automate browser interactions. Although it can be used to bypass the complicated (manual) Shibboleth SSO logins, it remains to be a rather "heavy" solution since this literally runs a browser (firefox by default) in the background.

Both implementations are using asynchronous APIs, so the performance difference in practice may not be that significant taking the network latency into account.

> [!IMPORTANT]
>
> Please make sure to download the corresponding browser binaries by running `playwright install [browser_name]` and `playwright install-deps [browser_name]` in your terminal after installing the `playwright` package if you are planning to use the `playwright` session implementation.
>
> This is automatically handled by the [entrypoint script](https://github.com/Uyanide/AuTUMoodle/blob/master/entry.sh) case you are using the Docker image provided in this repository.

## Pattern Matching

- `match_type` can be one of the following:

  - `literal`: exact string match, e.g. `"file.pdf"`
  - `regex`: regular expression match, e.g. `".*\.pdf$"`
  - `contains`: substring match, e.g. `"file"`

- `pattern` is the string or regular expression to match against.

> [!IMPORTANT]
>
> - All matches are case-sensitive (unless specified in `regex` pattern).
> - Please also take the unpredictable sanitization of paths by Moodle into account. (e.g. how could `In der Klausur bereitgestellte Referenzmaterialien (falls benötigt)` become `In der Klausur bereitgestellte ___nzmaterialien (falls benötigt)`?)

## Updating Methods

When a file to be downloaded already exists in the destination directory, and the file is determined to be updated (i.e. the update date of the file from moodle is newer than the local one), the following methods can be used to handle the situation:

- `skip`: do not download the file again, keep the existing one.
- `overwrite`: overwrite the existing file with the new one.
- `rename`: download the new file and rename it by appending numbered suffixes, e.g. `file.pdf` -> `file_1.pdf`, `file_2.pdf`, etc.

> [!NOTE]
>
> If not configured otherwise, the default method is always `rename`.
