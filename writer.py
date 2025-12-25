#!/usr/bin/env python3
"""
GLM Writing Agent - An autonomous agent for creative writing tasks.

This agent uses the GLM-4.7 model to create novels, books,
and short story collections based on user prompts.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
from zai import ZaiClient
from typing import List, Dict, Any

# Load environment variables from .env file
load_dotenv()

from utils import (
    estimate_token_count,
    get_tool_definitions,
    get_tool_map,
    get_system_prompt,
)
from tools.compression import compress_context_impl


# Constants
MAX_ITERATIONS = 300
TOKEN_LIMIT = 200000  # GLM-4.7 context window
COMPRESSION_THRESHOLD = 180000  # Trigger compression at 90% of limit
MODEL_NAME = "glm-4.7"
BACKUP_INTERVAL = 50  # Save backup summary every N iterations


def load_context_from_file(file_path: str) -> str:
    """
    Loads context from a summary file for recovery.

    Args:
        file_path: Path to the context summary file

    Returns:
        Content of the file as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"✓ Loaded context from: {file_path}\n")
        return content
    except Exception as e:
        print(f"✗ Error loading context file: {e}")
        sys.exit(1)


def get_user_input() -> tuple[str, bool]:
    """
    Gets user input from command line, either as a prompt or recovery file.

    Returns:
        Tuple of (prompt/context, is_recovery_mode)
    """
    parser = argparse.ArgumentParser(
        description="GLM Writing Agent - Create novels, books, and short stories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fresh start with inline prompt
  python writer.py "Create a collection of sci-fi short stories"

  # Recovery mode from previous context
  python writer.py --recover my_project/.context_summary_20250107_143022.md
        """
    )

    parser.add_argument(
        'prompt',
        nargs='?',
        help='Your writing request (e.g., "Create a mystery novel")'
    )
    parser.add_argument(
        '--recover',
        type=str,
        help='Path to a context summary file to continue from'
    )

    args = parser.parse_args()

    # Check if recovery mode
    if args.recover:
        context = load_context_from_file(args.recover)
        return context, True

    # Check if prompt provided as argument
    if args.prompt:
        return args.prompt, False

    # Interactive prompt
    print("=" * 60)
    print("GLM Writing Agent")
    print("=" * 60)
    print("\nEnter your writing request (or 'quit' to exit):")
    print("Example: Create a collection of 15 sci-fi short stories\n")

    prompt = input("> ").strip()

    if prompt.lower() in ['quit', 'exit', 'q']:
        print("Goodbye!")
        sys.exit(0)

    if not prompt:
        print("Error: Empty prompt. Please provide a writing request.")
        sys.exit(1)

    return prompt, False


def main():
    """Main agent loop."""

    # Get API key
    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        print("Error: ZAI_API_KEY environment variable not set.")
        print("Please set your API key: export ZAI_API_KEY='your-key-here'")
        sys.exit(1)

    # Debug: Show that key is loaded (masked for security)
    if len(api_key) > 8:
        print(f"✓ API Key loaded: {api_key[:4]}...{api_key[-4:]}")
    else:
        print(f"⚠️  Warning: API key seems too short ({len(api_key)} chars)")

    # Initialize GLM client (coding plan endpoint)
    client = ZaiClient(
        api_key=api_key,
        base_url="https://api.z.ai/api/coding/paas/v4"
    )

    print(f"✓ GLM-4.7 client initialized\n")

    # Get user input
    user_prompt, is_recovery = get_user_input()

    # Initialize messages list with dictionaries (OpenAI format)
    messages: List[Dict[str, Any]] = []

    # Add initial user message
    if is_recovery:
        initial_message = f"[RECOVERED CONTEXT]\n\n{user_prompt}\n\n[END RECOVERED CONTEXT]\n\nPlease continue the work from where we left off."
        print("🔄 Recovery mode: Continuing from previous context\n")
    else:
        initial_message = user_prompt
        print(f"\n📝 Task: {user_prompt}\n")

    messages.append({
        "role": "user",
        "content": initial_message
    })

    # Get tool definitions and mapping
    tools = get_tool_definitions()
    tool_map = get_tool_map()

    # Get system prompt
    system_instruction = get_system_prompt()

    print("=" * 60)
    print("Starting GLM Writing Agent")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    print(f"Max iterations: {MAX_ITERATIONS}")
    print(f"Context limit: {TOKEN_LIMIT:,} tokens")
    print(f"Auto-compression at: {COMPRESSION_THRESHOLD:,} tokens")
    print("=" * 60 + "\n")

    # Main agent loop
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n{'─' * 60}")
        print(f"Iteration {iteration}/{MAX_ITERATIONS}")
        print(f"{'─' * 60}")

        # Check token count before making API call
        try:
            token_count = estimate_token_count(messages)
            print(f"📊 Current tokens: {token_count:,}/{TOKEN_LIMIT:,} ({token_count/TOKEN_LIMIT*100:.1f}%)")

            # Trigger compression if approaching limit
            if token_count >= COMPRESSION_THRESHOLD:
                print(f"\n⚠️  Approaching token limit! Compressing context...")
                compression_result = compress_context_impl(
                    messages=[{"role": "system", "content": system_instruction}] + messages,
                    client=client,
                    model=MODEL_NAME,
                    keep_recent=10
                )

                if "compressed_messages" in compression_result:
                    # Rebuild messages from compressed messages (remove system message)
                    new_messages = []
                    for msg in compression_result["compressed_messages"]:
                        if msg.get("role") == "system":
                            continue
                        new_messages.append(msg)
                    messages = new_messages
                    print(f"✓ {compression_result['message']}")
                    print(f"✓ Estimated tokens saved: ~{compression_result.get('tokens_saved', 0):,}")
                    token_count = estimate_token_count(messages)
                    print(f"📊 New token count: {token_count:,}/{TOKEN_LIMIT:,}\n")

        except Exception as e:
            print(f"⚠️  Warning: Could not estimate token count: {e}")
            token_count = 0

        # Auto-backup every N iterations
        if iteration % BACKUP_INTERVAL == 0:
            print(f"💾 Auto-backup (iteration {iteration})...")
            try:
                compression_result = compress_context_impl(
                    messages=[{"role": "system", "content": system_instruction}] + messages,
                    client=client,
                    model=MODEL_NAME,
                    keep_recent=len(messages)
                )
                if compression_result.get("summary_file"):
                    print(f"✓ Backup saved: {os.path.basename(compression_result['summary_file'])}\n")
            except Exception as e:
                print(f"⚠️  Warning: Backup failed: {e}\n")

        # Build full messages with system instruction
        full_messages = [{"role": "system", "content": system_instruction}] + messages

        # Call the model
        try:
            print("🤖 Calling GLM-4.7 model...\n")

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=full_messages,
                temperature=1.0,
                extra_body={
                    "tools": tools
                }
            )

            # Process the response
            content_text = ""
            function_calls_list = []

            # Get the first choice's message
            choice = response.choices[0]
            message = choice.message

            # Extract content
            if message.content:
                content_text = message.content

            # Extract tool calls
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    function_calls_list.append({
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "args": json.loads(tool_call.function.arguments)
                    })

            # Display content
            if content_text:
                print("💬 Response:")
                print("-" * 60)
                print(content_text)
                print("-" * 60 + "\n")

            # Display function calls
            if function_calls_list:
                print("🔧 Function calls detected:")
                print("─" * 60)
                for fc in function_calls_list:
                    print(f"  → {fc['name']}")

            # Append assistant message to conversation (without tool_calls to avoid serialization issues)
            messages.append({
                "role": "assistant",
                "content": content_text
            })

            # Check if the model called any functions
            if not function_calls_list:
                print("=" * 60)
                print("✅ TASK COMPLETED")
                print("=" * 60)
                print(f"Completed in {iteration} iteration(s)")
                print("=" * 60)
                break

            # Handle function calls
            print(f"\n🔧 Model decided to call {len(function_calls_list)} tool(s):")

            # Process each tool call
            for fc in function_calls_list:
                func_name = fc["name"]
                func_args = fc["args"]
                tool_call_id = fc["id"]

                print(f"\n  → {func_name}")
                print(f"    Arguments: {json.dumps(func_args, ensure_ascii=False, indent=6)}")

                # Get the tool implementation
                tool_func = tool_map.get(func_name)

                if not tool_func:
                    result = f"Error: Unknown tool '{func_name}'"
                    print(f"    ✗ {result}")
                else:
                    # Special handling for compress_context (needs extra params)
                    if func_name == "compress_context":
                        result_data = compress_context_impl(
                            messages=[{"role": "system", "content": system_instruction}] + messages,
                            client=client,
                            model=MODEL_NAME,
                            keep_recent=10
                        )
                        result = result_data.get("message", "Compression completed")
                    else:
                        # Call the tool with its arguments
                        result = tool_func(**func_args)

                    # Print result (truncate if too long)
                    if len(str(result)) > 200:
                        print(f"    ✓ {str(result)[:200]}...")
                    else:
                        print(f"    ✓ {result}")

                # Add tool result as a tool role message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(result)
                })

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user. Saving context...")
            try:
                compression_result = compress_context_impl(
                    messages=[{"role": "system", "content": system_instruction}] + messages,
                    client=client,
                    model=MODEL_NAME,
                    keep_recent=len(messages)
                )
                if compression_result.get("summary_file"):
                    print(f"✓ Context saved to: {compression_result['summary_file']}")
                    print(f"\nTo resume, run:")
                    print(f"  python writer.py --recover {compression_result['summary_file']}")
            except:
                pass
            sys.exit(0)

        except Exception as e:
            print(f"\n✗ Error during iteration {iteration}: {e}")
            print(f"Attempting to continue...\n")
            continue

    # If we hit max iterations
    if iteration >= MAX_ITERATIONS:
        print("\n" + "=" * 60)
        print("⚠️  MAX ITERATIONS REACHED")
        print("=" * 60)
        print(f"\nReached maximum of {MAX_ITERATIONS} iterations.")
        print("Saving final context...")

        try:
            compression_result = compress_context_impl(
                messages=[{"role": "system", "content": system_instruction}] + messages,
                client=client,
                model=MODEL_NAME,
                keep_recent=len(messages)
            )
            if compression_result.get("summary_file"):
                print(f"✓ Context saved to: {compression_result['summary_file']}")
                print(f"\nTo resume, run:")
                print(f"  python writer.py --recover {compression_result['summary_file']}")
        except Exception as e:
            print(f"✗ Error saving context: {e}")


if __name__ == "__main__":
    main()
