#!/bin/bash
# Turn the agent incentive engine on.
#
# INCENTIVES_ENABLED defaults to False and was never set in .env, so the whole
# commission engine was dark in production: the Agent Portal advertised
# "Claimable Commission" and "Cashout at 5" while nothing could ever qualify.
# The feature is fully built (incentives.py, IncentiveSetting, payout batches,
# qualification events, the whole portal UI), it was simply never switched on.
set -e
ENV=/root/GAMETECH-BILLING-SYSTEM/.env

if grep -q "^INCENTIVES_ENABLED=" "$ENV"; then
  echo "already present, leaving as-is"
  grep "^INCENTIVES_ENABLED=" "$ENV"
else
  cp "$ENV" "$ENV.bak.pre-incentives-$(date +%Y%m%d_%H%M%S)"
  printf '\n# Agent commission engine. Was defaulted to False and never set, so agents\n# could never qualify for a payout even though the portal advertises it.\nINCENTIVES_ENABLED=True\n' >> "$ENV"
  echo "added INCENTIVES_ENABLED=True"
fi

tail -5 "$ENV"