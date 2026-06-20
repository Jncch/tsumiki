"""tsumiki: AgentSquare memory モジュール (vendored from Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/8f5b3fe5d8a32f9b59d20370823bef2a2c86928c/modules/memory_modules.py
Vendored at Phase 7e-1 (2026-06-19), rewritten at Phase 7e-2 (2026-06-19).
See docs/agentsquare_vendoring.md for vendoring policy.

Phase 7e-2 modifications:
- `from utils import llm_response` を削除. ChatFn (DI) を `__init__` で受け取る形に変更.
- `langchain_openai.OpenAIEmbeddings` / `langchain_chroma.Chroma` / `langchain.docstore.document.Document`
  を **削除**. 代替として in-memory な `_SimpleMemoryStore` を導入 (semantic 検索ではなく
  substring 一致 + 最新順のヒューリスティック).
  本来の semantic 類似検索が必要になれば Phase 7e-4 以降で `tsumiki.knowledge.skills` 参照に
  差し替える.
- 永続化 (`shutil`, `os.path`, `./db` ディレクトリ) を削除. Phase 7e-2 段階では in-memory.
"""

from __future__ import annotations

import re
from collections.abc import Callable

ChatFn = Callable[[str], str]


class _SimpleMemoryStore:
    """langchain Chroma の代替. semantic 検索ではなく substring 一致 + 最新順.

    Phase 7e-2 では AgentSquare モジュール群の import 通過と基本動作確認を主目的とする.
    本物の semantic 検索が要件になれば Phase 7e-4 以降で差し替える.
    """

    def __init__(self) -> None:
        self._docs: list[dict] = []

    def count(self) -> int:
        return len(self._docs)

    def add(self, page_content: str, metadata: dict) -> None:
        self._docs.append({"page_content": page_content, "metadata": metadata})

    def search(self, query: str, k: int = 1) -> list[dict]:
        if not self._docs:
            return []
        matched = [d for d in self._docs if query.lower() in d["page_content"].lower()]
        rest = [d for d in self._docs if d not in matched]
        return (matched + rest)[:k]


class MemoryBase:
    def __init__(
        self,
        chat_fn: ChatFn,
        llms_type: list[str] | None = None,
        memory_type: str = "",
    ) -> None:
        self.llm_type = llms_type[0] if llms_type else ""
        self.memory_type = memory_type
        self.scenario_memory = _SimpleMemoryStore()
        self._chat_fn = chat_fn

    def __call__(self, current_situation: str = ""):
        if "success." in current_situation:
            self.addMemory(current_situation.replace("success.", ""))
        else:
            return self.retriveMemory(current_situation)
        return None

    def retriveMemory(self, query_scenario):
        raise NotImplementedError("This method should be implemented by subclasses.")

    def addMemory(self, current_situation):
        raise NotImplementedError("This method should be implemented by subclasses.")


class MemoryDILU(MemoryBase):
    def __init__(self, chat_fn: ChatFn, llms_type: list[str] | None = None) -> None:
        super().__init__(chat_fn, llms_type, memory_type="dilu")

    def retriveMemory(self, query_scenario):
        # Extract task name from query scenario
        task_names = re.findall(r"Your task is to:\s*(.*?)\s*>", query_scenario)
        if len(task_names) < 3:
            return ""
        task_name = task_names[2]
        if self.scenario_memory.count() == 0:
            return ""
        similarity_results = self.scenario_memory.search(task_name, k=1)
        task_trajectories = [r["metadata"]["task_trajectory"] for r in similarity_results]
        return "\n".join(task_trajectories)

    def addMemory(self, current_situation):
        m = re.search(r"Your task is to:\s*(.*?)\s*>", current_situation)
        if m is None:
            return
        task_name = m.group(1)
        self.scenario_memory.add(
            page_content=task_name,
            metadata={"task_name": task_name, "task_trajectory": current_situation},
        )


class MemoryGenerative(MemoryBase):
    def __init__(self, chat_fn: ChatFn, llms_type: list[str] | None = None) -> None:
        super().__init__(chat_fn, llms_type, memory_type="generative")

    def retriveMemory(self, query_scenario):
        task_names = re.findall(r"Your task is to:\s*(.*?)\s*>", query_scenario)
        if len(task_names) < 3:
            return ""
        task_name = task_names[2]
        if self.scenario_memory.count() == 0:
            return ""
        similarity_results = self.scenario_memory.search(task_name, k=3)
        fewshot_results = []
        importance_scores = []
        for result in similarity_results:
            trajectory = result["metadata"]["task_trajectory"]
            fewshot_results.append(trajectory)
            prompt = f"""You will be given a successful case where you successfully complete the task. Then you will be given an ongoing task. Do not summarize these two cases, but rather evaluate how relevant and helpful the successful case is for the ongoing task, on a scale of 1-10.
Success Case:
{trajectory}
Ongoing task:
{query_scenario}
Your output format should be:
Score: """
            response = self._chat_fn(prompt).split("\n")[0]
            score = int(re.search(r"\d+", response).group()) if re.search(r"\d+", response) else 0
            importance_scores.append(score)
        max_score_idx = importance_scores.index(max(importance_scores))
        return similarity_results[max_score_idx]["metadata"]["task_trajectory"]

    def addMemory(self, current_situation):
        m = re.search(r"Your task is to:\s*(.*?)\s*>", current_situation)
        if m is None:
            return
        task_name = m.group(1)
        self.scenario_memory.add(
            page_content=task_name,
            metadata={"task_name": task_name, "task_trajectory": current_situation},
        )


class MemoryTP(MemoryBase):
    def __init__(self, chat_fn: ChatFn, llms_type: list[str] | None = None) -> None:
        super().__init__(chat_fn, llms_type, memory_type="tp")

    def retriveMemory(self, query_scenario):
        task_names = re.findall(r"Your task is to:\s*(.*?)\s*>", query_scenario)
        if len(task_names) < 3:
            return ""
        task_name = task_names[2]
        if self.scenario_memory.count() == 0:
            return ""
        similarity_results = self.scenario_memory.search(task_name, k=1)
        experience_plans = []
        task_description = "You are in the" + query_scenario.rsplit("You are in the", 1)[1]
        for result in similarity_results:
            prompt = f"""You will be given a successful case where you successfully complete the task. Then you will be given an ongoing task. Do not summarize these two cases, but rather use the successful case to think about the strategy and path you took to attempt to complete the task in the ongoing task. Devise a concise, new plan of action that accounts for your task with reference to specific actions that you should have taken. You will need this later to solve the task. Give your plan after "Plan".
Success Case:
{result["metadata"]["task_trajectory"]}
Ongoing task:
{task_description}
Plan:
"""
            experience_plans.append(self._chat_fn(prompt))
        return "Plan from successful attempt in similar task:\n" + "\n".join(experience_plans)

    def addMemory(self, current_situation):
        m = re.search(r"Your task is to:\s*(.*?)\s*>", current_situation)
        if m is None:
            return
        task_name = m.group(1)
        self.scenario_memory.add(
            page_content=task_name,
            metadata={"task_name": task_name, "task_trajectory": current_situation},
        )


class MemoryVoyager(MemoryBase):
    def __init__(self, chat_fn: ChatFn, llms_type: list[str] | None = None) -> None:
        super().__init__(chat_fn, llms_type, memory_type="voyager")

    def retriveMemory(self, query_scenario):
        task_names = re.findall(r"Your task is to:\s*(.*?)\s*>", query_scenario)
        if len(task_names) < 3:
            return ""
        task_name = task_names[2]
        if self.scenario_memory.count() == 0:
            return ""
        similarity_results = self.scenario_memory.search(task_name, k=1)
        memory_trajectories = [r["metadata"]["task_trajectory"] for r in similarity_results]
        return "\n".join(memory_trajectories)

    def addMemory(self, current_situation):
        voyager_prompt = """You are a helpful assistant that writes a description of the task resolution trajectory.

        1) Try to summarize the trajectory in no more than 6 sentences.
        2) Your response should be a single line of text.

        For example:
        Trajectory:
        You are in the middle of a room. Looking quickly around you, you see a cabinet 10, a cabinet 9, a cabinet 8, a cabinet 7, a cabinet 6, a cabinet 5, a cabinet 4, a cabinet 3, a cabinet 2, a cabinet 1, a coffeemachine 1, a countertop 3, a countertop 2, a countertop 1, a diningtable 1, a drawer 6, a drawer 5, a drawer 4, a drawer 3, a drawer 2, a drawer 1, a fridge 1, a garbagecan 1, a microwave 1, a sinkbasin 1, a stoveburner 4, a stoveburner 3, a stoveburner 2, a stoveburner 1, and a toaster 1.
        Your task is to: heat some egg and put it in diningtable.
        > think: To solve the task, I need to find and take an egg, then heat it with microwave, then put it in diningtable.
        OK.

        Then you would write: The trajectory is about finding an egg, heating it with a microwave, and placing it on the dining table after checking various locations like the fridge and countertops.

        Trajectory:
        """
        prompt = voyager_prompt + current_situation
        trajectory_summary = self._chat_fn(prompt)
        self.scenario_memory.add(
            page_content=trajectory_summary,
            metadata={
                "task_description": trajectory_summary,
                "task_trajectory": current_situation,
            },
        )
