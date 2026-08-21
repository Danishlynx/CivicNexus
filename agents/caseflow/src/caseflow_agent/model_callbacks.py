"""Baseline-parity model callback (B-009 run-5): strip the framework's
injected identity block.

Chat-mode agents get 'You are an agent. Your internal name is "..."' [+
description] prepended by ADK's identity processor; the measured-80%
baseline ran the specialists as single_turn nodes, which skip it. This is
the audit-isolated residual difference between the two request shapes
(the other — a transfer_to_agent declaration — is not cheaply addable).
"""

import re
from typing import Any

_IDENTITY = re.compile(
    r'You are an agent\. Your internal name is "[^"]*"\.'
    r'( The description about you is "[^"]*"\.)?\s*'
)


def strip_identity(callback_context: Any, llm_request: Any) -> None:
    """before_model_callback: remove the identity block in place."""
    try:
        si = llm_request.config.system_instruction
        if isinstance(si, str):
            llm_request.config.system_instruction = _IDENTITY.sub("", si)
    except Exception:  # never break a billed call over cosmetics
        pass
    return None
