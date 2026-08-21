"""
ask-anything layer over the marts/kpi layer, running fully local via ollama
-- no api key, no billing, nothing leaves this machine.

setup:
    1. install ollama: https://ollama.com
    2. ollama pull qwen2.5-coder:7b
    3. ollama serve   (usually already running as a background service)

    python ask/ask_anything.py
    > what were gross sales by channel last month?
"""
import json
import duckdb
import re
from openai import OpenAI

DB_PATH = "warehouse.duckdb"
MODEL = "qwen2.5-coder:7b"

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")  # key unused, ollama doesn't check it

RUN_SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "run_sql_query",
        "description": (
            "Run a read-only SQL query against the DuckDB warehouse to "
            "answer the user's question. Only query marts.* or clean.* tables."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The DuckDB SQL query to run."},
            },
            "required": ["sql"],
        },
    },
}


def get_schema(con) -> str:
    rows = con.sql("""
        SELECT table_schema, table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema IN ('marts', 'clean')
        ORDER BY table_schema, table_name, ordinal_position
    """).fetchall()
    lines, current = [], None
    for schema, table, col, dtype in rows:
        key = f"{schema}.{table}"
        if key != current:
            lines.append(f"\n{key}")
            current = key
        lines.append(f"  {col} ({dtype})")
    return "\n".join(lines)


def get_kpi_catalogue() -> str:
    try:
        return open("kpi_catalogue/KPI_CATALOGUE.md", encoding="utf-8").read()
    except FileNotFoundError:
        return "(catalogue not found)"


def build_system_prompt(schema: str, catalogue: str) -> str:
    return f"""You answer questions about Kestrel Provisions' sales, cold
chain, and warehouse data by running SQL against a DuckDB warehouse.

Rules:
- Always use the run_sql_query tool to answer any question about the
  data. Never answer from assumption or memory.
- Use table and column names EXACTLY as listed below -- do not guess or
  invent generic-sounding names (e.g. date_key, order_value_gross on
  fact_sales). If you're not sure a column exists, check the list again.
- Only query tables in the marts or clean schemas below. Never query
  staging or read raw files directly -- those aren't cleaned or joined.
- Prefer reusing the exact logic already defined in the KPI catalogue
  below when a question matches one of its metrics (e.g. use qty, not
  qty_eaches, for revenue -- see the Gross Sales entry for why).
- If a question can't be answered from this schema (e.g. anything asking
  to break results down "by carrier"), say so directly and explain the
  gap instead of guessing or joining something that doesn't exist.
- After the tool result comes back, explain the answer in plain English.

Schema (marts.* and clean.* only):
{schema}

KPI catalogue (existing, validated metric definitions):
{catalogue}
"""


def run_query(con, sql: str):
    try:
        return con.sql(sql).df().to_csv(index=False), False
    except Exception as e:
        return str(e), True


MAX_TOOL_ROUNDS = 3


def ask(con, system_prompt: str, question: str):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        print("...thinking (local model, can take a minute or two)...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=[RUN_SQL_TOOL],
            temperature=0,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            print(f"\n{message.content}\n")
            return

        messages.append(message.model_dump())

        for call in message.tool_calls:
            sql = json.loads(call.function.arguments)["sql"]
            print(f"\n--- SQL ---\n{sql}\n")
            output, is_error = run_query(con, sql)
            print(f"--- result ---\n{output}\n")
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": output,
            })

    print(f"\ngave up after {MAX_TOOL_ROUNDS} attempts -- the model kept "
          f"generating SQL that didn't match the real schema. try a more "
          f"specific question, or see the errors above.\n")


def main():
    con = duckdb.connect(DB_PATH, read_only=True)
    system_prompt = build_system_prompt(get_schema(con), get_kpi_catalogue())

    print("ask-anything (local, via ollama) -- type a question, or 'exit' to quit.")
    while True:
        question = input("\n> ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue
        try:
            ask(con, system_prompt, question)
        except Exception as e:
            print(f"error talking to ollama -- is `ollama serve` running? ({e})")


if __name__ == "__main__":
    main()
