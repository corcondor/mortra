"""Deterministic bounded game DSL. No world internals are arguments to the player."""
from collections import deque
from dataclasses import dataclass
import hashlib
import json
import random

ACTIONS = ("MOVE_UP", "MOVE_DOWN", "MOVE_LEFT", "MOVE_RIGHT", "INTERACT", "PICK", "DROP", "PUSH")
DELTAS = ((0, -1), (0, 1), (-1, 0), (1, 0))
TRIGGERS = {"ENTER", "INTERACT", "PICK", "DROP", "PUSH"}
CONDITIONS = {"carrying", "not_carrying", "flag", "active", "counter", "region"}
EFFECTS = {"set_flag", "toggle_flag", "set_active", "set_passability", "toggle_passability",
           "teleport", "give", "take", "consume", "move", "increment", "set_hazard"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def game_hash(genome):
    return hashlib.sha256(canonical(genome).encode()).hexdigest()


def validate(genome):
    """Reject malformed DSL before any evaluator runs it; all dynamic domains finite."""
    def need(ok, message):
        if not ok:
            raise ValueError(message)

    need(genome.get("version") == 1, "version")
    board = genome["board"]
    w, h = board["width"], board["height"]
    need(type(w) is int and type(h) is int and w in (12, 16, 24, 32) and w == h, "board size")
    def cell(p):
        return isinstance(p, (list, tuple)) and len(p) == 2 and all(type(v) is int for v in p) and 0 <= p[0] < w and 0 <= p[1] < h

    need(all(cell(p) for p in board["walls"]), "wall position")
    walls = {tuple(p) for p in board["walls"]}
    need(len(walls) == len(board["walls"]), "duplicate walls")
    need(cell(genome["start"]) and cell(genome["goal"]), "start/goal")
    need(tuple(genome["start"]) not in walls and tuple(genome["goal"]) not in walls, "blocked start/goal")
    need(genome["start"] != genome["goal"], "initial success prohibited")
    need(genome["action_set"] == list(ACTIONS), "action alphabet")
    need(all(type(v) is bool for v in genome["flags"]), "flags")
    objs = genome["objects"]
    need([o["id"] for o in objs] == list(range(len(objs))), "dense canonical object ids")
    need(len({tuple(o["position"]) for o in objs}) == len(objs), "initial object overlap")
    for o in objs:
        need(cell(o["position"]) and tuple(o["position"]) not in walls, "object position")
        need(all(type(o[k]) is bool for k in ("portable", "solid", "active", "hazard")), "object booleans")
        need(type(o["counter_max"]) is int and 0 <= o["counter_max"] <= 3, "finite counter")
        need(type(o["counter"]) is int and 0 <= o["counter"] <= o["counter_max"], "counter")
        need(type(o["mode"]) is int and 0 <= o["mode"] <= 3, "mode")
    need(not any(o["solid"] and o["active"] and o["position"] == genome["start"] for o in objs), "blocked initial state")
    ids = [r["id"] for r in genome["rules"]]
    need(all(type(i) is int and i >= 0 for i in ids) and len(ids) == len(set(ids)), "rule ids")

    def ref(d):
        need(type(d.get("object")) is int and 0 <= d["object"] < len(objs), "object reference")

    def flag(d):
        need(type(d.get("flag")) is int and 0 <= d["flag"] < len(genome["flags"]), "flag reference")

    for rule in genome["rules"]:
        trigger = rule["trigger"]
        need(trigger["event"] in TRIGGERS, "trigger")
        need(("object" in trigger) != ("cell" in trigger), "exactly one trigger target")
        if "object" in trigger:
            ref(trigger)
        else:
            need(trigger["event"] == "ENTER" and cell(trigger["cell"]), "cell trigger")
        need(len(rule["conditions"]) <= 4 and 1 <= len(rule["effects"]) <= 3, "bounded rule")
        for cond in rule["conditions"]:
            kind = cond["kind"]
            need(kind in CONDITIONS, "condition kind")
            if kind in ("carrying", "not_carrying", "active", "counter"):
                ref(cond)
            if kind == "flag":
                flag(cond)
            if kind in ("flag", "active"):
                need(type(cond["value"]) is bool, "condition boolean")
            if kind == "counter":
                need(cond["op"] in ("eq", "lt", "ge") and type(cond["value"]) is int, "counter comparison")
            if kind == "region":
                need(bool(cond["cells"]) and all(cell(p) for p in cond["cells"]), "region")
        for eff in rule["effects"]:
            kind = eff["kind"]
            need(kind in EFFECTS, "effect kind")
            if kind in ("set_flag", "toggle_flag"):
                flag(eff)
            elif kind != "teleport":
                ref(eff)
            if kind in ("set_flag", "set_active", "set_passability", "set_hazard"):
                need(type(eff["value"]) is bool, "effect boolean")
            if kind in ("teleport", "move"):
                need(cell(eff["position"]) and tuple(eff["position"]) not in walls, "effect position")
            if kind in ("give", "take"):
                need(objs[eff["object"]]["portable"], "inventory effect requires portable object")
            if kind == "increment":
                need(type(eff["value"]) is int and eff["value"] in (-1, 1), "bounded increment")
    return genome


@dataclass(frozen=True, slots=True)
class State:
    x: int
    y: int
    facing: int
    flags: tuple
    # x, y (-1,-1 carried; -2,-2 consumed), active, solid, counter, mode, hazard
    objects: tuple


class Engine:
    def __init__(self, genome):
        self.genome = json.loads(canonical(validate(genome)))
        self.width = genome["board"]["width"]
        self.height = genome["board"]["height"]
        self.walls = frozenset(map(tuple, genome["board"]["walls"]))
        self.rules = sorted(genome["rules"], key=lambda r: r["id"])
        self.start = tuple(genome["start"])
        self.goal = tuple(genome["goal"])
        self.initial = State(*self.start, 0, tuple(genome["flags"]), tuple(
            (*o["position"], o["active"], o["solid"], o["counter"], o["mode"], o["hazard"])
            for o in genome["objects"]))

    def is_goal(self, state):
        return (state.x, state.y) == self.goal

    def _free(self, x, y, objects, ignore=-1):
        return (0 <= x < self.width and 0 <= y < self.height and (x, y) not in self.walls
                and not any(i != ignore and o[0] == x and o[1] == y and o[2] and o[3]
                            for i, o in enumerate(objects)))

    @staticmethod
    def _condition(cond, x, y, flags, objects):
        kind = cond["kind"]
        if kind == "flag":
            return flags[cond["flag"]] == cond["value"]
        if kind == "region":
            return [x, y] in cond["cells"]
        o = objects[cond["object"]]
        if kind == "carrying":
            return o[:2] == [-1, -1]
        if kind == "not_carrying":
            return o[:2] != [-1, -1]
        if kind == "active":
            return o[2] == cond["value"]
        v = cond["value"]
        return {"eq": o[4] == v, "lt": o[4] < v, "ge": o[4] >= v}[cond["op"]]

    def step(self, state, action):
        if type(action) is not int or not 0 <= action < len(ACTIONS):
            raise ValueError("invalid action")
        x, y, facing = state.x, state.y, state.facing
        objects = [list(o) for o in state.objects]
        flags = list(state.flags)
        event, target = None, None
        if action < 4:
            facing = action
            dx, dy = DELTAS[action]
            if self._free(x + dx, y + dy, objects):
                x, y = x + dx, y + dy
                event = "ENTER"
        elif action == 4:
            target = next((i for i, o in enumerate(objects) if o[0] >= 0 and o[2]
                           and abs(o[0] - x) + abs(o[1] - y) <= 1), None)
            if target is not None:
                event = "INTERACT"
        elif action == 5:
            target = next((i for i, o in enumerate(objects) if o[:2] == [x, y]
                           and o[2] and self.genome["objects"][i]["portable"]), None)
            if target is not None:
                objects[target][:2] = [-1, -1]
                event = "PICK"
        elif action == 6:
            target = next((i for i, o in enumerate(objects) if o[:2] == [-1, -1]), None)
            if target is not None and self._free(x, y, objects, target):
                objects[target][:2] = [x, y]
                event = "DROP"
        else:
            dx, dy = DELTAS[facing]
            target = next((i for i, o in enumerate(objects) if o[:2] == [x + dx, y + dy]
                           and o[2] and o[3] and self.genome["objects"][i]["portable"]), None)
            if target is not None and self._free(x + 2 * dx, y + 2 * dy, objects, target):
                objects[target][:2] = [x + 2 * dx, y + 2 * dy]
                x, y = x + dx, y + dy
                event = "PUSH"
        # Each rule is visited once in id order. Conditions see preceding effects.
        # Effects do not recursively emit events. A PUSH also produces ENTER.
        entered = (x, y) != (state.x, state.y)
        entry_cell = (x, y)
        entry_objects = {i for i, o in enumerate(objects) if tuple(o[:2]) == entry_cell and o[2]}
        for rule in self.rules:
            trig = rule["trigger"]
            if trig["event"] == "ENTER":
                matches = entered and (tuple(trig["cell"]) == entry_cell if "cell" in trig else trig["object"] in entry_objects)
            else:
                matches = event == trig["event"] and target == trig.get("object")
            if not matches or not all(self._condition(c, x, y, flags, objects) for c in rule["conditions"]):
                continue
            for eff in rule["effects"]:
                kind = eff["kind"]
                if kind == "set_flag":
                    flags[eff["flag"]] = eff["value"]
                elif kind == "toggle_flag":
                    flags[eff["flag"]] = not flags[eff["flag"]]
                elif kind == "teleport":
                    if self._free(*eff["position"], objects):
                        x, y = eff["position"]
                else:
                    i = eff["object"]
                    o = objects[i]
                    if kind == "set_active":
                        o[2] = eff["value"]
                    elif kind == "set_passability":
                        o[3] = not eff["value"]
                    elif kind == "toggle_passability":
                        o[3] = not o[3]
                    elif kind == "give" and o[:2] != [-2, -2]:
                        o[:2] = [-1, -1]
                    elif kind == "take" and o[:2] == [-1, -1]:
                        o[:2] = [x, y]
                    elif kind == "consume":
                        o[:2] = [-2, -2]
                        o[2] = False
                    elif kind == "move" and o[:2] != [-2, -2]:
                        if self._free(*eff["position"], objects, i):
                            o[:2] = eff["position"]
                    elif kind == "increment":
                        o[4] = min(self.genome["objects"][i]["counter_max"], max(0, o[4] + eff["value"]))
                    elif kind == "set_hazard":
                        o[6] = eff["value"]
        # Hazard contact returns the player to start, preserving other variables.
        if any(o[:2] == [x, y] and o[2] and o[6] for o in objects):
            x, y = self.start
        result = State(x, y, facing, tuple(flags), tuple(map(tuple, objects)))
        return state if result == state else result


class OpaqueMap:
    """Lazy sampling without replacement from a 128-bit label namespace."""
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.states = {}
        self.labels = set()

    def encode(self, state):
        if state not in self.states:
            label = "state_" + format(self.rng.getrandbits(128), "032x")
            while label in self.labels:
                label = "state_" + format(self.rng.getrandbits(128), "032x")
            self.states[state] = label
            self.labels.add(label)
        return self.states[state]


class PlayerPort:
    """Only five public operations; this is an API boundary, not a Python sandbox."""
    __slots__ = ("reset", "current_observation", "available_actions", "step", "is_goal")


def make_port(engine, opaque):
    current = [engine.initial]
    def reset():
        current[0] = engine.initial
        return opaque.encode(current[0])
    def observation():
        return opaque.encode(current[0])
    def step(action):
        current[0] = engine.step(current[0], action)
        return observation()
    port = PlayerPort()
    port.reset = reset
    port.current_observation = observation
    port.available_actions = lambda: tuple(range(len(ACTIONS)))
    port.step = step
    port.is_goal = lambda: engine.is_goal(current[0])
    return port


def exact_oracle(engine, cap=250000):
    """Full reachable BFS. No oracle graph or path is given to the player/designer."""
    states = {engine.initial}
    queue = deque([(engine.initial, 0)])
    shortest = 0 if engine.is_goal(engine.initial) else None
    edges = 0
    while queue:
        state, depth = queue.popleft()
        for action in range(len(ACTIONS)):
            nxt = engine.step(state, action)
            edges += 1
            if shortest is None and engine.is_goal(nxt):
                shortest = depth + 1
            if nxt not in states:
                if len(states) >= cap:
                    return {"status": "UNRESOLVED_TOO_LARGE", "solvable": None,
                            "solution_witness_found": shortest is not None,
                            "reachable_states": None, "shortest_solution_length": shortest,
                            "explored_states": len(states), "examined_transitions": edges,
                            "exact_graph_complete": False}, states
                states.add(nxt)
                queue.append((nxt, depth + 1))
    return {"status": "SOLVABLE" if shortest is not None else "UNSOLVABLE",
            "solvable": shortest is not None, "reachable_states": len(states),
            "shortest_solution_length": shortest, "explored_states": len(states),
            "examined_transitions": edges, "exact_graph_complete": True}, states
