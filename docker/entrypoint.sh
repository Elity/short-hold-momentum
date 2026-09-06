#!/bin/sh
set -eu

seed_root=${SHM_SEED_ROOT:-/opt/shm/seed}
repository=${SHM_REPO_ROOT:-/var/lib/shm/repository}

mkdir -p "$repository"

for directory in config data docs experiments paper reports; do
    if [ ! -e "$repository/$directory" ]; then
        cp -a "$seed_root/$directory" "$repository/$directory"
    fi
done

# Existing volumes already have the V04 directories. Add versioned research
# assets without replacing owner files, frozen winners, or paper ledgers.
for directory in config/v03 experiments/prereg/v03 experiments/v03 reports/v03 \
                 config/v04 experiments/prereg/v04 experiments/v04 reports/v04 \
                 data/reference/sp500; do
    if [ -d "$seed_root/$directory" ]; then
        find "$seed_root/$directory" -type f | while IFS= read -r source; do
            destination="$repository/${source#"$seed_root/"}"
            if [ ! -e "$destination" ] && [ ! -L "$destination" ]; then
                mkdir -p "$(dirname "$destination")"
                cp -p "$source" "$destination"
            fi
        done
    fi
done

for file in config/sp500.yaml docs/spec-v0.3.md docs/decisions/ADR-011-v03-trend-exit-research.md \
            docs/spec-v0.4.md docs/decisions/ADR-012-sp500-universe.md; do
    if [ -f "$seed_root/$file" ] && [ ! -e "$repository/$file" ] && [ ! -L "$repository/$file" ]; then
        mkdir -p "$(dirname "$repository/$file")"
        cp -p "$seed_root/$file" "$repository/$file"
    fi
done

cd "$repository"
exec "$@"
