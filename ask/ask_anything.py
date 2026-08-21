"""
ask-anything layer over the marts/kpi layer. the cfo's one hard rule: if
it can't show the sql it ran, it doesn't count -- so every answer here
prints the query BEFORE the result, always, not just when claude mentions it.

needs anthropic credentials available (ANTHROPIC_API_KEY, or `ant auth login`).

    python ask/ask_anything.py
    > what were gross sales by channel last month?
"""
import duckdb
import anthropic

DB_PATH = "warehouse.duckdb"
MODEL = "claude-opus-5"

RUN_SQL_TOOL = {
    "name": "run_sql_query",
    "description": (
        "Run a read-only SQL query against the DuckDB warehouse to answer "
        "the user's question. Only query marts.* or clean.* tables."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "The DuckDB SQL query to run."},
        },
        "required": ["sql"],
        "additionalProperties": False,
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


def ask(client, con, system_prompt: str, question: str):
    messages = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            tools=[RUN_SQL_TOOL],
            messages=messages,
        )

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            text = next((b.text for b in response.content if b.type == "text"), "")
            print(f"\n{text}\n")
            return

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for call in tool_calls:
            sql = call.input["sql"]
            print(f"\n--- SQL ---\n{sql}\n")
            output, is_error = run_query(con, sql)
            print(f"--- result ---\n{output}\n")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": output,
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": tool_results})


def main():
    con = duckdb.connect(DB_PATH, read_only=True)
    client = anthropic.Anthropic()
    system_prompt = build_system_prompt(get_schema(con), get_kpi_catalogue())

    print("ask-anything -- type a question, or 'exit' to quit.")
    while True:
        question = input("\n> ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue
        try:
            ask(client, con, system_prompt, question)
        except anthropic.AuthenticationError:
            print("no anthropic credentials found -- set ANTHROPIC_API_KEY "
                  "or run `ant auth login`.")
            break


if __name__ == "__main__":
    main()
