"""tsumiki: AgentSquare reasoning モジュール (vendored from Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/8f5b3fe5d8a32f9b59d20370823bef2a2c86928c/modules/reasoning_modules.py
Vendored at Phase 7e-1 (2026-06-19), rewritten at Phase 7e-2 (2026-06-19).
See docs/agentsquare_vendoring.md for vendoring policy.

Phase 7e-2 modifications:
- `from utils import llm_response` を削除. ChatFn (DI) を `__init__` で受け取る形に変更.
- `n=5` / `n=3` のサンプリングは ChatFn を n 回呼ぶループで代替 (`_sample` ヘルパ).
- `stop_strs=['\\n']` は ChatFn の戻り値を `.split('\\n')[0]` で代替 (`_chat_then_strip`).
- ReasoningDILU の system + user メッセージは concat して単一 prompt に変換.
- 上流 alfworld 固有の `process_task_description` (`'You are in the'` 分割等) は **形を保持**.
  ドメイン非依存化は Phase 7e-4 (compose ラッパ) で必要に応じて差し替える.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

ChatFn = Callable[[str], str]


class ReasoningBase:
    def __init__(
        self,
        profile_type_prompt,
        memory,
        chat_fn: ChatFn,
        llms_type: list[str] | None = None,
    ) -> None:
        self.profile_type_prompt = profile_type_prompt
        self.memory = memory
        self.llm_type = llms_type[0] if llms_type else ""
        self.task_name_cache = None
        self.memory_cache: str = ""
        self._chat_fn = chat_fn

    def _chat_then_strip(self, prompt: str) -> str:
        """ChatFn 呼び出し + 改行で打切 (上流 stop_strs=['\\n'] の代替)."""
        return self._chat_fn(prompt).split("\n")[0]

    def _sample(self, prompt: str, n: int) -> list[str]:
        """ChatFn を n 回呼んでサンプル集合を返す (上流 n=5 等の代替)."""
        return [self._chat_then_strip(prompt) for _ in range(n)]

    def process_task_description(self, task_description):
        task_name = re.findall(r"Your task is to:\s*(.*?)\s*>", task_description)
        if self.memory is not None:
            if self.task_name_cache is not None and self.task_name_cache == task_name:
                pass
            else:
                self.task_name_cache = task_name
                self.memory_cache = self.memory(task_description)
        else:
            self.memory_cache = ""
        split_text = task_description.rsplit("You are in the", 1)
        examples = split_text[0]
        task_description = "You are in the" + split_text[1]
        return examples, task_description


class ReasoningIO(ReasoningBase):
    def __call__(self, task_description: str, feedback: str = ""):
        examples, task_description = self.process_task_description(task_description)
        prompt = """Interact with a household to solve a task. Your instructions must follow the examples.
Here are some examples.
{examples}{memory}
Here is the task:
{task_description}"""
        prompt = prompt.format(
            task_description=task_description,
            examples=examples,
            memory=self.memory_cache,
        )
        return self._chat_then_strip(prompt)


class ReasoningCOT(ReasoningBase):
    def __call__(self, task_description: str, feedback: str = ""):
        examples, task_description = self.process_task_description(task_description)
        prompt = """Solve the task step by step. Interact with a household to solve a task. Your instructions must follow the examples.
Here are some examples.
{examples}{memory}
Here is the task:
{task_description}"""
        prompt = prompt.format(
            task_description=task_description,
            examples=examples,
            memory=self.memory_cache,
        )
        return self._chat_then_strip(prompt)


class ReasoningCOTSC(ReasoningBase):
    def __call__(self, task_description: str, feedback: str = ""):
        examples, task_description = self.process_task_description(task_description)
        prompt = """Solve the task step by step. Interact with a household to solve a task. Your instructions must follow the examples.
Here are some examples.
{examples}{memory}
Here is the task:
{task_description}"""
        prompt = prompt.format(
            task_description=task_description,
            examples=examples,
            memory=self.memory_cache,
        )
        reasoning_results = self._sample(prompt, n=5)
        string_counts = Counter(reasoning_results)
        return string_counts.most_common(1)[0][0]


class ReasoningTOT(ReasoningBase):
    def __call__(self, task_description: str, feedback: str = ""):
        examples, task_description = self.process_task_description(task_description)
        prompt = """Solve the task step by step. Interact with a household to solve a task. Your instructions must follow the examples.
Here are some examples.
{examples}{memory}
Here is the task:
{task_description}"""
        prompt = prompt.format(
            task_description=task_description,
            examples=examples,
            memory=self.memory_cache,
        )
        reasoning_results = self._sample(prompt, n=3)
        return self.get_votes(task_description, reasoning_results, examples)

    def get_votes(self, task_description, reasoning_results, examples):
        if "think" in reasoning_results[0].lower():
            return reasoning_results[0]
        prompt = """Given the reasoning process for two completed tasks and one ongoing task, and several answers for the next step, decide which answer best follows the reasoning process for example command format. Output "The best answer is {{s}}", where s is the integer id chosen.
Here are some examples.
{examples}
Here is the task:
{task_description}

"""
        prompt = prompt.format(task_description=task_description, examples=examples)
        for i, y in enumerate(reasoning_results, 1):
            prompt += f"Answer {i}:\n{y}\n"
        vote_outputs = [self._chat_fn(prompt) for _ in range(5)]
        vote_results = [0] * len(reasoning_results)
        for vote_output in vote_outputs:
            pattern = r".*best answer is .*(\d+).*"
            match = re.match(pattern, vote_output, re.DOTALL)
            if match:
                vote = int(match.groups()[0]) - 1
                if vote in range(len(reasoning_results)):
                    vote_results[vote] += 1
            else:
                print(f"vote no match: {[vote_output]}")
        ids = list(range(len(reasoning_results)))
        select_id = sorted(ids, key=lambda x: vote_results[x], reverse=True)[0]
        return reasoning_results[select_id]


class ReasoningDILU(ReasoningBase):
    def __call__(self, task_description: str, feedback: str = ""):
        examples, task_description = self.process_task_description(task_description)
        # 上流は system + user の 2 role を渡していたが, ChatFn は単一 prompt なので concat.
        system_msg = (
            "You are ChatGPT, a large language model trained by OpenAI. "
            "Now you act as a mature domestic robot, who can give accurate and correct instruction "
            "in interacting with a household. You will be given a detailed description of the "
            "scenario of current frame along with your history of previous decisions."
        )
        user_msg = (
            "Above messages are some examples of how you make a step successfully in the past. "
            "Those scenarios are similar to the current scenario. You should refer to those examples "
            "to make a step for the current scenario. Your instructions must follow the examples.\n"
            "Here are two examples.\n"
            f"{examples}{self.memory_cache}\n"
            "Here is the task:\n"
            f"{task_description}"
        )
        prompt = f"[system]\n{system_msg}\n\n[user]\n{user_msg}"
        return self._chat_then_strip(prompt)


class ReasoningSelfRefine(ReasoningBase):
    def __call__(self, task_description: str, feedback: str = ""):
        examples, task_description = self.process_task_description(task_description)
        prompt = """Solve the task step by step. Interact with a household to solve a task. Your instructions must follow the examples.
Here are some examples.
{examples}{memory}
Here is the task:
{task_description}"""
        prompt = prompt.format(
            task_description=task_description,
            examples=examples,
            memory=self.memory_cache,
        )
        reasoning_result = self._chat_then_strip(prompt)
        return self.refine(reasoning_result)

    def refine(self, reasoning_result):
        if "think" in reasoning_result:
            return reasoning_result
        prompt = self._refine_prompt(reasoning_result)
        feedback_result = self._chat_fn(prompt)
        if "correct" in feedback_result.lower():
            if " in " in reasoning_result:
                reasoning_result = reasoning_result.replace(" in ", " in/on ")
            elif " on " in reasoning_result:
                reasoning_result = reasoning_result.replace(" on ", " in/on ")
            return reasoning_result.replace(".", "")
        if " in " in feedback_result:
            feedback_result = feedback_result.replace(" in ", " in/on ")
        elif " on " in feedback_result:
            feedback_result = feedback_result.replace(" on ", " in/on ")
        return feedback_result.split(":")[-1].replace(".", "").strip()

    @staticmethod
    def _refine_prompt(reasoning_result: str) -> str:
        return f"""You need to check that the syntactic structure of the step meets the requirements.
requirements: '1. take a from b 2. go to a 3. : open a 4. put a in/on b, end. 5. clean a with b, end. 6. heat a with b, end. 7. cool a with b, end. 8. use a, end.', where 'a' and 'b' are variable.
examples:
take pencil 1 from desk 2   correct
take potato 1 with fridge 1 error, The preposition with take is from. revised: take potato 1 from bridge 1
go to cabinet 3   correct
go to countertop 2 and check   error, go to countertop 2 is the complete instruction. revised: go to countertop 2
open fridge 1 and take potato 2   error, open fridge 1 is the complete instruction. revised: open fridge 1
open safe 2   correct
put mug 2 in desk 1, end   error, The preposition with put is in/on. revised: put mug 2 in/on desk 1, end
put watch 1 in/on safe 1, end   correct
clean soapbar 1 with sinkbasin 1   error, Add "end" to the clean statement. revised: clean soapbar 1 with sinkbasin 1, end
clean lettuce 4 with sinkbasin 1, end   correct
heat egg 2 with microwave 1, end   correct
heat bread 1 with stoveburner 1, end   error, microwave is what you use to heat. revised: heat bread 1 with microwave 1, end
cool potato 2 with fridge 1, end   correct
cool pan 1, end   error,  bridge is whta you ues to cool. revised: cool pan 1 with bridge 1, end
use desklamp 3 to check statue 2   error, use desklamp3 is the complete instruction. revised: use desklamp 3, end
use desklamp 2, end   correct
Just focus on syntactic structure.
step: {reasoning_result}
You can only output in two formats:
"correct" or "error, revised: your step"
"""


class ReasoningStepBack(ReasoningBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.principle: str = ""

    def __call__(self, task_description: str, feedback: str = ""):
        examples, task_description = self.process_task_description(task_description)
        if task_description.split("Your")[-1].count(">") == 1:
            self.principle = self.stepback(task_description)

        prompt = f"""Solve the task step by step. Interact with a household to solve a task. Your instructions must follow the examples.
Here are some examples.
{examples}{self.memory_cache}{self.principle}
Here is the task:
{task_description}"""
        return self._chat_then_strip(prompt)

    def stepback(self, task_description):
        last_index = task_description.rfind(">")
        task_description = task_description[:last_index]
        stepback_prompt = f"""What common sense, instruction structure is involved in solving this task?
{task_description}"""
        return self._chat_then_strip(stepback_prompt)


class ReasoningSelfReflectiveTOT(ReasoningBase):
    def __call__(self, task_description: str, feedback: str = ""):
        examples, task_description = self.process_task_description(task_description)
        prompt = """Interact with a household to solve a task. Your instructions must follow the examples.
Here are some examples.
{examples}{memory}
Here is the task:
{task_description}"""
        prompt = prompt.format(
            task_description=task_description,
            examples=examples,
            memory=self.memory_cache,
        )
        reasoning_results = self._sample(prompt, n=3)
        reasoning_result = self.get_votes(task_description, reasoning_results, examples)
        return self.refine(reasoning_result)

    def get_votes(self, task_description, reasoning_results, examples):
        if "think" in reasoning_results[0].lower():
            return reasoning_results[0]
        prompt = """Given the reasoning process for two completed tasks and one ongoing task, and several answers for the next step, decide which answer best follows the reasoning process for example command format, which outputs "The best answer is {{s}}", where s is the integer id chosen.
Here are some examples.
{examples}
Here is the task:
{task_description}

"""
        prompt = prompt.format(task_description=task_description, examples=examples)
        for i, y in enumerate(reasoning_results, 1):
            prompt += f"Answer {i}:\n{y}\n"
        vote_outputs = [self._chat_fn(prompt) for _ in range(5)]
        vote_results = [0] * len(reasoning_results)
        for vote_output in vote_outputs:
            pattern = r".*best answer is .*(\d+).*"
            match = re.match(pattern, vote_output, re.DOTALL)
            if match:
                vote = int(match.groups()[0]) - 1
                if vote in range(len(reasoning_results)):
                    vote_results[vote] += 1
            else:
                print(f"vote no match: {[vote_output]}")
        ids = list(range(len(reasoning_results)))
        select_id = sorted(ids, key=lambda x: vote_results[x], reverse=True)[0]
        return reasoning_results[select_id]

    def refine(self, reasoning_result):
        if "think" in reasoning_result:
            return reasoning_result
        prompt = ReasoningSelfRefine._refine_prompt(reasoning_result)
        feedback_result = self._chat_fn(prompt)
        if "correct" in feedback_result.lower():
            if " in " in reasoning_result:
                reasoning_result = reasoning_result.replace(" in ", " in/on ")
            elif " on " in reasoning_result:
                reasoning_result = reasoning_result.replace(" on ", " in/on ")
            return reasoning_result
        if " in " in feedback_result:
            feedback_result = feedback_result.replace(" in ", " in/on ")
        elif " on " in feedback_result:
            feedback_result = feedback_result.replace(" on ", " in/on ")
        return feedback_result.split(":")[-1].strip()
