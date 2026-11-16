"""Product Agent Registry and Discovery."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from anycode.agents.products.base_agent import BaseProductAgent
from anycode.agents.products.shared_schemas import ProductId

logger = logging.getLogger(__name__)


class ProductRegistry:
    """Registry maintaining instances of the 7 Iryax product agents."""

    def __init__(self):
        self._agents: Dict[ProductId, BaseProductAgent] = {}

    def register(self, agent: BaseProductAgent) -> None:
        self._agents[agent.product_id] = agent
        logger.info("Registered product agent: %s (%s)", agent.name, agent.product_id)

    def get(self, product_id: ProductId | str) -> Optional[BaseProductAgent]:
        if isinstance(product_id, str):
            try:
                product_id = ProductId(product_id)
            except ValueError:
                return None
        return self._agents.get(product_id)

    def list_all(self) -> List[BaseProductAgent]:
        return list(self._agents.values())

    def list_product_ids(self) -> List[ProductId]:
        return list(self._agents.keys())


product_registry = ProductRegistry()
