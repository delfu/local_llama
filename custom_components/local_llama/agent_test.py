from __future__ import annotations

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .agent_base import BaseAgent, Response


class Agent(BaseAgent):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)

    async def query(
        self,
        user_input: conversation.ConversationInput,
        messages,
        exposed_entities,
        n_requests,
    ):
        response = Response("this is a test message")
        return response
