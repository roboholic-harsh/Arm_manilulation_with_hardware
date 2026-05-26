"""Tool to save, update, or delete explicit user facts and preferences to Declarative Memory."""

from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult
import logging

logger = logging.getLogger(__name__)

class ManageMemoryTool(BaseTool):
    # This is the tool name which the LLM uses to identify this tool
    name = "manage_memory"
    # This is the tool description which teaches the LLM when to use this tool and what constraints exist
    description = (
        "Save, update, delete, or list important facts, user preferences, or pieces of information (like saved joint positions) in long-term declarative memory. "
        "Use this tool when the user explicitly asks you to remember, update, forget, or display/list saved memories. "
        "IMPORTANT: To save the current joint positions/values, you MUST first run the get_joint_states tool in the same turn to get the latest values."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["save", "delete", "list"],
                "description": "The action to perform: 'save' (creates or updates), 'delete' (removes a memory), or 'list' (retrieves and displays all saved memories)."
            },
            "fact": {
                "type": "string",
                "description": "The clear, standalone fact or information to save. Required if action is 'save'. Ignored for 'delete' or 'list'.",
            },
            "name": {
                "type": "string",
                "description": "An optional unique name or key for this memory (e.g., 'target 1', 'home position'). Required for 'delete', highly recommended for 'save' if referring to specific items. Ignored for 'list'.",
            }
        },
        "required": ["action"],
    }

    def __init__(self, memory_manager):
        self._memory_manager = memory_manager

    def execute(self, action: str, fact: str = "", name: str = "", **kwargs) -> ToolResult:
        action = action.lower()
        if action == "save":
            if not fact:
                return ToolResult(False, "Fact cannot be empty when saving.")
            try:
                self._memory_manager.save_user_memory(fact, name=name if name else None)
                msg = f"Successfully saved fact to memory: '{fact}'"
                if name:
                    msg += f" under the name '{name}'."
                return ToolResult(True, msg)
            except Exception as e:
                logger.error(f"ManageMemoryTool failed to save: {e}")
                return ToolResult(False, f"Failed to save fact to memory: {e}")

        elif action == "delete":
            if not name:
                return ToolResult(False, "A 'name' must be provided to delete a memory.")
            try:
                success = self._memory_manager.delete_user_memory(name)
                if success:
                    return ToolResult(True, f"Successfully deleted memory with name '{name}'.")
                else:
                    return ToolResult(False, f"Could not find or delete memory with name '{name}'.")
            except Exception as e:
                logger.error(f"ManageMemoryTool failed to delete: {e}")
                return ToolResult(False, f"Failed to delete memory: {e}")

        elif action == "list":
            try:
                memories = self._memory_manager.list_user_memories()
                if not memories:
                    return ToolResult(True, "No saved memories found.")
                
                formatted_list = "Saved memories:\n" + "\n".join(memories)
                return ToolResult(True, formatted_list)
            except Exception as e:
                logger.error(f"ManageMemoryTool failed to list: {e}")
                return ToolResult(False, f"Failed to list memories: {e}")

        else:
            return ToolResult(False, f"Invalid action: {action}. Must be 'save', 'delete', or 'list'.")
