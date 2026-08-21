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
- Once a tool result already answers the question, respond in plain text
  with the answer -- do not call the tool again just to double-check a
  result that's already correct.
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


def try_parse_text_tool_call(content: str):
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if obj.get("name") != "run_sql_query":
        return None
    args = obj.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return None
    return args.get("sql")


def normalize_result(csv_text: str) -> frozenset:
    lines = csv_text.strip().splitlines()
    return frozenset(lines[1:])  # drop header, row order doesn't matter


def ask(con, system_prompt: str, question: str):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    last_result = None

    for _ in range(MAX_TOOL_ROUNDS):
        print("...thinking (local model, can take a minute or two)...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=[RUN_SQL_TOOL],
            temperature=0,
        )
        message = response.choices[0].message

        if message.tool_calls:
            sql = json.loads(message.tool_calls[0].function.arguments)["sql"]
        else:
            sql = try_parse_text_tool_call(message.content)

        if sql is None:
            print(f"\n{message.content}\n")
            return

        print(f"\n--- SQL ---\n{sql}\n")
        output, is_error = run_query(con, sql)
        print(f"--- result ---\n{output}\n")

        if not is_error:
            normalized = normalize_result(output)
            if normalized == last_result:
                print("(same result as the last query -- taking this as the answer)\n")
                return
            last_result = normalized

        if message.tool_calls:
            messages.append(message.model_dump())
            messages.append({
                "role": "tool",
                "tool_call_id": message.tool_calls[0].id,
                "content": output,
            })
        else:
            messages.append({"role": "assistant", "content": message.content})
            messages.append({"role": "user", "content": f"Query result:\n{output}"})

    print(f"\ngave up after {MAX_TOOL_ROUNDS} attempts without a final answer "
          f"-- check the queries and results above, one of them may already "
          f"be correct.\n")


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
