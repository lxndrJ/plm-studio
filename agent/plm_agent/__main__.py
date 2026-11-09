import argparse
import json
import os
from pathlib import Path

from plm_agent.runner import PlmAgent
from plm_agent.toolgen import ToolCatalog

AGENT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PLM Studio AI agent (M7) - one prompt, tool loop via LiteLLM"
    )
    parser.add_argument("prompt")
    parser.add_argument("--plm-url", default=os.environ.get("PLM_API_URL", "http://localhost:8000"))
    parser.add_argument(
        "--llm-url", default=os.environ.get("OPENAI_BASE_URL", "http://localhost:4000/v1")
    )
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", "plm-chat"))
    parser.add_argument("--email", default=os.environ.get("PLM_AGENT_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("PLM_AGENT_PASSWORD", ""))
    parser.add_argument("--tools", default=str(AGENT_ROOT / "tools" / "tools.json"))
    parser.add_argument("--system-prompt", default=str(AGENT_ROOT / "prompts" / "system-prompt.md"))
    args = parser.parse_args()

    catalog = ToolCatalog.from_dict(json.loads(Path(args.tools).read_text(encoding="utf-8")))
    agent = PlmAgent(
        plm_base_url=args.plm_url,
        llm_base_url=args.llm_url,
        api_key=args.api_key,
        model=args.model,
        email=args.email,
        password=args.password,
        catalog=catalog,
        system_prompt=Path(args.system_prompt).read_text(encoding="utf-8"),
    )
    print(agent.run(args.prompt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
