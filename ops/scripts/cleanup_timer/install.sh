#!/bin/bash
# Installs the systemd-timer alternative to the `beat` docker-compose
# service. Run on the VM as root. If you use this, disable/remove the
# `beat` service in docker-compose.yml so the sweep doesn't run twice.
set -euo pipefail

cp dietnet-cleanup.service /etc/systemd/system/
cp dietnet-cleanup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dietnet-cleanup.timer
systemctl list-timers dietnet-cleanup.timer
