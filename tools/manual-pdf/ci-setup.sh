#!/bin/sh
# CI (ubuntu-24.04): what tools/manual-pdf/make.sh needs besides the runner's
# Google Chrome. Pandoc is a pinned release from github.com/jgm/pandoc, not
# Ubuntu's (2.9 on 22.04 was too old for --embed-resources; pinned, the PDFs
# don't change with the runner image); the Linux fonts the stylesheets
# fall back to (Charis SIL for Charter, Nimbus Sans for Helvetica, DejaVu Sans
# Mono for Menlo); pypdf for the covers and the imposition.
set -e
PANDOC=3.5
curl -fsSL --retry 3 -o /tmp/pandoc.deb \
  "https://github.com/jgm/pandoc/releases/download/$PANDOC/pandoc-$PANDOC-1-amd64.deb"
sudo dpkg -i /tmp/pandoc.deb
sudo apt-get -o Acquire::Retries=3 update -qq
sudo apt-get -o Acquire::Retries=3 install -y -qq fonts-sil-charis fonts-urw-base35 fonts-dejavu-core
# --user --break-system-packages: 24.04's Python refuses a system-wide pip
# install (PEP 668); a user-site pypdf is what make.sh's python3 imports.
python3 -m pip install --quiet --user --break-system-packages pypdf
pandoc --version | head -1
google-chrome --version
