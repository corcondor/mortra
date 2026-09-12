"""Source-neutral uniform substitution grammars and typed emissions.

Grammar symbols describe reusable composition states.  They are deliberately
separate from the terminal operators of a source domain.  A geometry adapter
may therefore emit four rigid-fold primitives from a grammar with any finite
alphabet, while another adapter can emit matrices, graph moves, or proof rules
without changing this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import Callable, Mapping, Sequence, TypeVar


Summary = TypeVar("Summary")


@dataclass(frozen=True)
class UniformSubstitutionGrammar:
    """A finite, uniform string substitution over arbitrary symbol names."""

    alphabet: tuple[str, ...]
    images: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.alphabet or any(not symbol for symbol in self.alphabet):
            raise ValueError("the grammar alphabet must contain nonempty symbols")
        if len(set(self.alphabet)) != len(self.alphabet):
            raise ValueError("grammar symbols must be distinct")
        if len(self.images) != len(self.alphabet):
            raise ValueError("one substitution image is required per grammar symbol")
        widths = {len(image) for image in self.images}
        if len(widths) != 1 or next(iter(widths), 0) < 1:
            raise ValueError("all substitution images must have one common positive width")
        known = set(self.alphabet)
        if any(symbol not in known for image in self.images for symbol in image):
            raise ValueError("a substitution image contains an unknown grammar symbol")

    @property
    def width(self) -> int:
        return len(self.images[0])

    def image(self, symbol: str) -> tuple[str, ...]:
        try:
            return self.images[self.alphabet.index(symbol)]
        except ValueError as error:
            raise ValueError(f"unknown grammar symbol: {symbol}") from error

    @property
    def notation(self) -> tuple[str, ...]:
        return tuple(
            f"{symbol}->{','.join(self.image(symbol))}" for symbol in self.alphabet
        )

    def expand_tokens(self, *, seed_symbol: str, generation_count: int) -> tuple[str, ...]:
        if seed_symbol not in self.alphabet:
            raise ValueError("seed_symbol is outside the grammar alphabet")
        if generation_count < 0:
            raise ValueError("generation_count must be nonnegative")
        word = (seed_symbol,)
        for _ in range(generation_count):
            word = tuple(
                emitted
                for symbol in word
                for emitted in self.image(symbol)
            )
        return word


def validate_terminal_emissions(
    grammar: UniformSubstitutionGrammar,
    terminal_emissions: Mapping[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    """Validate a total, nonempty map from grammar symbols to source operators."""

    if set(terminal_emissions) != set(grammar.alphabet):
        raise ValueError("terminal emissions must cover the grammar alphabet exactly")
    normalized = {
        symbol: tuple(str(terminal) for terminal in terminal_emissions[symbol])
        for symbol in grammar.alphabet
    }
    if any(not terminals or any(not terminal for terminal in terminals) for terminals in normalized.values()):
        raise ValueError("every grammar symbol must emit nonempty terminal names")
    return normalized


def expand_emitted_tokens(
    grammar: UniformSubstitutionGrammar,
    terminal_emissions: Mapping[str, Sequence[str]],
    *,
    seed_symbol: str,
    generation_count: int,
) -> tuple[str, ...]:
    """Expand the grammar, then compile its symbols to typed source terminals."""

    emissions = validate_terminal_emissions(grammar, terminal_emissions)
    return tuple(
        terminal
        for symbol in grammar.expand_tokens(
            seed_symbol=seed_symbol,
            generation_count=generation_count,
        )
        for terminal in emissions[symbol]
    )


def iterate_emitted_summaries(
    grammar: UniformSubstitutionGrammar,
    terminal_emissions: Mapping[str, Sequence[str]],
    terminal_summaries: Mapping[str, Summary],
    compose: Callable[[Summary, Summary], Summary],
    *,
    seed_symbol: str,
    maximum_generation: int,
) -> tuple[Summary, ...]:
    """Evaluate exponentially long emitted words without materializing them."""

    if maximum_generation < 0:
        raise ValueError("maximum_generation must be nonnegative")
    emissions = validate_terminal_emissions(grammar, terminal_emissions)
    required_terminals = {
        terminal for values in emissions.values() for terminal in values
    }
    missing = required_terminals - set(terminal_summaries)
    if missing:
        raise ValueError(f"missing terminal summaries: {sorted(missing)}")

    summaries = {
        symbol: reduce(
            compose,
            (terminal_summaries[terminal] for terminal in emissions[symbol]),
        )
        for symbol in grammar.alphabet
    }
    if seed_symbol not in summaries:
        raise ValueError("seed_symbol is outside the grammar alphabet")

    result: list[Summary] = []
    for generation in range(maximum_generation + 1):
        result.append(summaries[seed_symbol])
        if generation == maximum_generation:
            break
        summaries = {
            symbol: reduce(compose, (summaries[token] for token in grammar.image(symbol)))
            for symbol in grammar.alphabet
        }
    return tuple(result)


__all__ = [
    "UniformSubstitutionGrammar",
    "expand_emitted_tokens",
    "iterate_emitted_summaries",
    "validate_terminal_emissions",
]
