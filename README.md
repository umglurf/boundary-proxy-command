<!--
SPDX-FileCopyrightText: 2022 Håvard Moen <post@haavard.name>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Project has moved

You can now find this project at [codeberg](https://codeberg.org/umglurf/boundary-proxy-command) instead.

# boundary-proxy-command

Wrapper script for running commands through [boundary](https://www.boundaryproject.io) with correct hostname so ssl can be verified.

## Installing

The requirements are set up using [pipenv](https://github.com/pypa/pipenv), run `pipenv install` to install required dependencies.

## Usage

You need to have the environment variable `BOUNDARY_ADDR` set. Run `boundary-proxy-command -h` to see all options.
The environment variable `BOUNDARY_LISTEN_PORT` will be set for the command to the port set up by boundary to listen on.
If `listen_port` argument is not given, this is a random port chosen by boundary.

## Example

You have the program `salt-pepper` which needs to connect to `https://salt.example.com:8000` which is only available through boundary.
You can then run
```bash
`pipenv run ./boundary-proxy-command.py --hostname salt.example.com --target 'name of salt target' --listen_port 8000 -- salt-pepper ...
```
