#!/usr/bin/env python3
# ==============================================================================
# SentinelAI (Action Guardrail) - Architecture Diagram Generator
# Preparation for Aivar Innovations - CIT AI Engineers Task
# ==============================================================================

DIAGRAM = """
================================================================================
                    SENTINELAI (ACTION GUARDRAIL) SYSTEM ARCHITECTURE
================================================================================

              [ USER REQUEST (Natural Language Prompt) ]
                                  |
                                  v
              +----------------------------------------+
              |      React Web Dashboard (Port 8501)   |
              +----------------------------------------+
                                  |
                           POST /request
                                  v
              +----------------------------------------+
              |      FastAPI Web Server (Port 8000)    |
              +----------------------------------------+
                                  |
                                  v
            +--------------------------------------------+
            |           AI Agent (agent.py)              |
            |   Resolves request into structured actions |
            +--------------------------------------------+
                                  |
                  Attempt Online Gemini API (Free-Tier)
                  Fallback to Heuristic Offline Regex Parser
                                  |
                                  v
            +--------------------------------------------+
            |        Guardrail Engine (guardrail.py)     |
            |   Checks action against policies in rules  |
            +--------------------------------------------+
                                  |
                           Reads rules.yaml
                                  v
            +--------------------------------------------+
            |        Evaluation Decision outcome         |
            +--------------------------------------------+
                     /            |            \\
                    /             |             \\
           ALLOWED /      BLOCKED |              \\ PENDING_REVIEW (HITL)
                  /               |               \\
                 v                v                v
          [ Exec Tool ]    [ Block Action ]   [ Review Queue ]
           (tools.py)        (Log & Reject)    (Admin Console)
                 |                |                |
                 |                |                +--- POST /review/approve
                 v                v                |    (Executes tool call)
          +----------------------------------+     |
          |       SQLite DB (Audit Logs)     | <---+
          |     Secure Audit Trail logged    |
          +----------------------------------+

================================================================================
All services (FastAPI Backend, SQLite Database, React Frontend) are dockerized
and orchestrated via Docker Compose, targeting AWS EC2 standard deployments.
================================================================================
"""

def main():
    print(DIAGRAM)

if __name__ == "__main__":
    main()
