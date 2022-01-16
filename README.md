<!--
SPDX-FileCopyrightText: 2022 Håvard Moen <post@haavard.name>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# boundary-proxy-command

Wrapper script for running commands through boundary with correct hostname so ssl can be verified.

## Usage

You need to have the environment variable `BOUNDARY_ADDR' set. Run `boundary-proxy-command -h` to see all options.
The environment variable `BOUNDARY_LISTEN_PORT` will be set for the command to the port set up by boundary to listen on.
If `listen_port` argument is not given, this is a random port chosen by boundary.

## Example

You have the program `salt-pepper` which needs to connect to `https://salt.example.com:8000` which is only available through boundary.
You can then run
```bash
`boundary-proxy-command.py --hostname salt.example.com --target 'name of salt target' --listen_port 8000 -- salt-pepper ...
```
