#!/bin/sh
# CI (ubuntu-22.04): what tools/manual-pdf/make.sh needs besides the runner's
# Google Chrome. Ubuntu's pandoc (2.9) is too old for --embed-resources, so a
# pinned release from github.com/jgm/pandoc; the Linux fonts the stylesheets
# fall back to (Charis SIL for Charter, Nimbus Sans for Helvetica, DejaVu Sans
# Mono for Menlo); pypdf for the covers and the imposition.
set -e
PANDOC=3.5
curl -fsSL --retry 3 -o /tmp/pandoc.deb \
  "https://github.com/jgm/pandoc/releases/download/$PANDOC/pandoc-$PANDOC-1-amd64.deb"
sudo dpkg -i /tmp/pandoc.deb
sudo apt-get -o Acquire::Retries=3 update -qq
sudo apt-get -o Acquire::Retries=3 install -y -qq fonts-sil-charis fonts-urw-base35 fonts-dejavu-core
python3 -m pip install --quiet pypdf
pandoc --version | head -1
google-chrome --version
