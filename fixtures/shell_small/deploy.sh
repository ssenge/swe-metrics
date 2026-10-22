#!/usr/bin/env bash
# Deploys a build with known ShellCheck findings (see expected.json).
target=$1
files=`ls $target`
cd $target
for f in $files; do
  echo "copying $f"
done
if [ $target == "prod" ]; then
  echo "done"
fi
