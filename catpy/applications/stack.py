from catpy.applications import NameResolver
from catpy.stacks import ProjectStack
from .base import CatmaidClientApplication
from typing import NamedTuple, List, Union, Dict


class ShortStackInfo(NamedTuple):
    id: int
    pid: int
    title: str
    comment: str


class StackInGroup(NamedTuple):
    id: int
    relation: str
    position: int


class StackGroup(NamedTuple):
    id: int
    project_id: int
    title: str
    stacks: List[StackInGroup]


class StackFetcher(CatmaidClientApplication):
    def __init__(self, catmaid_client):
        super().__init__(catmaid_client)
        self.name_resolver = NameResolver(catmaid_client)

    def _get_stack_id(self, stack_id_or_title):
        try:
            return int(stack_id_or_title)
        except TypeError:
            if stack_id_or_title is None:
                return None
            return self.name_resolver.get_stack_id(stack_id_or_title)

    def _stacks(self) -> List[Dict[str, Union[int, str]]]:
        return self.get((self.project_id, "stacks"))

    def stacks(self) -> List[ShortStackInfo]:
        return [ShortStackInfo(**d) for d in self._stacks()]

    def _stack_info(self, stack_id):
        stack_id = self._get_stack_id(stack_id)
        return self.get((self.project_id, "stack", stack_id, "info"))

    def stack_info(self, stack_id) -> ProjectStack:
        stack_id = self._get_stack_id(stack_id)
        return ProjectStack.from_stack_info(self._stack_info(stack_id))

    def stack_groups(self, stack_id) -> List[int]:
        """Groups to which stack_id belongs"""
        stack_id = self._get_stack_id(stack_id)
        return sorted(self.get((self.project_id, "stack", stack_id, "groups")))

    def _stack_group(self, group_id):
        return self.get((self.project_id, "stackgroup", group_id, "info"))

    def stack_group(self, group_id):
        data = self._stack_group(group_id)
        data["stacks"] = sorted(
            (StackInGroup(**d) for d in data["stacks"]), key=lambda s: s.position
        )
        return StackGroup(**data)
