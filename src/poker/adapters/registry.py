"""Rejestr nazwanych agentów CLI: nazwa -> deterministyczny agent portu Agent."""

from poker.agent import Agent
from poker.clone_agent import CloneAgent
from poker.evaluation import HandCategory
from poker.mlp_agent import MlpCloneAgent
from poker.rule_agent import RuleAgent, RuleAgentThresholds
from poker.strategy_agent import StrategyAgent


def agent_registry() -> dict[str, Agent]:
    return {
        "clone": CloneAgent(),
        "mccfr": StrategyAgent(),
        "mlp-clone": MlpCloneAgent(),
        "rule": RuleAgent(),
        "rule-aggressive": RuleAgent(
            thresholds=RuleAgentThresholds(aggress_from=HandCategory.ONE_PAIR)
        ),
    }
