"""Simulate and synthesize the MORTRA FPGA geometry prefilter."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from amaranth.back import verilog
from amaranth.sim import Simulator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.fpga.mortra_geometry_prefilter import (  # noqa: E402
    GeometryPrefilter,
    OP_DISTINCT_PAIR,
    OP_NONCOLLINEAR_TRIPLE,
    OP_NONPARALLEL_LINES,
    OP_PASS,
    PrefilterVector,
    ports,
    reference_accept,
)


def vectors(count: int, seed: int, coordinate_limit: int) -> list[PrefilterVector]:
    rng = random.Random(seed)
    result: list[PrefilterVector] = []
    opcodes = (
        OP_PASS,
        OP_DISTINCT_PAIR,
        OP_NONCOLLINEAR_TRIPLE,
        OP_NONPARALLEL_LINES,
    )
    for index in range(count):
        opcode = opcodes[index % len(opcodes)]
        points = tuple(
            (
                rng.randint(-coordinate_limit, coordinate_limit),
                rng.randint(-coordinate_limit, coordinate_limit),
            )
            for _ in range(4)
        )
        # Force regular degenerate cases into the test stream.
        if index % 17 == 0:
            points = (points[0], points[0], points[2], points[3])
        elif index % 19 == 0:
            x0, y0 = points[0]
            points = ((x0, y0), (x0 + 1, y0 + 2), (x0 + 2, y0 + 4), points[3])
        elif index % 23 == 0:
            points = ((0, 0), (2, 3), (7, -1), (9, 2))
        result.append(PrefilterVector(opcode, points))
    return result


def simulate(design: GeometryPrefilter, cases: list[PrefilterVector]) -> list[bool]:
    simulator = Simulator(design)
    simulator.add_clock(1e-6)
    observed: list[bool] = []

    async def bench(context) -> None:
        for case in cases:
            context.set(design.valid_in, 1)
            context.set(design.opcode, case.opcode)
            for index, (x, y) in enumerate(case.points):
                context.set(design.x[index], x)
                context.set(design.y[index], y)
            await context.tick()
            assert context.get(design.valid_out) == 1
            observed.append(bool(context.get(design.accept)))
        context.set(design.valid_in, 0)
        await context.tick()
        assert context.get(design.valid_out) == 0

    simulator.add_testbench(bench)
    simulator.run()
    return observed


def synthesize(verilog_path: Path, stat_path: Path) -> dict[str, object]:
    sibling = Path(sys.executable).with_name("yowasp-yosys.exe")
    yosys = shutil.which("yowasp-yosys") or (str(sibling) if sibling.is_file() else None)
    if yosys is None:
        raise RuntimeError("yowasp-yosys is required for target-aware synthesis")
    command = [
        yosys,
        "-Q",
        "-q",
        "-p",
        (
            f"read_verilog {verilog_path.as_posix()}; "
            "synth_xilinx -family xc7 -top mortra_geometry_prefilter; "
            f"tee -o {stat_path.as_posix()} stat -json"
        ),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-4000:] or completed.stdout[-4000:])
    raw = stat_path.read_text(encoding="utf-8")
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"Yosys did not emit JSON statistics: {raw[-2000:]}")
    payload = json.loads(raw[start : end + 1])
    stat_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    module = payload["modules"]["\\mortra_geometry_prefilter"]
    return {
        "yosys_version": payload.get("creator"),
        "wires": module.get("num_wires"),
        "wire_bits": module.get("num_wire_bits"),
        "cells": module.get("num_cells"),
        "cell_types": module.get("num_cells_by_type", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu-profile-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verilog", type=Path, required=True)
    parser.add_argument("--yosys-stat", type=Path, required=True)
    parser.add_argument("--vectors", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260819)
    parser.add_argument("--coordinate-width", type=int, default=18)
    parser.add_argument("--frequencies-mhz", default="100,200")
    args = parser.parse_args()

    design = GeometryPrefilter(coordinate_width=args.coordinate_width)
    cases = vectors(args.vectors, args.seed, 2 ** (args.coordinate_width - 2))
    expected = [reference_accept(case) for case in cases]
    started = time.perf_counter()
    observed = simulate(design, cases)
    simulation_seconds = time.perf_counter() - started
    mismatches = [
        index for index, (left, right) in enumerate(zip(expected, observed)) if left != right
    ]

    args.verilog.parent.mkdir(parents=True, exist_ok=True)
    args.verilog.write_text(
        verilog.convert(
            design,
            name="mortra_geometry_prefilter",
            ports=ports(design),
        ),
        encoding="utf-8",
    )
    args.yosys_stat.parent.mkdir(parents=True, exist_ok=True)
    synthesis = synthesize(args.verilog.resolve(), args.yosys_stat.resolve())

    cpu_profile = json.loads(args.cpu_profile_summary.read_text(encoding="utf-8"))
    measured_cpu = cpu_profile["measured_cpu"]
    before_elapsed = float(measured_cpu["before_attempt_seconds"])
    after_elapsed = float(measured_cpu["after_lazy_attempt_seconds"])
    candidate_count = int(measured_cpu["candidate_count"])
    frequencies = [float(item) for item in args.frequencies_mhz.split(",") if item]
    throughput = {
        str(frequency): {
            "candidates_per_second": frequency * 1_000_000,
            "seconds_for_measured_trajectory": candidate_count / (frequency * 1_000_000),
        }
        for frequency in frequencies
    }
    lazy_enum_seconds = float(measured_cpu["after_enumeration_seconds_profiled"])
    artifact = {
        "experiment": "mortra_fpga_geometry_prefilter_post_synthesis",
        "protocol": {
            "uses_external_llm": False,
            "truth_plane_changed": False,
            "acceptance_requires_symbolic_replay": True,
            "hardware_status": "rtl_simulation_and_xilinx_7series_post_synthesis_only",
            "physical_fpga_board_measured": False,
            "pipeline_initiation_interval_cycles": 1,
            "pipeline_latency_cycles": 1,
            "coordinate_width": args.coordinate_width,
            "synthesis_target": "Xilinx 7-series primitive mapping",
        },
        "equivalence": {
            "vectors": len(cases),
            "mismatches": len(mismatches),
            "first_mismatch_indices": mismatches[:20],
            "simulation_seconds": simulation_seconds,
        },
        "synthesis": synthesis,
        "measured_cpu": measured_cpu,
        "fpga_throughput_model": throughput,
        "end_to_end_bound_after_lazy": {
            "amdahl_max_if_enumeration_were_free": (
                after_elapsed / max(after_elapsed - lazy_enum_seconds, 1e-12)
            ),
            "scope": (
                "candidate tuple/precondition/rank kernel only; numerical construction, "
                "incidence profiling, PCIe transfer, and Yuclid remain on CPU"
            ),
        },
        "artifacts": {
            "verilog": args.verilog.resolve().relative_to(ROOT).as_posix(),
            "verilog_sha256": hashlib.sha256(args.verilog.read_bytes()).hexdigest(),
            "yosys_stat": args.yosys_stat.resolve().relative_to(ROOT).as_posix(),
            "cpu_profile_summary": args.cpu_profile_summary.resolve().relative_to(ROOT).as_posix(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
