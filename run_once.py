# Entrypoint: initialize storage if needed and execute one monitoring run.

from news_agent.agent import run_monitoring_once


def main() -> None:
    run_id = run_monitoring_once()
    print(f"Monitoring run completed: run_id={run_id}")


if __name__ == "__main__":
    main()
