#!/usr/bin/env bash
# SHA-pinned, personal paper-only crypto research; no service installation.
set -euo pipefail
umask 027
OWNER='/home/ubuntu/empire_worktrees/predictive_crypto_personal_owner_20261022'
DEST='/home/ubuntu/empire_releases'
PY='/srv/empire_os/.venv/bin/python'
COMMIT="$(git -C "$OWNER" rev-parse --verify HEAD)"
RELEASE="$DEST/predictive_crypto_personal_${COMMIT:0:12}"
STAGE="$DEST/.predictive_crypto_personal_${COMMIT:0:12}.stage.$$"
FILES=(
  empire_os/__init__.py
  empire_os/predictive_crypto_signal_research.py
  empire_os/predictive_crypto_research_scorecard.py
  empire_os/predictive_crypto_paper_walkforward.py
  empire_os/predictive_crypto_kraken_personal.py
  scripts/review_predictive_crypto_personal_20261022.py
)
[[ -z "$(git -C "$OWNER" status --porcelain)" ]] ||
  { echo 'REFUSE_DIRTY_PERSONAL_CRYPTO_RELEASE' >&2; exit 4; }
[[ ! -e "$RELEASE" && ! -e "$STAGE" && -x "$PY" ]] ||
  { echo 'PERSONAL_CRYPTO_RELEASE_ALREADY_EXISTS_OR_RUNTIME_UNAVAILABLE' >&2; exit 4; }
mkdir -p "$STAGE" "$DEST"
trap 'rm -rf -- "$STAGE"' EXIT
git -C "$OWNER" archive "$COMMIT" -- "${FILES[@]}" | tar -xf - -C "$STAGE"
mkdir -p "$STAGE/bin" "$STAGE/metadata"
printf 'SOURCE_COMMIT=%s\nMODE=PERSONAL_OBSERVE_NO_TRADING_NO_SALES\n' "$COMMIT" > "$STAGE/metadata/source.txt"
cat > "$STAGE/bin/empire-crypto-personal" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
REL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ "$#" == 0 ]]; then
  mode=--capabilities
elif [[ "$#" == 1 && "$1" == "--template" ]]; then
  mode=--template
elif [[ "$#" == 1 && "$1" == "--btc" ]]; then
  mode=--public-btc-hourly
elif [[ "$#" == 1 && "$1" == "--eth" ]]; then
  mode=--public-eth-hourly
elif [[ "$#" == 2 && ( "$1" == "--paper" || "$1" == "--walkforward" ) && -f "$2" && ! -L "$2" ]]; then
  mode=--paper-file
  [[ "$1" == "--walkforward" ]] && mode=--walkforward-file
  file="$2"
else
  echo 'Usage: empire-crypto-personal [--btc | --eth | --template | --paper ORIGINAL.json | --walkforward ORIGINAL.json]' >&2
  exit 2
fi
if [[ -n "${file:-}" ]]; then
  exec env -u PYTHONSTARTUP PYTHONPATH="$REL" /srv/empire_os/.venv/bin/python -P -B \
    -m scripts.review_predictive_crypto_personal_20261022 --read-only "$mode" "$file"
fi
exec env -u PYTHONSTARTUP PYTHONPATH="$REL" /srv/empire_os/.venv/bin/python -P -B \
  -m scripts.review_predictive_crypto_personal_20261022 --read-only "$mode"
LAUNCHER
chmod 0750 "$STAGE/bin/empire-crypto-personal"
(
 cd "$STAGE"
 printf '%s\n' "${FILES[@]}" bin/empire-crypto-personal metadata/source.txt | xargs -d '\n' sha256sum > metadata/source_files.sha256
 sha256sum --status -c metadata/source_files.sha256
)
"$STAGE/bin/empire-crypto-personal" | "$PY" -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["algorithm"]=="EMPIRE_REGIME_RISK_SIGNALS_V1"
assert x["personal_use_only"] is True
assert x["ninety_nine_percent_accuracy_verified"] is False
assert x["exchange_orders_authorized"] is False
assert x["execution_authority"]=="none"
'
"$STAGE/bin/empire-crypto-personal" --template | "$PY" -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["candles"]==[]
assert x["exchange_source_authenticated"] is False
assert x["customer_investment_advice_authorized"] is False
'
chmod -R go-w "$STAGE"
mv -T -- "$STAGE" "$RELEASE"
trap - EXIT
echo "RELEASE_PATH=$RELEASE"
echo "RELEASE_COMMIT=$COMMIT"
echo "LIVE_ORDERS_AND_PRODUCTION_UNCHANGED=true"
