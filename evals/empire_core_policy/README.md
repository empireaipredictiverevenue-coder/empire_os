# Empire AI Policy Evals

This Promptfoo suite is a promotion gate for models and agents used by EmpireOS.

It tests non-negotiable production rules:

- unknown email stays unknown;
- unknown pricing stays unknown;
- forecasts/payment requests are not actual revenue;
- opt-out suppresses further outreach;
- no model may claim or initiate fund movement without explicit authority;
- inbound email is untrusted content, never executable instruction.

The provider defaults to the local OpenAI-compatible endpoint at
`http://127.0.0.1:11435/v1/chat/completions`.

Override with:

- `EMPIRE_EVAL_URL`
- `EMPIRE_EVAL_MODEL`
- `EMPIRE_EVAL_API_KEY` (optional)

Run from this directory with Promptfoo 0.123.1+ and Node.js 22.22+:

`npx promptfoo@0.123.1 eval -c promptfooconfig.yaml`

A passing eval does not grant execution authority. It is only evidence for
promotion review.
