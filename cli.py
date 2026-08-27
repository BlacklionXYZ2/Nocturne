"""
Local Agent & VTuber Management Center - Interactive CLI
=========================================================
Terminal-based management interface with rich colored outputs, model selection,
live ReAct thought streaming, and memory inspection.
"""

import sys
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from backend.model_scanner import ModelScanner
from backend.llama_manager import LlamaServerManager
from backend.params import LlamaServerParams
from agent.memory import MemoryManager
from agent.core import LocalAgent
from server.app import load_config, save_config

console = Console()


async def main():
    cfg = load_config()
    paths = cfg.get("paths", {})
    scanner = ModelScanner(paths.get("models_dir", r"C:\Users\oscar\Desktop\Models"))
    llama_mgr = LlamaServerManager(
        llama_server_path=paths.get("llama_server_path", r"C:\llama.cpp\llama-server.exe"),
        host=cfg.get("server", {}).get("host", "127.0.0.1"),
        port=cfg.get("server", {}).get("llama_port", 8080)
    )
    memory_mgr = MemoryManager(
        memory_dir=paths.get("memory_dir", "memory"),
        conversations_dir=paths.get("conversations_dir", "conversations")
    )
    agent = LocalAgent(base_url=llama_mgr.base_url, memory_manager=memory_mgr)

    console.print(Panel.fit(
        "[bold cyan]Local Agent & VTuber Management Center (CLI Mode)[/bold cyan]\n"
        "[dim]Model management, autonomous tasks, and markdown memory engine[/dim]",
        border_style="cyan"
    ))

    while True:
        status_text = "[green]RUNNING[/green]" if llama_mgr.is_running else "[red]STOPPED[/red]"
        current_model = llama_mgr.get_status().get("current_model") or "None"
        console.print(f"\n[bold]Server Status:[/bold] {status_text} | [bold]Loaded Model:[/bold] {current_model}")

        table = Table(title="Select an Option", show_header=False, box=None)
        table.add_row("[1]", "List / Select Model from Desktop")
        table.add_row("[2]", "Start / Restart llama-server (ROCm GPU 9070 XT)")
        table.add_row("[3]", "Stop llama-server")
        table.add_row("[4]", "Run Autonomous Agent Task")
        table.add_row("[5]", "View / Edit Markdown Memory Files")
        table.add_row("[6]", "Exit")
        console.print(table)

        choice = Prompt.ask("Choose an action", choices=["1", "2", "3", "4", "5", "6"], default="1")

        if choice == "1":
            models = scanner.scan()
            if not models:
                console.print("[yellow]No .gguf models found in Desktop/Models![/yellow]")
                continue

            m_table = Table(title="Available GGUF Models", header_style="bold magenta")
            m_table.add_column("#", style="dim", width=4)
            m_table.add_column("Model Name", style="bold")
            m_table.add_column("Size", justify="right")
            m_table.add_column("Quant", style="cyan")
            m_table.add_column("Suggested Role", style="green")

            for idx, m in enumerate(models, start=1):
                m_table.add_row(
                    str(idx),
                    m["name"],
                    f"{m['size_gb']} GB",
                    m["quantization"],
                    m["recommended_role"]
                )
            console.print(m_table)

            sel = Prompt.ask("Select model number to load (or press Enter to cancel)", default="")
            if sel.isdigit() and 1 <= int(sel) <= len(models):
                chosen_model = models[int(sel) - 1]
                console.print(f"[cyan]Loading {chosen_model['name']} onto ROCm GPU...[/cyan]")
                params = LlamaServerParams(
                    ctx_size=8192 if chosen_model["recommended_role"] == "Agent" else 16384,
                    n_gpu_layers=99,
                    device="ROCm0",
                    flash_attn=True
                )
                success = llama_mgr.start(chosen_model["full_path"], params)
                if success:
                    console.print("[bold green]✓ Model loaded successfully![/bold green]")
                else:
                    console.print("[bold red]✗ Failed to start llama-server.[/bold red]")

        elif choice == "2":
            if not llama_mgr.current_model_path:
                console.print("[yellow]Please select a model first (Option 1).[/yellow]")
            else:
                llama_mgr.restart()

        elif choice == "3":
            llama_mgr.stop()
            console.print("[yellow]llama-server stopped.[/yellow]")

        elif choice == "4":
            if not llama_mgr.is_running:
                console.print("[yellow]llama-server is not running. Please start a model first.[/yellow]")
                continue

            task_prompt = Prompt.ask("\n[bold cyan]Enter task for the agent[/bold cyan]")
            if not task_prompt.strip():
                continue

            console.print("\n[bold green]=== Agent Task Execution Started ===[/bold green]\n")
            async for event in agent.run_task(task_prompt, max_steps=20):
                ev_type = event["type"]
                data = event.get("data", "")
                if ev_type == "thought":
                    console.print(Panel(data, title="[bold blue]Agent Thought[/bold blue]", border_style="blue"))
                elif ev_type == "tool_call":
                    console.print(f"[bold yellow]→ Calling Tool:[/bold yellow] [cyan]{data.get('name')}[/cyan] with {data.get('arguments')}")
                elif ev_type == "tool_result":
                    console.print(Panel(data.get("result", ""), title=f"[bold dim]Result: {data.get('name')}[/bold dim]", border_style="dim"))
                elif ev_type == "final_answer":
                    console.print(Panel(data, title="[bold green]Final Answer[/bold green]", border_style="green"))
                elif ev_type == "error":
                    console.print(f"[bold red]Error: {data}[/bold red]")

        elif choice == "5":
            files = memory_mgr.list_memory_files()
            mem_table = Table(title="Markdown Memory Files", header_style="bold green")
            mem_table.add_column("#", width=4)
            mem_table.add_column("Filename", style="bold")
            mem_table.add_column("Size", justify="right")
            for idx, f in enumerate(files, start=1):
                mem_table.add_row(str(idx), f["filename"], f"{f['size_bytes']} bytes")
            console.print(mem_table)

            f_sel = Prompt.ask("Select file to read (or Enter to cancel)", default="")
            if f_sel.isdigit() and 1 <= int(f_sel) <= len(files):
                f_name = files[int(f_sel) - 1]["filename"]
                content = memory_mgr.read_memory_file(f_name)
                console.print(Panel(content, title=f_name, border_style="green"))

        elif choice == "6":
            llama_mgr.stop()
            console.print("[dim]Goodbye![/dim]")
            sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
