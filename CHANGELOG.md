# Changelog

## v1.17.2 - 2025-08-01

Maintenance release, no functional changes. At least not from my side. I do note
the API has changed on Bitvavo's side, but I'll need to cover that soon enough.

### Added

- `copilot-instructions.md`

### Changed

- `structlog` v25 can now be used
- fixed `coverage` reporting
  - it broke; don't know why; solution was to add `coverage combine` to
    `tox.ini`

## v1.17.1 - 2024-12-24

Turns out the settings weren't working as expected, so I switched
`python-decouple` out from `pydantic-settings`, which (once setup) works a lot
smoother. Keywords being "once setup", because holy smokes is it a paint to do
the initial setup - figure out how the hell you need to validate values before
or after, etc.

Just don't forget to create a local `.env` with `BITVAVO_APIKEY` and
`BITVAVO_APISECRET` keys.

### Added

- `pydantic-settings`: a powerful and modern way of loading your settings.
  - we're using `.env` here, but it can be setup for `.json` or `.yaml` -
    whatever you fancy.
  - because of `pydantic-settings` you can now also do
    `Bitvavo(bitvavo_settings.model_dump())`, and import bitvavo_settings from
    `settings.py`
- add pydantic plugin for mypy, so mypy stops complaining about pydantic.
- vscode settings to disable `pytest-cov` during debugging. If you do not
  disable `pytest-cov` during debugging, it still silently break your debugging
  system...
- you can now import BitvavoApiUpgradedSettings and BitvavoSettings directly
  from `bitvavo_api_upgraded`

### Changed

- `python-decouple` replaced by `pydantic-settings` - see Added and Removed
- `pytest-cov` relegated to enable coverage via vscode - friendship with
  `pytest-cov` ended. `coverage.py` is my best friend.
  - reason for this is because `pytest-cov` fucked with the ability to debug
    within vscode.
- bump minor Python versions

### Removed

- `python-decouple` - this lacked type hinting since forever, not to mention it
  didn't throw errors if missing...

### Fixed

- a bunch of tests that have VERY flaky output from the API >:(

## v1.17.0 - 2024-11-24

Integrate all changes from Bitvavo's `v1.1.1` to `v1.4.2` lib versions,
basically catching up their changes with our code. The reason for choosing
`v1.1.1` as starting point, is because I'm not sure if I missed anything,
because if I follow the timeline on PyPI is that I should pick `v1.2.2`, but if
I look at my commit history, I should choose an older point. Oh well, it's only
a little bit more work.

I used [this Github
link](https://github.com/bitvavo/python-bitvavo-api/compare/v1.1.1...v1.4.2) to
compare their versions.

### Added

- `fees()` call. This was added to the Python SDK in early 2024.
- `_default(value, fallback)` function, which ensures a `fallback` is returned,
  if `value` is `None`. This ensures sane values will always be available.
- `strintdict` type, as I had a bunch of `dict` types copied.

### Changed

- you can now do `from bitvavo_api_upgraded import Bitvavo`, instead of `from
  bitvavo_api_upgraded.bitvavo import Bitvavo`, which always felt annoying. You
  can still use the old way; no worries.
- lowercased the http headers like `Bitvavo-Ratelimit-Remaining`, because
  Bitvavo updated the API, which broke this code. This should probably fix the
  issues of older versions of this lib going over the rate limit. 😅
- `LICENSE.txt`'s year got updated
- in `README.md`, below my text, I've replaced their old README with their
  current one.
- fixed coverage report; I switched to `pytest-cov`, from `coverage.py`
  eventhough `pytest-cov` still uses `coverage.py`, but the output was messed up
  (it also covered `tests/`, wich was unintentional)

### Unchanged

Normally I don't add this chapter, but I'm moving changes from Bitvavo's repo to
here, so it's good I'll track this stuff for later.

- I did NOT add the `name` var to `__init__.py`, because I'm pretty sure they
  added it for their build process, but since I'm using `uv` I don't need that.
- Did not add `self.timeout`, as I use `self.ACCESSWINDOW / 1000` instead.

## v1.16.0 - 2024-11-18

Quite a few changes, most aimed at the maintenance of this project, but all
changes are superficial - the functional code has not changed.

### Added

- `ruff`, which replaces `auotflake`, `black`, `flake8`, `isort`, and `pyupgrade`, in both `pyproject.toml` and
  `.pre-commit-config.yaml`
- `from __future__ import annotations`, so I can already use `|` instead of
  `Union`
- `py.typed` to enable mypy support for people who use this lib :)
- `wrap_public_request` to `conftest.py`, so I can more easily fix tests, if a market like `BABYDOGE-EUR` returns broken
  data (missing fields, `None` values, etc)

### Changed

- replaced `pip` with `uv`; I've become a big fan, since I don't have to handle the Python version anymore
  - [uv installation](https://docs.astral.sh/uv/getting-started/installation/) - do prefer the `curl` installation so
    you can `uv self update` and not need to touch your system's Python installation at all!
  - Just `uv sync` to setup the `.venv`, and then `uv run tox` to run tox, or `uv run black` to run black, etc.
- updated dependencies in `pyproject.toml`, and `.pre-commit-config.yaml`
- because we're dropping Python 3.7 and 3.8 support, we can finally use lowercase `list` and `dict`
- fixed a bunch of tests (disabled one with errorCode 400), due to minor API
  changes.
- formatting using `ruff`
- replace the unmaintained `bump2version` with `bump-my-version`

### Removed

- support for Python `3.7`, `3.8`; both EOL since last update
- `check-manifest` (used for `MANIFEST.in`)
- `rich`, as it would force its use on my users, and that's a no-no, as it's WAY
  too verbose. >:(

## v1.15.8 - 2022-03-13

### Changed

- also iso format

## v1.15.7 - 2022-03-13

### Changed

- add currentTime to napping-until-reset log

## v1.15.6 - 2022-03-13

### Changed

- add buffer time to sleep()

## v1.15.5 - 2022-03-13

### Changed

- format targetDatetime

## v1.15.4 - 2022-03-13

### Changed

- same as last one, except also for private calls

## v1.15.3 - 2022-03-13

### Changed

- add targetDatetime to napping-until-reset info log

## v1.15.2 - 2022-03-13

### Changed

- fix not being able to override settings variables

## v1.15.1 - 2022-03-13

### Changed

- fix the rateLimit check for private calls (this was a bug that let you get banned when making too many calls)

## v1.15.0 - 2022-02-09

### Changed

- fix the callback functions, again
- internal `Bitvavo.websocket` is now `Bitvavo.WebSocketAppFacade` (which is a better, more descriptive, name)
- internal `receiveThread` class is now `ReceiveThread`

### Removed

- bug that broke the code, lmao

## v1.14.1 - 2022-02-09

### Changed

- fixed the websocket's callback functions

## v1.14.0 - 2022-02-06

Make `upgraded_bitvavo_api` multi-processing friendly! :D

### Added

- add chapted to PyPI to shortly explain how to change settings for this lib.
- add `BITVAVO_API_UPGRADED_RATE_LIMITING_BUFFER` variable. Default value `25`; Change this to 50 or higher _only_ when
  you keep getting banned, because you're running more than one `Bitvavo` object. If you're only running one `Bitvavo`
  objects, you're probably fine.

## v1.13.2 - 2022-02-06

### Changed

- fixed a bug where I subtracted where I should've added, making 304 errors more likely 😅

## v1.13.1 - 2022-01-29

### Changed

- You will now be informed that you have been temporary banned, even if you did NOT enable the `DEBUGGING` var during
  creation of the `Bitvavo` object. Such a stupid design, originally.

## v1.13.0 - 2022-01-23

### Changed

- fixed the API timeout (which did nothing, client-side), by adding a timeout to the actual API call. If `ACCESSWINDOW`
  is now set (when creating `Bitvavo`) to `2000` ms, it will time-out after `2000` ms, and not wait the full `30_000` ms
  anyway.

## v1.12.0 - 2022-01-21

### Added

- A trigger to nap `Bitvavo` when `rateLimitRemaining` is about run empty, until `rateLimitResetAt` has elapsed and
  `rateLimitRemaining` has reset, after which the API call will continue as normal. ONLY WORKS FOR NORMAL CALLS -
  WEBSOCKET NOT (yet?) SUPPORTED!

## v1.11.5 - 2022-01-19

A `.env` file is just a text file with "equal-separated" key-value pairs. No spaces around the `=` symbol!

### Added

- `calcLag()` to `Bitvavo`, which returns the time difference between the server's clock and your local clock. Set the
  variable 1 line down to the value that comes out of this function :)
- `BITVAVO_API_UPGRADED_LAG=50` option for your `.env` file, to reduce the amount of `304 "Request was not received
within acceptable window"` errors I was getting. Default value of this setting is 50 (milliseconds), but it is better
  if you override it :)
- One or two patch-versions back I added `BITVAVO_API_UPGRADED_EXTERNAL_LOG_LEVEL` as an option, but forgot to mention
  it 😅. This setting covers all loggers that are used by this lib's dependencies (`requests`, which makes use of
  `urllib3`, and `websocket-client` to be a bit more specific). Use this setting to shut them up, by setting the
  variable to `WARNING` or `CRITICAL` 😁

## v1.11.4 - 2022-01-19

### Removed

- duplicate log messages ;)

## v1.11.3 - 2022-01-18

### Changed

- The logger should now be fixed; I wanted all subloggers to get integrated into the struclog style instead of putting
  out some standard text.

## v1.11.2 - 2022-01-16

### Added

- putting `BITVAVO_API_UPGRADED_LOG_LEVEL=DEBUG` into a `.env` file in your client should make this lib spam you with
  log messages.

### Changed

- replaced `python-dotenv` with `python-decouple` lib. This enables us to set default values for settible settings.

## v1.11.1 - 2022-01-16

I ran the unittests this time >\_>

### Changed

- fixed bug where `self.debugging` could not be found in `Bitvavo`

## v1.11.0 - 2022-01-16

### Changed

- all external loggers (urllib3 and websocket being big ones) now all use a fancy format to log! Or at least, they
  should be!
- improved pypi README

## v1.10.0 - 2022-01-15

No more `print()` bullshit! :D

### Added

- classifiers on the pypi page
- a better logging library (structlog). This should enable you to control logging better (while providing better logs!)

## v1.9.0 - 2022-01-15

### Changed

- fixed a critical bug that broke the `Bitvavo` class

## v1.8.3 - 2022-01-15

### Changed

- improve api calls by subtracting some client-server lag; This should make calls more stable
- simplify Bitvavo constructor (doesn't change anything about the external API)
- fix time_to_wait by checking whether curr_time > rateLimitResetAt

### Removed

- rateLimitThread, because it has been a pain in my ass. Using a regular `sleep()` is much better, I noticed.

## v1.8.2 - 2022-01-15

### Changed

- `time_to_wait` now _always_ returns a positive number. I'm getting sick of sleep getting a negative number

## v1.8.1 - 2022-01-15

### Added

- type aliases! You can now use `s`, `ms`, `us`, instead of slapping `int` on everything! float versions `s_f`, `ms_f`
  and `us_f` are also available. You'll likely use `ms` and `s_f` most of the time :)
- helper functions! I added `time_ms` and `time_to_wait` to hide some weird calculations behind functions.

### Changed

- improved the timing calculation and typing of certain values a bit

## v1.8.0 - 2022-01-11

### Changed

- fixed getRemainingLimit - This explains why it NEVER changed from 1000...

## v1.7.0 - 2021-12-31

Documentation now comes built-in! :D

I'll probably find some typo/minor error right after creating this version, but I think for users this is one of the
more important updates, so out it does!

PS: Happy new year! I write this as it's 2021-12-31 23:15. Almost stopping, so I can stuff my face with Oliebollen and
celebrate new year! :D

### Added

- documentation/docstrings for almost every function and method!
- type aliases: `anydict`,`strdict`,`intdict`,`errordict`
- types for `caplog` and `capsys` in all `test_*` function

### Changed

- `candle` wasn't the only wrongly named method. `book` was too. Changed `symbol` argument to `market`
- string concatenation converted to f-strings
- a ton of improvements to unit tests, checking for types, and conversion possibilities, though most of them for
  `Bitvavo`, not for `Bitvavo.websocket`
- simplified a few functions; though I wrote tests for them to confirm behavior before changing them
- improved type hints for several functions - for example: replaced some `Any`'s with `Union[List[anydict], anydict]`;
  in other words: reduced the use of `Any`

### Removed

- the old non-documentation above each function (it usually started with `# options:`)

## v1.6.0 - 2021-12-29

Bugfix round! All found bugs in the original code should now be fixed.

### Changed

- fixed ["Negative sleep time length"](https://github.com/bitvavo/python-bitvavo-api/pull/22)
- fixed ["API response error when calling depositAssets()"](https://github.com/bitvavo/python-bitvavo-api/pull/18)
- in `Bitvavo.candles()` renamed the `symbol` argument to `market`, because candles expects a market, and not a
  symbol... The only API break I've done so far, but it's super minor.

## v1.5.0 - 2021-12-29

### Added

- separate README for pypi; now I can keep that separate from the one on Github; they can share _some_ information, but
  don't need to share all
- guides on how to get started as either a users or a developer (who wants to work on this lib)
- test support for Python 3.7 - 3.10

### Changed

- dependencies are now loosened so users of this lib get more freedom to choose their versions

## v1.4.1 - 2021-12-29

### Changed

- nothing, I just need to push a new commit to Github so I can trigger a new publish

## v1.4.0 - 2021-12-29

### Changed

- set the `mypy` settings to something sane (as per some rando internet articles)
- `pre-commit` `flake8` support; this was initially disabled due to too a lack of sane settings
- reduced pyupgrade from `--py39-plus` to `--py38-plus`, due to `39` changing `Dict` to `dict` and `List` to `list`, but
  `mypy` not being able to handle those new types yet.
- added types to _all_ functions, methods and classes

## v1.3.3 - 2021-12-29

### Changed

- fix the workflow (hopefully) - if I did, then this is the last you'll see about that

## v1.3.2 - 2021-12-29

### Changed

- fix requirements; 1.3.1 is _broken_

## v1.3.1 - 2021-12-29

### Changed

- easy fix to enable publishing to PyPi: disable the `if` that checks for tags 😅

## v1.3.0 - 2021-12-28

### Changed

- when there's a version bump, Github should push to PyPi now (not only to https://test.pypi.org)

## v1.1.1 - 2021-12-28

### Changed

- improved description

## v1.1.0 - 2021-12-28

### Added

- a metric fuckton of tests to check if everything works as expected. said tests are a bit... rough, but it's better
  than nothing, as I already found two bugs that showed that the original code _did not work!_
- two fixtures: `bitvavo` and `websocket`, each used to test each category of methods (REST vs websockets)

### Changed

- renamed the `python_bitvavo_api` folder to `bitvavo_api_upgraded`
- replaced `websocket` lib with `websocket-client`; I picked the wrong lib, initially, due to a lack of requirements in
  the original repo
- the `*ToConsole` functions now use the logging library from Python, as the print statement raised an exception when it
  received a exception object, instead of a string message...... (the `+` symbol was sorta the culprit, but not really -
  the lack of tests was the true culprit)
- the `on_*` methods now have either an extra `self` or `ws` argument, needed to unfuck the websocket code

### Removed

...

## v1.0.2 - 2021-12-27

Everything from since NostraDavid started this project; version `1.0.0` and `1.0.1` did not have `bump2version` working
well yet, which is why they do not have separate entries

### Added

- autopublishing to pypi
- capability to use a `.env` file to hold `BITVAVO_APIKEY` and `BITVAVO_APISECRET` variables
- `setup.py`; it was missing as _someone_ added it to .gitignore
- `__init__.py` to turn the code into a package (for `setup.py`)
- `MANIFEST.in` to include certain files in the source distribution of the app (needed for tox)
- `scripts/bootstrap.sh` to get newbies up and running faster
- ton of tools (`pre-commit`, `tox`, `pytest`, `flake8`, etc; see `requirements/dev.txt` for more information)
- ton of settings (either in `tox.ini`, `pyproject.toml`, or in a dedicated file like `.pre-commit-config` or
  `.bumpversion.cfg`)
- stub test to `test_bitvavo.py` to make tox happy
- added `# type: ignore` in `bitvavo.py` to shush mypy

### Changed

- moved `python_bitvavo_api` into the `src` folders
- moved and renamed `src/python_bitvavo_api/testApi.py` to `tests/test_bitvavo.py` (for `pytest` compatibility)

### Removed

- Nothing yet; I kept code changes to a minimum, until I got `bump2version` working with a `CHANGELOG.md` to prevent
  changing things without noting it down.
