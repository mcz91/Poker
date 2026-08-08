"""Rejestr nazwanych agentów CLI: nazwa -> deterministyczny agent portu Agent."""

from poker.agent import Agent
from poker.evaluation import HandCategory
from poker.rule_agent import RuleAgent, RuleAgentThresholds


def agent_registry() -> dict[str, Agent]:
    return {
        "rule": RuleAgent(),
        "rule-aggressive": RuleAgent(
            thresholds=RuleAgentThresholds(aggress_from=HandCategory.ONE_PAIR)
        ),
    }
