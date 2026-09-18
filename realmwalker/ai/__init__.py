"""Player2 AI integration. The AI writes words; code owns every number and outcome.

Modules:
  client   - thin HTTP wrapper around the local Player2 app API
  parsing  - defensive JSON extraction and refusal detection
  prompts  - prompt templates loaded from ai/prompts/*.txt
  tasks    - the kinds of text we ask for, with schemas and built-in fallbacks
  service  - background workers, priority queue, health ping, status indicator
  store    - "generate once, keep forever" storage for every piece of flavour text
"""
