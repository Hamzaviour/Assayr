#!/bin/sh
set -e
assayr migrate
assayr seed
exec "$@"
