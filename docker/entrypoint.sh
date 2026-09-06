#!/bin/sh
set -eu

seed_root=/opt/shm/seed
repository=${SHM_REPO_ROOT:-/var/lib/shm/repository}

mkdir -p "$repository"

for directory in config data docs experiments paper reports; do
    if [ ! -e "$repository/$directory" ]; then
        cp -a "$seed_root/$directory" "$repository/$directory"
    fi
done

cd "$repository"
exec "$@"
