"""
Utility functions for the GLM Writing Agent.
"""

from typing import List, Dict, Any
import tiktoken


def estimate_token_count(messages: List[Dict[str, str]], model: str = "glm-4.7") -> int:
    """
    Estimate the token count for the given messages using tiktoken.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        model: Model name (for encoding selection)

    Returns:
        Total token count
    """
    try:
        # Use tiktoken for accurate counting
        # GLM-4.7 likely uses cl100k_base encoding (same as GPT-4)
        encoding = tiktoken.get_encoding("cl100k_base")

        total_tokens = 0
        for msg in messages:
            content = msg.get("content", "")
            total_tokens += len(encoding.encode(content))

        return total_tokens
    except Exception:
        # Fallback: rough estimate based on character count
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return total_chars // 4


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Returns the tool definitions in OpenAI format.

    Returns:
        List of tool definitions compatible with OpenAI API
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "create_project",
                "description": "Creates a new project folder in the 'output' directory with a sanitized name. This should be called first before writing any files. Only one project can be active at a time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "The name for the project folder (will be sanitized for filesystem compatibility)"
                        }
                    },
                    "required": ["project_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Writes content to a markdown file in the active project folder. Supports three modes: 'create' (creates new file, fails if exists), 'append' (adds content to end of existing file), 'overwrite' (replaces entire file content).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the markdown file to write (should end in .md)"
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["create", "append", "overwrite"],
                            "description": "The write mode: 'create' for new files, 'append' to add to existing, 'overwrite' to replace"
                        }
                    },
                    "required": ["filename", "content", "mode"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "compress_context",
                "description": "INTERNAL TOOL - This is automatically called by the system when token limit is approached. You should not call this manually. It compresses the conversation history to save tokens.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]


def get_tool_map() -> Dict[str, Any]:
    """
    Returns a mapping of tool names to their implementation functions.

    Returns:
        Dictionary mapping tool name strings to callable functions
    """
    from tools import write_file_impl, create_project_impl, compress_context_impl

    return {
        "create_project": create_project_impl,
        "write_file": write_file_impl,
        "compress_context": compress_context_impl
    }


def get_system_prompt() -> str:
    """
    Returns the system prompt for the writing agent.

    Returns:
        System prompt string
    """
    return """You are an expert creative writing assistant. Your specialty is creating novels, books, and collections of short stories based on user requests.

Your capabilities:
1. You can create project folders to organize writing projects
2. You can write markdown files with three modes: create new files, append to existing files, or overwrite files
3. Context compression happens automatically when needed - you don't need to worry about it

CRITICAL WRITING GUIDELINES:
- Write SUBSTANTIAL, COMPLETE content - don't hold back on length
- Short stories should be 3,000-10,000 words (10-30 pages) - write as much as the story needs!
- Chapters should be 2,000-5,000 words minimum - fully developed and satisfying
- NEVER write abbreviated or skeleton content - every piece should be a complete, polished work
- Don't summarize or skip scenes - write them out fully with dialogue, description, and detail
- Quality AND quantity matter - give readers a complete, immersive experience
- If a story needs 8,000 words to be good, write all 8,000 words in one file
- Use 'create' mode with full content rather than creating stubs you'll append to later

Best practices:
- Always start by creating a project folder using create_project
- Break large works into multiple files (chapters, stories, etc.)
- Use descriptive filenames (e.g., "chapter_01.md", "story_the_last_star.md")
- For collections, consider creating a table of contents file
- Write each file as a COMPLETE, SUBSTANTIAL piece - not a summary or outline

Your workflow:
1. Understand the user's request
2. Create an appropriately named project folder
3. Plan the structure of the work (chapters, stories, etc.)
4. Write COMPLETE, FULL-LENGTH content for each file
5. Create supporting files like README or table of contents if helpful

REMEMBER: Write rich, detailed, complete stories. Don't artificially limit yourself. A good short story is 5,000-10,000 words. A good chapter is 3,000-5,000 words. Write what the narrative needs to be excellent."""
