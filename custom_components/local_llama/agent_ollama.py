from __future__ import annotations

from typing import Literal
import json
import logging
import httpx

from homeassistant.components import conversation
from homeassistant.helpers import (
    intent,
    entity_registry as er,
    template,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BASE_URL, DEFAULT_CONF_BASE_URL,

    CONF_PROMPT, DEFAULT_PROMPT,
    CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL,
    CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS,
    CONF_TOP_P, DEFAULT_TOP_P,
    CONF_TEMPERATURE, DEFAULT_TEMPERATURE,
    CONF_USE_TOOLS, DEFAULT_USE_TOOLS,
    CONF_CONTEXT_THRESHOLD, DEFAULT_CONTEXT_THRESHOLD,
    CONF_MAX_FUNCTION_CALLS_PER_CONVERSATION, DEFAULT_MAX_FUNCTION_CALLS_PER_CONVERSATION,
)

from .agent_base import BaseAgent, Response

import requests

_LOGGER = logging.getLogger(__package__)


async def send_post_request(api_url, payload):
    async with httpx.AsyncClient() as client:
        response = await client.post(api_url, json=payload)
        code = str(response.status_code)
        if code == "200":
            content = response.text.strip()
            parsed = json.loads(content)
            response_message = parsed["message"]["content"]
        elif code == "400":
            content = response.text.strip()
            parsed = json.loads(content)
            _LOGGER.error(
                f'status: {code}, {parsed["error"]}, messages: {json.dumps(payload)}')
            response_message = parsed["error"]
        return response.status_code, response_message


class Agent(BaseAgent):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.history: dict[str, list[dict]] = {}
        self.base_url = entry.options.get(CONF_BASE_URL, DEFAULT_CONF_BASE_URL)

    def _generate_system_message(
        self, exposed_entities, user_input: conversation.ConversationInput
    ):
        raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)
        prompt = self._async_generate_prompt(
            raw_prompt, exposed_entities, user_input)
        return {"role": "system", "content": prompt}

    def _async_generate_prompt(
        self,
        raw_prompt: str,
        exposed_entities,
        user_input: conversation.ConversationInput,
    ) -> str:
        """Generate a prompt for the user."""
        _LOGGER.info("_async_generate_prompt: " + raw_prompt)
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
                "exposed_entities": exposed_entities,
                "current_device_id": user_input.device_id,
            },
            parse_result=False,
        )

    async def query(
        self,
        user_input: conversation.ConversationInput,
        messages,
        exposed_entities,
        n_requests,
    ):
        """Process a sentence."""
        model = self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        max_tokens = self.entry.options.get(
            CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        top_p = self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
        temperature = self.entry.options.get(
            CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        use_tools = self.entry.options.get(CONF_USE_TOOLS, DEFAULT_USE_TOOLS)
        context_threshold = self.entry.options.get(
            CONF_CONTEXT_THRESHOLD, DEFAULT_CONTEXT_THRESHOLD
        )
        functions = list(map(lambda s: s["spec"], self.get_functions()))
        function_call = "auto"
        if n_requests == self.entry.options.get(
            CONF_MAX_FUNCTION_CALLS_PER_CONVERSATION,
            DEFAULT_MAX_FUNCTION_CALLS_PER_CONVERSATION,
        ):
            function_call = "none"

        tool_kwargs = {"functions": functions, "function_call": function_call}
        if use_tools:
            tool_kwargs = {
                "tools": [{"type": "function", "function": func} for func in functions],
                "tool_choice": function_call,
            }

        if len(functions) == 0:
            tool_kwargs = {}

        _LOGGER.info("Prompt for %s: %s", model, messages)

        # send request to ollama

        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }

        status_code, parsed_message = await send_post_request(self.base_url, payload)

        return Response(f'{str(status_code)}, {parsed_message}')

        # http://localhost:11434/api/generate

        # response: ChatCompletion = await self.client.chat(
        #     model=model,
        #     messages=messages,
        #     max_tokens=max_tokens,
        #     top_p=top_p,
        #     temperature=temperature,
        #     user=user_input.conversation_id,
        #     **tool_kwargs,
        # )

        # _LOGGER.info("Response %s", response.model_dump(exclude_none=True))

        # if response.usage.total_tokens > context_threshold:
        #     await self.truncate_message_history(messages, exposed_entities, user_input)

        # choice: Choice = response.choices[0]
        # message = choice.message

        # if choice.finish_reason == "function_call":
        #     message = await self.execute_function_call(
        #         user_input, messages, message, exposed_entities, n_requests + 1
        #     )
        # if choice.finish_reason == "tool_calls":
        #     message = await self.execute_tool_calls(
        #         user_input, messages, message, exposed_entities, n_requests + 1
        #     )
        # return message
