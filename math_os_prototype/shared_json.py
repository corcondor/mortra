"""Lossless content-addressed JSON trees; no mathematical simplification.

Container records are shared on disk. Decoding restores ordinary unaliased
JSON trees, so a caller's mutation cannot change a second occurrence.
"""
from hashlib import sha256
import json
import math
from pathlib import Path

SCHEMA = "mortra.shared-json.v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def scalar(value):
    return value is None or type(value) in (str, bool, int) or (type(value) is float and math.isfinite(value))


def pack(value):
    records, memo, active = {}, {}, set()

    def visit(item, depth=0):
        if depth > 256:
            raise ValueError("shared JSON depth budget")
        if scalar(item):
            return item
        if type(item) not in (dict, list):
            raise ValueError("only JSON values can be shared")
        identity = id(item)
        if identity in active:
            raise ValueError("cyclic JSON input")
        if identity in memo:
            return {"ref": memo[identity]}
        active.add(identity)
        if isinstance(item, dict):
            if any(type(k) is not str for k in item):
                raise ValueError("JSON object keys must be strings")
            record = {"kind": "dict", "items": [[k, visit(v, depth+1)] for k, v in item.items()]}
        else:
            record = {"kind": "list", "items": [visit(v, depth+1) for v in item]}
        checksum = digest(record)
        records.setdefault(checksum, record)
        memo[identity] = checksum
        active.remove(identity)
        return {"ref": checksum}

    root = visit(value)
    payload = {"schema": SCHEMA, "root": root, "records": records}
    payload["sha256"] = digest(payload)
    return payload


def unpack(payload, *, max_expanded_items=20_000_000):
    if (type(payload) is not dict or set(payload) != {"schema", "root", "records", "sha256"}
            or payload["schema"] != SCHEMA or type(payload["records"]) is not dict):
        raise ValueError("invalid shared JSON envelope")
    if payload["sha256"] != digest({k: v for k, v in payload.items() if k != "sha256"}):
        raise ValueError("shared JSON envelope changed")
    records = payload["records"]
    if len(records) > 200_000:
        raise ValueError("shared JSON record budget")
    sizes, heights, active = {}, {}, set()

    def validate(token, depth=0):
        if depth > 256:
            raise ValueError("shared JSON depth budget")
        if scalar(token):
            return 1, 0
        if type(token) is not dict or set(token) != {"ref"} or type(token["ref"]) is not str:
            raise ValueError("invalid shared JSON reference")
        checksum = token["ref"]
        if checksum in active or checksum not in records:
            raise ValueError("cyclic or missing shared JSON reference")
        if checksum not in sizes:
            record = records[checksum]
            if (type(record) is not dict or set(record) != {"kind", "items"}
                    or record["kind"] not in ("list", "dict") or type(record["items"]) is not list
                    or digest(record) != checksum):
                raise ValueError("invalid shared JSON record")
            active.add(checksum)
            keys = set()
            size, height = 1, 0
            for entry in record["items"]:
                if record["kind"] == "dict":
                    if (type(entry) is not list or len(entry) != 2 or type(entry[0]) is not str
                            or entry[0] in keys):
                        raise ValueError("invalid or repeated shared JSON key")
                    keys.add(entry[0])
                    count, child_height = validate(entry[1], depth+1)
                else:
                    count, child_height = validate(entry, depth+1)
                size += count
                height = max(height, child_height+1)
                if size > max_expanded_items:
                    raise ValueError("shared JSON expansion budget")
            active.remove(checksum)
            sizes[checksum], heights[checksum] = size, height
        if depth + heights[checksum] > 256:
            raise ValueError("shared JSON depth budget")
        return sizes[checksum], heights[checksum]

    size, _ = validate(payload["root"])
    if size > max_expanded_items:
        raise ValueError("shared JSON expansion budget")
    if set(sizes) != set(records):
        raise ValueError("unreachable shared JSON records")

    # Validate the shared graph before allocating the expanded tree. Materialize
    # each output occurrence once, without copying whole subtrees at every level.
    def materialize(token):
        if scalar(token):
            return token
        record = records[token["ref"]]
        if record["kind"] == "dict":
            return {name: materialize(value) for name, value in record["items"]}
        return [materialize(value) for value in record["items"]]

    return materialize(payload["root"])


def read(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return unpack(data) if isinstance(data, dict) and data.get("schema") == SCHEMA else data


def write(path, data, *, shared=False):
    Path(path).write_text(json.dumps(pack(data) if shared else data, ensure_ascii=False,
                                    allow_nan=False, indent=2)+"\n", encoding="utf-8")
