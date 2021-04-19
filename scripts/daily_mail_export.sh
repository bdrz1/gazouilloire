#!/bin/bash

# - Usage:
# Place this script in your gazouilloire corpus directory
# Run it by giving it the corpus name as argument and
# the directory where to place the data exports, as well as
# the adress that will be used to send the e-mails and the 
# adresses to which it should be sent, and finally the root url
# of the server where the files will be for instance:
# ./daily_mail_export.sh mycorpus my@email.fr "my@email.fr mycolleague@email.fr" "https://myserver.fr/path_where_exports_are_served"
#
# - Prerequisites:
# This script supposes gazouilloire was installed within a python environment using PyEnv:
# https://github.com/pyenv/pyenv-installer
#
# - Typical cronjob:
# The main use of this script is to automate building daily exports
# and send it by email every day.
# A typical crontab would look something like the following:
#
# m  h dom mon dow   command
# 00 8  *   *   *    bash /data/gazouilloire/daily_mail_export.sh CORPUSNAME EXPORTS_DIRECTORY SENDER_EMAIL "RECEIVER_EMAIL_1 RECEIVER_EMAIL_2 ..." "SERVER_URL"


# User arguments to adapt (TODO: transform into CLI args)
CORPUS=$1
OUTDIR=$2
SENDER=$3
RECEIVERS=$4
BASEURL=$5

# Internal variables
CORPUSDIR=$(dirname "$0")
CORPUSENV="gazou-$CORPUS"
OUTFILE="tweets_${CORPUS}_${YESTERDAY}.csv"
YESTERDAY=$(date -d yesterday --iso)
TODAY=$(date --iso)

# Load gazouilloire's python virtualenv
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
export PYENV_VIRTUALENV_DISABLE_PROMPT=1
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv activate "$CORPUSENV"

# Load cargo for xsv use
source "$HOME/.cargo/env"

# Export tweets from last day
cd "$CORPUSDIR"
mkdir -p "$OUTDIR"
gazou export --since "$YESTERDAY" --until "$TODAY" --quiet > $OUTDIR/$OUTFILE

# Count tweets and file size
count=$(xsv count $OUTDIR/$OUTFILE)
fsize=$(ls -lh $OUTDIR/$OUTFILE | awk '{print $5}')

# Zip it and measure new size
gzip $OUTDIR/$OUTFILE
zsize=$(ls -lh $OUTDIR/${OUTFILE}.gz | awk '{print $5}')

# Send an e-mail with a link to the gzip and quick metadata
emailtext="
$YESTERDAY

$count tweets
$fsize ($zsize zipped)
$BASEURL/$CORPUS/${OUTFILE}.gz"

echo "$emailtext" | mail -s "[Tweets $CORPUS] Daily export $YESTERDAY" -S replyto="$SENDER" $RECEIVERS

