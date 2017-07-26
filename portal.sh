#!/bin/sh

# Generate the portal config file
./make-portal-config --in portal-template.json \
                     --out portal-config.json \
                     --ir-since 2014-01-01

# Note: ExoSM is excluded, it doesn't work properly with
# jacks-context.
python jacks-context.py --basic \
                        --config portal-config.json \
                        --output jacks-context.json
