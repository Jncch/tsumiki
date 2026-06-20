"""tsumiki: AgentSquare tooluse モジュール (vendored from Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/8f5b3fe5d8a32f9b59d20370823bef2a2c86928c/modules/tooluse_modules.py
Vendored at Phase 7e-1 (2026-06-19), rewritten at Phase 7e-2 (2026-06-19).
See docs/agentsquare_vendoring.md for vendoring policy.

Phase 7e-2 modifications:
- `from utils import llm_response` を削除. ChatFn (DI) を `__init__` で受け取る形に変更.
- `from tooluse_IO_pool import tooluse_IO_pool` を削除. `tool_pool: dict[str, str]` を
  `__init__` の引数として外部から注入する形に変更 (将来 `tsumiki.tools` プラグインで埋める想定).
- `langchain_openai.OpenAIEmbeddings` / `langchain_chroma.Chroma` を **削除**.
- `ToolUseToolBench` / `ToolUseToolBenchFormer` (langchain ベース embedding 検索) は **削除**.
  tsumiki では `tsumiki.tools` で決定的ツール選択を提供する想定 (Phase 7e-3 / 7e-4).
- `n=3`, `n=5` のサンプリングは ChatFn を n 回呼ぶループで代替.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable

ChatFn = Callable[[str], str]


class ToolUseBase:
    def __init__(
        self,
        chat_fn: ChatFn,
        llms_type: list[str] | None = None,
        tool_pool: dict[str, str] | None = None,
    ) -> None:
        self.llm_type = llms_type[0] if llms_type else ""
        self.tool_pool: dict[str, str] = tool_pool if tool_pool is not None else {}
        self._chat_fn = chat_fn

    def format_prompt(
        self,
        tool_pool,
        task_description,
        tool_instruction,
        feedback_of_previous_tools,
    ) -> str:
        return f"""You have access to the following tools:
{tool_pool}
You need to select the appropriate tool from the list of available tools according to the task description to complete the task:
{tool_instruction}
You must use the tools by outputting the tool name followed by its arguments, delimited by commas.
You can optionally express your thoughts using natural language before your action. For example, 'Thought: I want to use tool_name to do something. Action: <your action to call tool_name> End Action'.
You can only invoke one tool at a time.
You must begin your tool invocation with 'Action:' and end it with 'End Action'.
Your tool invocation format must follow the invocation format in the tool description.
{feedback_of_previous_tools}
"""


class ToolUseIO(ToolUseBase):
    def __call__(self, task_description, tool_instruction, feedback_of_previous_tools):
        tools = self.tool_pool.get(task_description, "")
        prompt = self.format_prompt(
            tools, task_description, tool_instruction, feedback_of_previous_tools
        )
        return self._chat_fn(prompt)


class ToolUseAnyTool(ToolUseBase):
    def __init__(
        self,
        chat_fn: ChatFn,
        llms_type: list[str] | None = None,
        tool_pool: dict[str, str] | None = None,
    ) -> None:
        super().__init__(chat_fn, llms_type, tool_pool)
        self.dicts: dict[str, list[dict]] = {}
        self.tool_description: dict[str, dict[str, str]] = {}
        for name, tools in self.tool_pool.items():
            pattern = r"\[\d+\] (\w+): (.+?)(?=\[\d+\]|\Z)"
            matches = re.findall(pattern, tools, re.DOTALL)
            self.tool_description[name] = {k: v.strip() for k, v in matches}
            category_prompt = f"""{self.tool_description[name]}
    You have a series of tools, you need to divide them into several categories, such as data calculation, trip booking and so on.
    All tools should be included in categories.
    your output format must be as follows:
    category 1 : {{'category name': 'category description', 'tool list': ['tool 1 name', 'tool 2 name']}}
    category 2 : {{'category name': 'category description', 'tool list': ['tool 1 name', 'tool 2 name']}}
    """
            string = self._chat_fn(category_prompt)
            dict_strings = re.findall(r"\{[^{}]*\}", string)
            self.dicts[name] = [ast.literal_eval(ds) for ds in dict_strings]

    def __call__(self, task_description, tool_instruction, feedback_of_previous_tools):
        prompt = f"""{self.dicts.get(task_description, [])}
You need to select the appropriate tool category from the list of available tools according to the task description to complete the task:
{tool_instruction}
You can only invoke one category at a time.
Completed steps: {feedback_of_previous_tools}
You need to think about what tools do you need next.
Output category name directly.
Your output must be of the following format:
Category name:
"""
        category_name = self._chat_fn(prompt).split(":")[-1].strip()
        matched_tools: dict[str, str] = {}
        for d in self.dicts.get(task_description, []):
            if str(d.get("category name", "")).lower().strip() == category_name.lower().strip():
                matched_tools = {
                    tool: self.tool_description[task_description][tool] for tool in d["tool list"]
                }
                break
        prompt = self.format_prompt(
            matched_tools, task_description, tool_instruction, feedback_of_previous_tools
        )
        return self._chat_fn(prompt)


class ToolUseToolFormer(ToolUseBase):
    def __call__(self, task_description, tool_instruction, feedback_of_previous_tools):
        tools = self.tool_pool.get(task_description, "")
        prompt = self.format_prompt(
            tools, task_description, tool_instruction, feedback_of_previous_tools
        )
        strings = [self._chat_fn(prompt) for _ in range(3)]
        return self.get_votes(tools, tool_instruction, feedback_of_previous_tools, strings)

    def get_votes(self, tool_pool, tool_instruction, feedback_of_previous_tools, strings):
        prompt = f"""You have access to the following tools:
{tool_pool}
You need to select the appropriate tool from the list of available tools according to the task description to complete the task:
{tool_instruction}
You must use the tools by outputing the tool name followed by its arguments, delimited by commas.
You can optionally express your thoughts using natural language before your action. For example, 'Thought: I want to use tool_name to do something. Action: <your action to call tool_name> End Action'.
You can only invoke one tool at a time.
You must begin your tool invocation with 'Action:' and end it with 'End Action'.
Your tool invocation format must follow the invocation format in the tool description.
{feedback_of_previous_tools}
------------
Given several answers, decide which answer is most promising. Output "The best answer is {{s}}", where s the integer id of the choice.
"""
        for i, y in enumerate(strings, 1):
            prompt += f"Answer {i}:\n{y}\n"
        vote_outputs = [self._chat_fn(prompt) for _ in range(5)]
        vote_results = [0] * len(strings)
        for vote_output in vote_outputs:
            pattern = r".*best choice is .*(\d+).*"
            match = re.match(pattern, vote_output, re.DOTALL)
            if match:
                vote = int(match.groups()[0]) - 1
                if vote in range(len(strings)):
                    vote_results[vote] += 1
            else:
                print(f"vote no match: {[vote_output]}")
        ids = list(range(len(strings)))
        select_id = sorted(ids, key=lambda x: vote_results[x], reverse=True)[0]
        return strings[select_id]
