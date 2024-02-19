# from homeassistant.const import MATCH_ALL

# from ollama import (AsyncClient, ResponseError)


# class Agent(conversation.AbstractConversationAgent):
#     """OpenAI conversation agent."""

#     def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
#         """Initialize the agent."""
#         self.hass = hass
#         self.entry = entry
#         self.history: dict[str, list[dict]] = {}
#         base_url = entry.data.get(CONF_BASE_URL)
#         self.client = AsyncClient(base_url)

#     @property
#     def supported_languages(self) -> list[str] | Literal["*"]:
#         """Return a list of supported languages."""
#         return homeassistant.const.MATCH_ALL

#     async def async_process(
#         self, user_input: conversation.ConversationInput
#     ) -> conversation.ConversationResult:
#         exposed_entities = self.get_exposed_entities()

#         if user_input.conversation_id in self.history:
#             conversation_id = user_input.conversation_id
#             messages = self.history[conversation_id]
#         else:
#             conversation_id = ulid.ulid()
#             user_input.conversation_id = conversation_id
#             try:
#                 system_message = self._generate_system_message(
#                     exposed_entities, user_input
#                 )
#             except TemplateError as err:
#                 _LOGGER.error("Error rendering prompt: %s", err)
#                 intent_response = intent.IntentResponse(
#                     language=user_input.language)
#                 intent_response.async_set_error(
#                     intent.IntentResponseErrorCode.UNKNOWN,
#                     f"Sorry, I had a problem with my template: {err}",
#                 )
#                 return conversation.ConversationResult(
#                     response=intent_response, conversation_id=conversation_id
#                 )
#             messages = [system_message]
#         user_message = {"role": "user", "content": user_input.text}
#         if self.entry.options.get(CONF_ATTACH_USERNAME, DEFAULT_ATTACH_USERNAME):
#             user = await self.hass.auth.async_get_user(user_input.context.user_id)
#             if user is not None and user.name is not None:
#                 user_message[ATTR_NAME] = user.name

#         messages.append(user_message)

#         try:
#             response = await self.query(user_input, messages, exposed_entities, 0)
#         except ResponseError as err:
#             _LOGGER.error(err)
#             intent_response = intent.IntentResponse(
#                 language=user_input.language)
#             intent_response.async_set_error(
#                 intent.IntentResponseErrorCode.UNKNOWN,
#                 f"Sorry, I had a problem talking to OpenAI: {err}",
#             )
#             return conversation.ConversationResult(
#                 response=intent_response, conversation_id=conversation_id
#             )
#         except HomeAssistantError as err:
#             _LOGGER.error(err, exc_info=err)
#             intent_response = intent.IntentResponse(
#                 language=user_input.language)
#             intent_response.async_set_error(
#                 intent.IntentResponseErrorCode.UNKNOWN,
#                 f"Something went wrong: {err}",
#             )
#             return conversation.ConversationResult(
#                 response=intent_response, conversation_id=conversation_id
#             )

#         messages.append(response.model_dump(exclude_none=True))
#         self.history[conversation_id] = messages

#         intent_response = intent.IntentResponse(language=user_input.language)
#         intent_response.async_set_speech(response.content)
#         return conversation.ConversationResult(
#             response=intent_response, conversation_id=conversation_id
#         )

#     def _generate_system_message(
#         self, exposed_entities, user_input: conversation.ConversationInput
#     ):
#         raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)
#         prompt = self._async_generate_prompt(
#             raw_prompt, exposed_entities, user_input)
#         return {"role": "system", "content": prompt}

#     def _async_generate_prompt(
#         self,
#         raw_prompt: str,
#         exposed_entities,
#         user_input: conversation.ConversationInput,
#     ) -> str:
#         """Generate a prompt for the user."""
#         return template.Template(raw_prompt, self.hass).async_render(
#             {
#                 "ha_name": self.hass.config.location_name,
#                 "exposed_entities": exposed_entities,
#                 "current_device_id": user_input.device_id,
#             },
#             parse_result=False,
#         )

#     def get_exposed_entities(self):
#         states = [
#             state
#             for state in self.hass.states.async_all()
#             if async_should_expose(self.hass, conversation.DOMAIN, state.entity_id)
#         ]
#         entity_registry = er.async_get(self.hass)
#         exposed_entities = []
#         for state in states:
#             entity_id = state.entity_id
#             entity = entity_registry.async_get(entity_id)

#             aliases = []
#             if entity and entity.aliases:
#                 aliases = entity.aliases

#             exposed_entities.append(
#                 {
#                     "entity_id": entity_id,
#                     "name": state.name,
#                     "state": self.hass.states.get(entity_id).state,
#                     "aliases": aliases,
#                 }
#             )
#         return exposed_entities

#     def get_functions(self):
#         try:
#             function = self.entry.options.get(CONF_FUNCTIONS)
#             result = yaml.safe_load(
#                 function) if function else DEFAULT_CONF_FUNCTIONS
#             if result:
#                 for setting in result:
#                     function_executor = get_function_executor(
#                         setting["function"]["type"]
#                     )
#                     setting["function"] = function_executor.to_arguments(
#                         setting["function"]
#                     )
#             return result
#         except (InvalidFunction, FunctionNotFound) as e:
#             raise e
#         except:
#             raise FunctionLoadFailed()

#     async def truncate_message_history(
#         self, messages, exposed_entities, user_input: conversation.ConversationInput
#     ):
#         """Truncate message history."""
#         strategy = self.entry.options.get(
#             CONF_CONTEXT_TRUNCATE_STRATEGY, DEFAULT_CONTEXT_TRUNCATE_STRATEGY
#         )

#         if strategy == "clear":
#             last_user_message_index = None
#             for i in reversed(range(len(messages))):
#                 if messages[i]["role"] == "user":
#                     last_user_message_index = i
#                     break

#             if last_user_message_index is not None:
#                 del messages[1:last_user_message_index]
#                 # refresh system prompt when all messages are deleted
#                 messages[0] = self._generate_system_message(
#                     exposed_entities, user_input
#                 )

#     async def query(
#         self,
#         user_input: conversation.ConversationInput,
#         messages,
#         exposed_entities,
#         n_requests,
#     ):
#         """Process a sentence."""
#         model = self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
#         max_tokens = self.entry.options.get(
#             CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
#         top_p = self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
#         temperature = self.entry.options.get(
#             CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
#         use_tools = self.entry.options.get(CONF_USE_TOOLS, DEFAULT_USE_TOOLS)
#         context_threshold = self.entry.options.get(
#             CONF_CONTEXT_THRESHOLD, DEFAULT_CONTEXT_THRESHOLD
#         )
#         functions = list(map(lambda s: s["spec"], self.get_functions()))
#         function_call = "auto"
#         if n_requests == self.entry.options.get(
#             CONF_MAX_FUNCTION_CALLS_PER_CONVERSATION,
#             DEFAULT_MAX_FUNCTION_CALLS_PER_CONVERSATION,
#         ):
#             function_call = "none"

#         tool_kwargs = {"functions": functions, "function_call": function_call}
#         if use_tools:
#             tool_kwargs = {
#                 "tools": [{"type": "function", "function": func} for func in functions],
#                 "tool_choice": function_call,
#             }

#         if len(functions) == 0:
#             tool_kwargs = {}

#         _LOGGER.info("Prompt for %s: %s", model, messages)

#         response: ChatCompletion = await self.client.chat(
#             model=model,
#             messages=messages,
#             max_tokens=max_tokens,
#             top_p=top_p,
#             temperature=temperature,
#             user=user_input.conversation_id,
#             **tool_kwargs,
#         )

#         _LOGGER.info("Response %s", response.model_dump(exclude_none=True))

#         if response.usage.total_tokens > context_threshold:
#             await self.truncate_message_history(messages, exposed_entities, user_input)

#         choice: Choice = response.choices[0]
#         message = choice.message

#         if choice.finish_reason == "function_call":
#             message = await self.execute_function_call(
#                 user_input, messages, message, exposed_entities, n_requests + 1
#             )
#         if choice.finish_reason == "tool_calls":
#             message = await self.execute_tool_calls(
#                 user_input, messages, message, exposed_entities, n_requests + 1
#             )
#         return message

#     async def execute_function_call(
#         self,
#         user_input: conversation.ConversationInput,
#         messages,
#         message: ChatCompletionMessage,
#         exposed_entities,
#         n_requests,
#     ):
#         function_name = message.function_call.name
#         function = next(
#             (s for s in self.get_functions()
#              if s["spec"]["name"] == function_name),
#             None,
#         )
#         if function is not None:
#             return await self.execute_function(
#                 user_input,
#                 messages,
#                 message,
#                 exposed_entities,
#                 n_requests,
#                 function,
#             )
#         raise FunctionNotFound(function_name)

#     async def execute_function(
#         self,
#         user_input: conversation.ConversationInput,
#         messages,
#         message: ChatCompletionMessage,
#         exposed_entities,
#         n_requests,
#         function,
#     ):
#         function_executor = get_function_executor(function["function"]["type"])

#         try:
#             arguments = json.loads(message.function_call.arguments)
#         except json.decoder.JSONDecodeError as err:
#             raise ParseArgumentsFailed(
#                 message.function_call.arguments) from err

#         result = await function_executor.execute(
#             self.hass, function["function"], arguments, user_input, exposed_entities
#         )

#         messages.append(
#             {
#                 "role": "function",
#                 "name": message.function_call.name,
#                 "content": str(result),
#             }
#         )
#         return await self.query(user_input, messages, exposed_entities, n_requests)

#     async def execute_tool_calls(
#         self,
#         user_input: conversation.ConversationInput,
#         messages,
#         message: ChatCompletionMessage,
#         exposed_entities,
#         n_requests,
#     ):
#         messages.append(message.model_dump(exclude_none=True))
#         for tool in message.tool_calls:
#             function_name = tool.function.name
#             function = next(
#                 (s for s in self.get_functions()
#                  if s["spec"]["name"] == function_name),
#                 None,
#             )
#             if function is not None:
#                 result = await self.execute_tool_function(
#                     user_input,
#                     tool,
#                     exposed_entities,
#                     function,
#                 )

#                 messages.append(
#                     {
#                         "tool_call_id": tool.id,
#                         "role": "tool",
#                         "name": function_name,
#                         "content": str(result),
#                     }
#                 )
#             else:
#                 raise FunctionNotFound(function_name)
#         return await self.query(user_input, messages, exposed_entities, n_requests)

#     async def execute_tool_function(
#         self,
#         user_input: conversation.ConversationInput,
#         tool,
#         exposed_entities,
#         function,
#     ):
#         function_executor = get_function_executor(function["function"]["type"])

#         try:
#             arguments = json.loads(tool.function.arguments)
#         except json.decoder.JSONDecodeError as err:
#             raise ParseArgumentsFailed(tool.function.arguments) from err

#         result = await function_executor.execute(
#             self.hass, function["function"], arguments, user_input, exposed_entities
#         )
#         return result
