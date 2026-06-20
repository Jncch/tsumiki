"""tsumiki: AgentSquare planning モジュール (vendored from Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/8f5b3fe5d8a32f9b59d20370823bef2a2c86928c/modules/planning_modules.py
Vendored at Phase 7e-1 (2026-06-19), rewritten at Phase 7e-2 (2026-06-19).
See docs/agentsquare_vendoring.md for vendoring policy.

Phase 7e-2 modifications:
- `from utils import llm_response` を削除. ChatFn (DI) を `__init__` で受け取る形に変更.
- `from planning_prompt import *` を削除. few_shot 例は `__call__` の引数で外部から注入.
- `llms_type` は後方互換のため引数で受けるが, モデル選択は `chat_fn` 内部 (`settings.model`) で完結.
- 上流の各 PlanningXxx の `create_prompt` の英語プロンプトは構造を保持. 内容のドメイン非依存化は
  Phase 7e-4 (compose ラッパ) で必要に応じて差し替える.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable

ChatFn = Callable[[str], str]


class PlanningBase:
    def __init__(
        self,
        chat_fn: ChatFn,
        llms_type: list[str] | None = None,
    ) -> None:
        self.plan: list[dict] = []
        self.llm_type = llms_type[0] if llms_type else ""
        self._chat_fn = chat_fn

    def create_prompt(
        self,
        task_type: str,
        task_description: str,
        feedback: str,
        few_shot: str,
    ) -> str:
        raise NotImplementedError("Subclasses should implement this method")

    def __call__(
        self,
        task_type: str,
        task_description: str,
        feedback: str,
        few_shot: str,
    ) -> list[dict]:
        prompt = self.create_prompt(task_type, task_description, feedback, few_shot)
        string = self._chat_fn(prompt)
        dict_strings = re.findall(r"\{[^{}]*\}", string)
        dicts = [ast.literal_eval(ds) for ds in dict_strings]
        self.plan = dicts
        return self.plan


class PlanningIO(PlanningBase):
    def create_prompt(self, task_type, task_description, feedback, few_shot):
        if feedback == "":
            prompt = """You are a planner who divides a {task_type} task into several subtasks. You also need to give the reasoning instructions for each subtask and the instructions for calling the tool. Your output format should follow the example below.
The following are some examples:
Task: {example}

Task: {task_description}
"""
            return prompt.format(
                example=few_shot,
                task_description=task_description,
                task_type=task_type,
            )
        prompt = """You are a planner who divides a {task_type} task into several subtasks. You also need to give the reasoning instructions for each subtask and the instructions for calling the tool. Your output format should follow the example below.
The following are some examples:
Task: {example}

end
--------------------
Reflexion:{feedback}
Task:{task_description}
"""
        return prompt.format(
            example=few_shot,
            task_description=task_description,
            task_type=task_type,
            feedback=feedback,
        )


class PlanningDEPS(PlanningBase):
    def create_prompt(self, task_type, task_description, feedback, few_shot):
        if feedback == "":
            prompt = """You are a helper AI agent in reasoning. You need to generate the sequences of sub-goals (actions) for a {task_type} task in multi-hop questions. You also need to give the reasoning instructions for each subtask and the instructions for calling the tool. Your output format should follow the example below.
The following are some examples:
Task: {example}

Task: {task_description}
"""
            return prompt.format(
                example=few_shot,
                task_description=task_description,
                task_type=task_type,
            )
        prompt = """You are a helper AI agent in reasoning. You need to generate the sequences of sub-goals (actions) for a {task_type} task in multi-hop questions. You also need to give the reasoning instructions for each subtask and the instructions for calling the tool. Your output format should follow the example below.
The following are some examples:
Task: {example}

end
--------------------
Reflexion:{feedback}
Task:{task_description}
"""
        return prompt.format(
            example=few_shot,
            task_description=task_description,
            task_type=task_type,
            feedback=feedback,
        )


class PlanningTD(PlanningBase):
    def create_prompt(self, task_type, task_description, feedback, few_shot):
        if feedback == "":
            prompt = """You are a planner who divides a {task_type} task into several subtasks with explicit temporal dependencies.
Consider the order of actions and their dependencies to ensure logical sequencing.
Your output format must follow the example below, specifying the order and dependencies.
The following are some examples:
Task: {example}

Task: {task_description}
"""
        else:
            prompt = """You are a planner who divides a {task_type} task into several subtasks with explicit temporal dependencies.
Consider the order of actions and their dependencies to ensure logical sequencing.
Your output format should follow the example below, specifying the order and dependencies.
The following are some examples:
Task: {example}

end
--------------------
Reflexion:{feedback}
Task:{task_description}
"""
        return prompt.format(
            example=few_shot,
            task_description=task_description,
            task_type=task_type,
            feedback=feedback,
        )


class PlanningVoyager(PlanningBase):
    def create_prompt(self, task_type, task_description, feedback, few_shot):
        if feedback == "":
            prompt = """You are a helpful assistant that generates subgoals to complete any {task_type} task specified by me.
I'll give you a final task, you need to decompose the task into a list of subgoals.
You must follow the following criteria:
1) Return a  list of subgoals that can be completed in order to complete the specified task.
2) Give the reasoning instructions for each subgoal and the instructions for calling the tool.
You also need to give the reasoning instructions for each subtask and the instructions for calling the tool. Your output format should follow the example below.
The following are some examples:
Task: {example}

Task: {task_description}
"""
        else:
            prompt = """You are a helpful assistant that generates subgoals to complete any {task_type} task specified by me.
I'll give you a final task, you need to decompose the task into a list of subgoals.
You must follow the following criteria:
1) Return a list of subgoals that can be completed in order to complete the specified task.
2) Give the reasoning instructions for each subgoal and the instructions for calling the tool.
You also need to give the reasoning instructions for each subtask and the instructions for calling the tool. Your output format should follow the example below.
The following are some examples:
Task: {example}

end
--------------------
reflexion:{feedback}
task:{task_description}
"""
        return prompt.format(
            example=few_shot,
            task_description=task_description,
            task_type=task_type,
            feedback=feedback,
        )


class PlanningOPENAGI(PlanningBase):
    def create_prompt(self, task_type, task_description, feedback, few_shot):
        if feedback == "":
            prompt = """You are a planner who is an expert at coming up with a todo list for a given {task_type} objective.
For each task, you also need to give the reasoning instructions for each subtask and the instructions for calling the tool.
Ensure the list is as short as possible, and tasks in it are relevant, effective and described in a single sentence.
Develop a concise to-do list to achieve the objective.
Your output format should follow the example below.
The following are some examples:
Task: {example}

Task: {task_description}
"""
        else:
            prompt = """You are a planner who is an expert at coming up with a todo list for a given {task_type} objective.
For each task, you also need to give the reasoning instructions for each subtask and the instructions for calling the tool.
Ensure the list is as short as possible, and tasks in it are relevant, effective and described in a single sentence.
Develop a concise to-do list to achieve the objective.
Your output format should follow the example below.
The following are some examples:
Task: {example}

end
--------------------
Reflexion:{feedback}
Task:{task_description}
"""
        return prompt.format(
            example=few_shot,
            task_description=task_description,
            task_type=task_type,
            feedback=feedback,
        )


class PlanningHUGGINGGPT(PlanningBase):
    def create_prompt(self, task_type, task_description, feedback, few_shot):
        if feedback == "":
            prompt = """You are a planner who divides a {task_type} task into several subtasks. Think step by step about all the tasks needed to resolve the user's request. Parse out as few tasks as possible while ensuring that the user request can be resolved. Pay attention to the dependencies and order among tasks. you also need to give the reasoning instructions for each subtask and the instructions for calling the tool. Your output format should follow the example below.
The following are some examples:
Task: {example}

Task: {task_description}
"""
        else:
            prompt = """You are a planner who divides a {task_type} task into several subtasks. Think step by step about all the tasks needed to resolve the user's request. Parse out as few tasks as possible while ensuring that the user request can be resolved. Pay attention to the dependencies and order among tasks. you also need to give the reasoning instructions for each subtask and the instructions for calling the tool. Your output format should follow the example below.
The following are some examples:
Task: {example}

end
--------------------
Reflexion:{feedback}
Task:{task_description}
"""
        return prompt.format(
            example=few_shot,
            task_description=task_description,
            task_type=task_type,
            feedback=feedback,
        )
