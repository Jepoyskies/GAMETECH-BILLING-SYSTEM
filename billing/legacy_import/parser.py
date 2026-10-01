"""Read rows out of a legacy MySQL dump. No Django, no database, no ORM.

Kept separate from the management command so it can be exercised against a
real dump in isolation -- every import bug so far lived in this layer, and
none of it needs a database to test.

Two dump layouts are supported:
  * mysqldump  -- ``INSERT INTO `t` VALUES (..),(..);`` all on one line, and
                  no column list in the statement.
  * phpMyAdmin -- ``INSERT INTO `t` (`c1`,`c2`) VALUES`` followed by one
                  tuple per line, terminated by ';'.

Rows are keyed by COLUMN NAME, never by position. The legacy schema gained a
column part-way through this project (barangay_id at index 9), which silently
shifted every positional field after it -- reading a barangay id as a
customer's billing status. Name mapping makes that class of corruption
impossible.
"""

import csv
import io
import re

INSERT_RE = re.compile(r"^INSERT\s+INTO\s+`?([A-Za-z0-9_]+)`?")
COLUMN_LIST_RE = re.compile(r"^\s*\(([^)]*)\)\s*VALUES", re.I)
CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z0-9_]+)`?\s*\((.*?)\n\)\s*ENGINE",
    re.I | re.S,
)


def split_value_tuples(payload):
    """Split a VALUES payload into individual "(...)" tuple strings.

    A naive split on "," or "),(" corrupts any value containing those
    characters, so this walks the string tracking quote state and paren depth.
    Handles MySQL backslash escaping and '' doubling, and returns tuples that
    are safe to hand to csv.reader.
    """
    tuples = []
    buf = []
    depth = 0
    in_str = False
    i = 0
    n = len(payload)
    while i < n:
        ch = payload[i]

        if in_str:
            if ch == "\\" and i + 1 < n:
                nxt = payload[i + 1]
                if nxt == "'":
                    # MySQL escapes an apostrophe as \'. Python's csv module
                    # knows nothing about MySQL escaping and would read that
                    # quote as a quote toggle, shattering
                    # "Eddie\'s Compound, Vamenta Blvd" into four fields.
                    # Double it instead: csv decodes it back to one apostrophe.
                    buf.append("''")
                else:
                    buf.append(nxt)
                i += 2
                continue
            buf.append(ch)
            if ch == "'":
                if i + 1 < n and payload[i + 1] == "'":   # doubled quote
                    buf.append(payload[i + 1])
                    i += 2
                    continue
                in_str = False
            i += 1
            continue

        if ch == "'":
            in_str = True
            buf.append(ch)
            i += 1
            continue

        if ch == "(":
            if depth == 0:
                buf = []
            depth += 1
            if depth > 1:
                buf.append(ch)
            i += 1
            continue

        if ch == ")":
            depth -= 1
            if depth == 0:
                tuples.append("(" + "".join(buf) + ")")
                buf = []
            else:
                buf.append(ch)
            i += 1
            continue

        if depth > 0:
            buf.append(ch)   # keep the commas separating values
        i += 1

    return tuples


def parse_row(tup):
    """Turn one '(...)' tuple string into a list of values."""
    line = tup.strip()
    if line.startswith("("):
        line = line[1:]
    if line.endswith(");"):
        line = line[:-2]
    elif line.endswith("),"):
        line = line[:-2]
    elif line.endswith(")"):
        # split_value_tuples() already balanced the parens, so a trailing ")"
        # is always the tuple's own closing paren, never part of a value.
        line = line[:-1]
    try:
        row = next(csv.reader(io.StringIO(line), quotechar="'", skipinitialspace=True))
    except StopIteration:
        return []
    return [None if c == "NULL" else c for c in row]


def columns_from_create_table(sql_file_path):
    """Map table -> ordered column names, from the CREATE TABLE statements.

    Fallback for dumps that omit the column list in their INSERT statements
    (plain mysqldump). phpMyAdmin dumps always include it.
    """
    cols = {}
    with open(sql_file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.lstrip().upper().startswith("CREATE TABLE"):
                continue
            # CREATE TABLE wraps across lines. Read until a line that is just
            # the closing paren -- stopping at the first ")" would trip over
            # "varchar(50)" and cut the block short.
            block = [line]
            while not re.search(r"^\s*\)\s*(ENGINE|;|$)", block[-1], re.M | re.I):
                nxt = f.readline()
                if not nxt:
                    break
                block.append(nxt)
            m = CREATE_TABLE_RE.search("".join(block))
            if not m:
                continue
            names = re.findall(r"^\s*`([A-Za-z0-9_]+)`", m.group(2), re.M)
            if names:
                cols[m.group(1)] = names
    return cols


def iter_rows(sql_file_path):
    """Yield (table_name, {column_name: value}) for every row in the dump."""
    fallback_cols = columns_from_create_table(sql_file_path)

    with open(sql_file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            m = INSERT_RE.match(stripped)
            if not m:
                continue
            table = m.group(1)

            # The column list (if any) sits AFTER `INSERT INTO `table``.
            cm = COLUMN_LIST_RE.match(stripped[m.end():])
            if cm:
                names = [c.strip().strip("`") for c in cm.group(1).split(",")]
                start = m.end() + cm.end()
            else:
                names = fallback_cols.get(table)
                vidx = stripped.upper().find("VALUES")
                if vidx == -1 or not names:
                    continue
                start = vidx + len("VALUES")

            # Tuples may continue on following lines (phpMyAdmin style).
            # Accumulate in a list: repeated string += on a multi-megabyte
            # statement is quadratic and gets the process OOM-killed.
            parts = [stripped[start:]]
            found_end = ";" in parts[0]
            while not found_end:
                nxt = f.readline()
                if not nxt:
                    break
                nxt = nxt.rstrip()
                parts.append(nxt)
                found_end = ";" in nxt
            buffer = "\n".join(parts)

            for tup in split_value_tuples(buffer.strip().rstrip(";").strip()):
                values = parse_row(tup)
                if not values:
                    continue
                if len(values) != len(names):
                    raise ValueError(
                        f"Table `{table}`: header lists {len(names)} columns but a "
                        f"row has {len(values)}. Dump is malformed -- refusing to "
                        f"import rather than guess."
                    )
                yield table, dict(zip(names, values))
