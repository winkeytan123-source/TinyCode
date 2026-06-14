"""Interactive REPL - the user-facing terminal interface."""

import sys
import os
import argparse

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings

from .agent import Agent
from .llm import LLM, LiteLLM
from .config import Config
from .session import save_session, load_session, list_sessions
from . import __version__

console = Console()


def _parse_args():
    p = argparse.ArgumentParser(
        prog="corecoder",
        description="Minimal AI coding agent. Works with any OpenAI-compatible LLM.",
    )
    p.add_argument("-m", "--model", help="Model name (default: $CORECODER_MODEL or gpt-4o)")
    p.add_argument("--base-url", help="API base URL (default: $OPENAI_BASE_URL)")
    p.add_argument("--api-key", help="API key (default: $OPENAI_API_KEY)")
    p.add_argument("-p", "--prompt", help="One-shot prompt (non-interactive mode)")
    p.add_argument("-r", "--resume", metavar="ID", help="Resume a saved session")
    p.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args()


def main():
    args = _parse_args()
    config = Config.from_env()

    # CLI args override env vars
    if args.model:
        config.model = args.model
        # 同步切换到该模型对应的 api_key 和 base_url
        profile = config.get_profile(args.model)
        if profile:
            config.api_key = profile.api_key
            config.base_url = profile.base_url
    # 显式传入的 --base-url 和 --api-key 优先级最高
    if args.base_url:
        config.base_url = args.base_url
    if args.api_key:
        config.api_key = args.api_key

    if not config.api_key:
        console.print("[red bold]No API key found.[/]")
        console.print(
            "Set one of: OPENAI_API_KEY, DEEPSEEK_API_KEY, or CORECODER_API_KEY\n"
            "\nExamples:\n"
            "  # OpenAI\n"
            "  export OPENAI_API_KEY=sk-...\n"
            "\n"
            "  # DeepSeek\n"
            "  export OPENAI_API_KEY=sk-... OPENAI_BASE_URL=https://api.deepseek.com\n"
            "\n"
            "  # Ollama (local)\n"
            "  export OPENAI_API_KEY=ollama OPENAI_BASE_URL=http://localhost:11434/v1 CORECODER_MODEL=qwen2.5-coder\n"
        )
        sys.exit(1)

    llm_cls = LiteLLM if config.provider == "litellm" else LLM
    llm = llm_cls(
        model=config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    agent = Agent(llm=llm, max_context_tokens=config.max_context_tokens)

    # resume saved session
    if args.resume:
        loaded = load_session(args.resume)
        if loaded:
            agent.messages, loaded_model = loaded
            # restore the model from the saved session unless overridden by CLI
            if not args.model:
                agent.llm.model = loaded_model
                config.model = loaded_model
            console.print(f"[green]Resumed session: {args.resume} (model: {agent.llm.model})[/green]")
        else:
            console.print(f"[red]Session '{args.resume}' not found.[/red]")
            sys.exit(1)

    # one-shot mode
    if args.prompt:
        _run_once(agent, args.prompt)
        return

    # interactive REPL
    _repl(agent, config, llm_cls)


def _run_once(agent: Agent, prompt: str):
    """Non-interactive: run one prompt and exit."""
    def on_token(tok):
        print(tok, end="", flush=True)

    def on_tool(name, kwargs):
        # 在终端运行工具时，打印工具名称和参数
        console.print(f"\n[dim]> {name}({_brief(kwargs)})[/dim]")

    agent.chat(prompt, on_token=on_token, on_tool=on_tool)
    print()


def _repl(agent: Agent, config: Config, llm_cls=None):
    """Interactive read-eval-print loop."""
    if llm_cls is None:
        llm_cls = LLM
    console.print(Panel(
        f"[bold]CoreCoder[/bold] v{__version__}\n"
        f"Model: [cyan]{config.model}[/cyan]"
        + (f"  Base: [dim]{config.base_url}[/dim]" if config.base_url else "")
        + "\nType [bold]/help[/bold] for commands, [bold]Ctrl+C[/bold] to cancel, [bold]quit[/bold] to exit.",
        border_style="blue",
    ))

    # 用户可以通过上下方向键调出以前输入过的 prompt，甚至在关闭终端重新打开后依然有效。
    hist_path = os.path.expanduser("~/.corecoder_history")
    history = FileHistory(hist_path)

    # Enter submits, Escape+Enter inserts a newline (for pasting code blocks etc.)
    kb = KeyBindings()

    @kb.add("enter")
    def _submit(event):
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")
    def _newline(event):
        event.current_buffer.insert_text("\n")

    while True:
        try:
            user_input = pt_prompt(
                "You > ",
                history=history,
                multiline=True,
                key_bindings=kb,
                prompt_continuation="...  ",
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye!")
            break

        if not user_input:
            continue

        # built-in commands
        if user_input.lower() in ("quit", "exit", "/quit", "/exit"):
            break
        if user_input == "/help":
            _show_help()
            continue
        if user_input == "/reset":
            agent.reset()
            console.print("[yellow]Conversation reset.[/yellow]")
            continue
        if user_input == "/tokens":
            p = agent.llm.total_prompt_tokens
            c = agent.llm.total_completion_tokens
            line = f"Tokens: [cyan]{p}[/cyan] prompt + [cyan]{c}[/cyan] completion = [bold]{p+c}[/bold] total"
            cost = agent.llm.estimated_cost
            if cost is not None:
                line += f"  (~${cost:.4f})"
            console.print(line)
            continue
        if user_input == "/model" or user_input.startswith("/model "):
            new_model = user_input[7:].strip() if user_input.startswith("/model ") else ""
            if new_model:
                # 查找模型对应的配置
                profile = config.get_profile(new_model)
                if profile:
                    # 找到配置，同步切换 model、api_key、base_url
                    config.model = new_model
                    config.api_key = profile.api_key
                    config.base_url = profile.base_url
                    # 重建 LLM client 以应用新的 api_key 和 base_url
                    agent.llm = llm_cls(
                        model=config.model,
                        api_key=config.api_key,
                        base_url=config.base_url,
                        temperature=config.temperature,
                        max_tokens=config.max_tokens,
                    )
                    console.print(f"[green]Switched to model:[/green] [cyan]{new_model}[/cyan]")
                    console.print(f"  Base URL: [dim]{config.base_url}[/dim]")
                    console.print(f"  API Key:  [dim]{config.api_key[:8]}...{config.api_key[-4:]}[/dim]")
                else:
                    # 未找到配置，仅切换模型名，保持当前 url 和 key
                    agent.llm.model = new_model
                    config.model = new_model
                    console.print(f"[yellow]Warning: No profile found for '{new_model}', using current API key & URL[/yellow]")
                    console.print(f"  Model:    [cyan]{new_model}[/cyan]")
                    console.print(f"  Base URL: [dim]{config.base_url}[/dim]")
                    console.print(f"[dim]Tip: Add MODEL_<ALIAS>_NAME/API_KEY/BASE_URL to .env to configure this model[/dim]")
            else:
                # 显示当前模型信息和所有可用模型
                console.print(f"Current model: [cyan]{config.model}[/cyan]")
                console.print(f"  Base URL: [dim]{config.base_url}[/dim]")
                available = config.list_models()
                if available:
                    console.print(f"\n[bold]Available models ({len(available)}):[/bold]")
                    for m in available:
                        marker = " [green]◀ active[/green]" if m == config.model else ""
                        p = config.get_profile(m)
                        console.print(f"  [cyan]{m}[/cyan]{marker}")
                        console.print(f"    URL: [dim]{p.base_url}[/dim]")
            continue
        if user_input == "/compact":
            from .context import estimate_tokens
            before = estimate_tokens(agent.messages)
            compressed = agent.context.maybe_compress(agent.messages, agent.llm)
            after = estimate_tokens(agent.messages)
            if compressed:
                console.print(f"[green]Compressed: {before} → {after} tokens ({len(agent.messages)} messages)[/green]")
            else:
                console.print(f"[dim]Nothing to compress ({before} tokens, {len(agent.messages)} messages)[/dim]")
            continue
        if user_input == "/save":
            sid = save_session(agent.messages, config.model)
            console.print(f"[green]Session saved: {sid}[/green]")
            console.print(f"Resume with: corecoder -r {sid}")
            continue
        # 显示本次会话中修改过的文件列表（如果有的话）。这依赖于 tools/edit.py 中的 _changed_files 集合，该集合在编辑工具被调用时更新。
        if user_input == "/diff":
            from .tools.edit import _changed_files
            if not _changed_files:
                console.print("[dim]No files modified this session.[/dim]")
            else:
                console.print(f"[bold]Files modified this session ({len(_changed_files)}):[/bold]")
                for f in sorted(_changed_files):
                    console.print(f"  [cyan]{f}[/cyan]")
            continue
        if user_input == "/sessions":
            sessions = list_sessions()
            if not sessions:
                console.print("[dim]No saved sessions.[/dim]")
            else:
                for s in sessions:
                    console.print(f"  [cyan]{s['id']}[/cyan] ({s['model']}, {s['saved_at']}) {s['preview']}")
            continue

        # /skills 快捷命令：列出所有可用 skill
        if user_input == "/skills":
            skills = agent.skill_manager.list_skills()
            if not skills:
                console.print("[dim]No skills available.[/dim]")
            else:
                console.print(f"[bold]Available Skills ({len(skills)}):[/bold]")
                for s in skills:
                    status = "[green]✓ loaded[/green]" if s.is_loaded() else "[dim]○ not loaded[/dim]"
                    console.print(f"  [cyan]/{s.name}[/cyan] {status}")
                    console.print(f"    {s.description}")
            continue

        # /skill_name 手动触发 Skill（需放在所有内置命令之后）
        if user_input.startswith("/"):
            parts = user_input[1:].strip().split(None, 1)
            skill_name = parts[0]
            inline_task = parts[1] if len(parts) > 1 else ""
            skill = agent.skill_manager.get(skill_name)
            if skill is not None:
                content = skill.load()
                console.print(f"[green]✓ Skill [bold]{skill.name}[/bold] loaded manually[/green]")
                # 如果命令后面没有附带任务，则提示用户输入
                if inline_task:
                    task_input = inline_task
                else:
                    try:
                        task_input = pt_prompt(
                            f"[{skill.name}] > ",
                            history=history,
                            multiline=True,
                            key_bindings=kb,
                            prompt_continuation="...  ",
                        ).strip()
                    except (EOFError, KeyboardInterrupt):
                        console.print("\n[yellow]Cancelled.[/yellow]")
                        continue
                if not task_input:
                    console.print("[dim]No task provided, skill cancelled.[/dim]")
                    continue
                # 将 Skill 指令 + 用户任务一起交给 agent
                user_input = (
                    f"[System: The following skill '{skill.name}' has been "
                    f"manually activated by the user. You MUST follow its instructions.]\n\n"
                    f"{content}\n\n"
                    f"---\n\nUser task: {task_input}"
                )
                # 继续往下走，交给 agent.chat 处理
            else:
                console.print(f"[yellow]Unknown command or skill: /{skill_name}[/yellow]")
                console.print("[dim]Use /help for commands, /skills to list available skills.[/dim]")
                continue

        # call the agent
        streamed: list[str] = []

        def on_token(tok):
            streamed.append(tok)
            print(tok, end="", flush=True)

        def on_tool(name, kwargs):
            console.print(f"\n[dim]> {name}({_brief(kwargs)})[/dim]")

        try:
            response = agent.chat(user_input, on_token=on_token, on_tool=on_tool)
            # 交互模式需要区分流式输出是否成功
            if streamed:
                print()  # newline after streamed tokens
            else:
                # response wasn't streamed (came after tool calls)
                console.print(Markdown(response))
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")


def _show_help():
    console.print(Panel(
        "[bold]Commands:[/bold]\n"
        "  /help          Show this help\n"
        "  /reset         Clear conversation history\n"
        "  /model         Show current model\n"
        "  /model <name>  Switch model mid-conversation\n"
        "  /tokens        Show token usage\n"
        "  /compact       Compress conversation context\n"
        "  /diff          Show files modified this session\n"
        "  /save          Save session to disk\n"
        "  /sessions      List saved sessions\n"
        "  /skills        List available skills\n"
        "  /<skill_name>  Manually activate a skill\n"
        "  quit           Exit CoreCoder\n"
        "\n"
        "[bold]Skills:[/bold]\n"
        "  Passive: describe your task naturally, the agent will load\n"
        "          the matching skill automatically when needed.\n"
        "  Active:  type /<skill_name> to force-load a specific skill,\n"
        "          then enter your task at the prompt.\n"
        "\n"
        "[bold]Input:[/bold]\n"
        "  Enter          Submit message\n"
        "  Esc+Enter      Insert newline (for pasting code)",
        title="CoreCoder Help",
        border_style="dim",
    ))


def _brief(kwargs: dict, maxlen: int = 80) -> str:
    s = ", ".join(f"{k}={repr(v)[:40]}" for k, v in kwargs.items())
    return s[:maxlen] + ("..." if len(s) > maxlen else "")
