#!/bin/bash

export FLASK_DEBUG=1
export FLASK_APP=app.py
export FLASK_ENV=development
export STUDIO_BASE_DIR=~/studioVI

. .venv/bin/activate
flask --app app run --host=localhost --port=5000
