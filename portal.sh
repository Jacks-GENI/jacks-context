#!/bin/sh

# Generate the portal config file
./make-portal-config --in portal-template.json \
                     --out portal-config.json \
                     --ir-since 2014-01-01

# Note: ExoSM is excluded, it doesn't work properly with
# jacks-context.
python jacks-context.py --basic \
                        --config portal-config.json \
                        --output jacks-context.json \
                        apt \
                        cl-utah \
                        clemson-og \
                        eg-fiu \
                        eg-gpo \
                        eg-nicta \
                        eg-osf \
                        eg-rci \
                        eg-sl \
                        eg-tamu \
                        eg-ucd \
                        eg-ufl \
                        eg-uh \
                        eg-wsu \
                        eg-wvn \
                        gpo-og \
                        ig-cenic \
                        ig-chicago \
                        ig-clemson \
                        ig-cornell \
                        ig-cwru \
                        ig-gatech \
                        ig-gpo \
                        ig-illinois \
                        ig-kansas \
                        ig-kentucky \
                        ig-kettering \
                        ig-max \
                        ig-missouri \
                        ig-moxi \
                        ig-northwestern \
                        ig-nps \
                        ig-nysernet \
                        ig-nyu \
                        ig-ohmetrodc \
                        ig-rutgers \
                        ig-sox \
                        ig-stanford \
                        ig-ucla \
                        ig-ukypks2 \
                        ig-ukymcv \
                        ig-umich \
                        ig-umkc \
                        ig-utah \
                        ig-utahddc \
                        ig-utc \
                        ig-uwashington \
                        ig-wisconsin \
                        pg-kentucky \
                        pg-utah \
                        pg-wall1 \
                        pg-wall2 \
                        pg-wilab \
                        ukl-og
