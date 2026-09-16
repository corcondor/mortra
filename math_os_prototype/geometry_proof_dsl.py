"""Typed selection of existing exact proof procedures, not a new prover.

Request nodes describe a procedure, not a computed polynomial system. Only
`certify` executes it. Backend progress and all rejected certificates survive
in the trace. A request or a sampled diagram is never a proof.
"""
from collections import Counter
from dataclasses import asdict
import multiprocessing as mp
import time

from sympy.polys.polyerrors import CoercionFailed, PolynomialError

from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import (
    PrimitiveResult, RuntimePrimitive, initial_fact, synthesize_typed_plan,
)


def accepted_obligation(obligation):
    return bool(obligation.exact_replay and obligation.remainder == "0"
                and not obligation.vacuous_unit_ideal
                and not obligation.untransported_nonzero_conditions)


def request_options(request):
    representation = request["chart"]
    if representation == "relational":
        representation = ("goal_" if request["goal_slice"] else "") + (
            "local_" if request["local_elimination"] else "") + representation
    elif request["goal_slice"] or request["local_elimination"]:
        raise ValueError("relational chart required for relational transformations")
    return dict(representation=representation,
                enable_affine_local_lemmas=request["affine"],
                enable_structural_lemmas=request["structural"])


def proof_operations():
    return {
        "explicit_chart": ("JGEXStatement", "ExactProofRequest"),
        "relational_chart": ("JGEXStatement", "ExactProofRequest"),
        "local_elimination": ("ExactProofRequest", "ExactProofRequest"),
        "goal_slice": ("ExactProofRequest", "ExactProofRequest"),
        "affine": ("ExactProofRequest", "ExactProofRequest"),
        "structural": ("ExactProofRequest", "ExactProofRequest"),
        "certify": ("ExactProofRequest", "ExactGeometryCertificate"),
    }


def _proof_worker(connection, statement, options):
    """One bounded proof attempt. No search decisions or external input here."""
    from worker.backend.jgex_exact_constraint_bridge import lower_jgex_to_exact_obligation
    try:
        result = lower_jgex_to_exact_obligation(statement, **options,
            progress_callback=lambda e: connection.send(("progress", e)))
        connection.send(("result", result))
    except Exception as exc:
        connection.send(("error", type(exc).__name__+": "+str(exc)))
    finally:
        connection.close()


def bounded_proof(statement, options, seconds, emit):
    """Charge process startup, computation and transfer to the same attempt."""
    if seconds <= 0:
        raise ValueError("positive proof attempt timeout required")
    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_proof_worker, args=(sender, statement, options))
    start = time.perf_counter()
    try:
        worker.start()
        sender.close()
        while True:
            remaining = seconds-(time.perf_counter()-start)
            if remaining <= 0 or not receiver.poll(remaining):
                raise TimeoutError("proof attempt budget exhausted")
            try:
                kind, payload = receiver.recv()
            except EOFError as exc:
                raise RuntimeError("proof worker exited without a result") from exc
            if kind == "progress":
                emit(payload)
            elif kind == "result":
                return payload
            else:
                raise RuntimeError(payload)
    finally:
        if worker.pid is not None:
            if worker.is_alive():
                worker.terminate()
            worker.join()
        receiver.close()
        sender.close()


def _proof_session_worker(connection):
    """Reuse imports, not proof results or task-dependent search decisions."""
    try:
        from sympy.core.cache import clear_cache
        from worker.backend.jgex_exact_constraint_bridge import lower_jgex_to_exact_obligation
        connection.send((None, "ready", None))
        while True:
            request = connection.recv()
            if request is None:
                return
            request_id, statement, options = request
            started = time.perf_counter()
            try:
                clear_cache()
                result = lower_jgex_to_exact_obligation(statement, **options,
                    progress_callback=lambda e: connection.send((request_id, "progress", e)))
                kind, payload = "result", result
            except Exception as exc:
                kind, payload = "error", type(exc).__name__+": "+str(exc)
            connection.send((request_id, "backend_seconds", time.perf_counter()-started))
            connection.send((request_id, kind, payload))
    except EOFError:
        pass
    finally:
        connection.close()


class ProofSession:
    """One sequential worker, replaced on timeout, error or broken transport.

    Every call constructs a fresh obligation. Startup, transfer and computation
    all count against its deadline. Timed-out results cannot reach later calls.
    """
    def __init__(self):
        self.worker = self.connection = None
        self.sequence = 0
        self.costs = Counter()
        self.started_at = None

    def close(self):
        start = time.perf_counter()
        if self.worker is not None:
            if self.worker.pid is not None:
                if self.worker.is_alive():
                    self.worker.terminate()
                self.worker.join()
            self.worker.close()
            self.worker = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.costs["proof_worker_cleanup_seconds"] += time.perf_counter()-start

    def run(self, statement, options, seconds, emit):
        if seconds <= 0:
            raise ValueError("positive proof attempt timeout required")
        start = time.perf_counter()
        self.sequence += 1
        request_id = self.sequence
        try:
            if self.worker is None:
                context = mp.get_context("spawn")
                self.connection, child = context.Pipe()
                self.worker = context.Process(target=_proof_session_worker, args=(child,))
                self.started_at = start
                try:
                    self.worker.start()
                finally:
                    child.close()
                self.costs["proof_worker_starts"] += 1
            else:
                self.costs["proof_worker_reused_requests"] += 1
            self.connection.send((request_id, statement, options))
            while True:
                remaining = seconds-(time.perf_counter()-start)
                if remaining <= 0 or not self.connection.poll(remaining):
                    raise TimeoutError("proof attempt budget exhausted")
                try:
                    received_id, kind, payload = self.connection.recv()
                except (EOFError, OSError) as exc:
                    raise RuntimeError("proof worker exited without a result") from exc
                if kind == "ready" and received_id is None:
                    self.costs["proof_worker_startup_seconds"] += time.perf_counter()-self.started_at
                    continue
                if received_id != request_id:
                    raise RuntimeError("proof worker request mismatch")
                if kind == "progress":
                    emit(payload)
                elif kind == "backend_seconds":
                    self.costs["proof_worker_completed_backend_seconds"] += payload
                elif kind == "result":
                    return payload
                else:
                    raise RuntimeError(payload)
        except TimeoutError:
            self.costs["proof_worker_resets"] += 1
            self.close()
            raise
        except (EOFError, OSError) as exc:
            self.costs["proof_worker_resets"] += 1
            self.close()
            raise RuntimeError("proof worker transport failed") from exc
        except BaseException:
            self.costs["proof_worker_resets"] += 1
            self.close()
            raise
        finally:
            self.costs["proof_worker_request_seconds"] += time.perf_counter()-start


def search_exact_proof(statement, *, budget=64, max_depth=7, emit=lambda e: None,
                       backend_limits=None, attempt_seconds=None, reuse_worker=False):
    """The shared planner chooses requests and their compositions.

    All switches refer to the existing bridge. No task name, auxiliary, chart
    answer or completed request is supplied by the caller. Costs count failed
    proof attempts too; acquiring a request does not count as new mathematics.
    """
    from worker.backend.jgex_exact_constraint_bridge import lower_jgex_to_exact_obligation
    costs, attempts = Counter(), []
    limits = dict(backend_limits or {})
    allowed = {"local_max_steps", "local_max_output_terms", "local_max_resultant_degree",
               "local_max_separator_variables", "max_saturation_rounds"}
    if set(limits)-allowed:
        raise ValueError("proof DSL accepts resource bounds, not injected proof options")
    if reuse_worker and attempt_seconds is None:
        raise ValueError("worker reuse requires a finite proof attempt timeout")
    session = ProofSession() if reuse_worker else None

    def chart(args, name):
        value = {"statement": args[0].value, "chart": name, "local_elimination": False,
                 "goal_slice": False, "affine": False, "structural": False}
        return PrimitiveResult(value, {"operation": name+"_chart", "input": digest(args[0].value)})

    def transform(args, operation):
        before = args[0].value
        if before[operation] or (operation in {"goal_slice", "local_elimination"}
                                and before["chart"] != "relational"):
            return None
        after = dict(before, **{operation: True})
        return PrimitiveResult(after, {"operation": operation, "input": digest(before),
                                       "output": digest(after)})

    def certify(args):
        request = args[0].value
        options = request_options(request)
        start = time.perf_counter()
        costs["exact_prover_calls"] += 1
        row = {"request": request, "options": options, "accepted": False}
        worker_costs_before = session.costs.copy() if session is not None else Counter()
        emit({"event": "proof_dsl_attempt_started", "request": request})
        try:
            progress = lambda e: emit({"event": "proof_backend_progress",
                                      "request_sha256": digest(request), **e})
            if attempt_seconds is None:
                obligation = lower_jgex_to_exact_obligation(statement, **options, **limits,
                                                           progress_callback=progress)
            elif session is not None:
                obligation = session.run(statement, dict(options, **limits), attempt_seconds, progress)
            else:
                obligation = bounded_proof(statement, dict(options, **limits), attempt_seconds, progress)
            row.update(accepted=accepted_obligation(obligation), obligation=asdict(obligation))
        except (ValueError, NotImplementedError, CoercionFailed, PolynomialError,
                TimeoutError, RuntimeError) as exc:
            row["refusal"] = type(exc).__name__+": "+str(exc)
            row["timed_out"] = isinstance(exc, TimeoutError)
            costs["exact_prover_timeouts"] += int(row["timed_out"])
        row["seconds"] = time.perf_counter()-start
        if session is not None:
            row["worker_costs"] = dict(session.costs-worker_costs_before)
        costs["exact_prover_seconds"] += row["seconds"]
        attempts.append(row)
        emit({"event": "proof_dsl_attempt", **row})
        if not row["accepted"]:
            return None
        return PrimitiveResult(row, {"operation": "certify", "options": options,
            "certificate_sha256": obligation.certificate_sha256})

    primitives = [RuntimePrimitive(name+"_chart", ("JGEXStatement",), "ExactProofRequest",
                     lambda a, name=name: chart(a, name)) for name in ("explicit", "relational")]
    primitives += [RuntimePrimitive(name, ("ExactProofRequest",), "ExactProofRequest",
                      lambda a, name=name: transform(a, name))
                   for name in ("local_elimination", "goal_slice", "affine", "structural")]
    primitives.append(RuntimePrimitive("certify", ("ExactProofRequest",), "ExactGeometryCertificate", certify))
    start = time.perf_counter()
    try:
        plan = synthesize_typed_plan([initial_fact("JGEXStatement", statement)], primitives,
            ["ExactGeometryCertificate"], max_depth=max_depth, max_states=budget, fair=True,
            value_key=lambda sort, value: digest(value))
    finally:
        if session is not None:
            session.close()
            costs.update(session.costs)
    goal = plan.goals.get("ExactGeometryCertificate")
    result = dict(goal.value) if goal else dict(attempts[0] if attempts else {})
    result.update(statement=statement, accepted=bool(goal), proof_program=list(plan.proof_program),
                  proof_dsl_costs=dict(costs, planner_applications=plan.states_explored-1,
                                       total_seconds=time.perf_counter()-start),
                  proof_attempts=attempts,
                  stop_reason="certified" if goal else "proof_dsl_budget_or_request_exhaustion")
    emit({"event": "proof_dsl_completed", "accepted": bool(goal),
          "program": result["proof_program"], "costs": result["proof_dsl_costs"]})
    return result
